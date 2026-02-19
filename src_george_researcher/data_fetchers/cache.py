"""
TTL-based data cache using SQLite.

Provides persistent caching for API responses to reduce costs and latency.
Uses synchronous SQLite (sqlite3) to match existing sync data fetchers.

Usage:
    from .cache import cached

    @cached("fds_prices", ticker_param="ticker")
    def fetch_prices(ticker: str, limit: int = 365) -> Tuple[...]:
        ...
"""
import sqlite3
import json
import hashlib
import logging
import inspect
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any, Dict, Set
from dataclasses import dataclass, is_dataclass, fields
from functools import wraps

logger = logging.getLogger(__name__)

# =============================================================================
# TTL Configuration (in seconds)
# =============================================================================
TTL_CONFIG = {
    "gemini_search": 2 * 3600,           # 2 hours - news freshness
    "fds_prices": 24 * 3600,             # 24 hours - daily prices
    "fds_financials": 7 * 24 * 3600,     # 7 days - quarterly data
    "fds_analyst_estimates": 7 * 24 * 3600,  # 7 days
    "fds_insider_trades": 7 * 24 * 3600,     # 7 days
    "fds_news": 2 * 3600,                # 2 hours - news freshness
    "fds_company_facts": 24 * 3600,      # 24 hours
    "yfinance_info": 24 * 3600,          # 24 hours
    "yfinance_history": 24 * 3600,       # 24 hours
    "yfinance_chart": 24 * 3600,         # 24 hours
}

# Cost per request for savings calculation
COST_CONFIG = {
    "gemini_search": 0.035,
    "fds_prices": 0.01,
    "fds_financials": 0.02,
    "fds_analyst_estimates": 0.02,
    "fds_insider_trades": 0.02,
    "fds_news": 0.02,
    "fds_company_facts": 0.0,  # FREE endpoint
    "yfinance_info": 0.0,
    "yfinance_history": 0.0,
    "yfinance_chart": 0.0,
}


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    total_entries: int = 0
    total_size_bytes: int = 0
    hits: int = 0
    misses: int = 0
    total_cost_saved_usd: float = 0.0
    by_type: Dict[str, int] = None
    expired_count: int = 0

    def __post_init__(self):
        if self.by_type is None:
            self.by_type = {}


class DataCache:
    """
    Synchronous SQLite cache for data fetcher responses.

    Thread-safe for reads, serializes writes via SQLite locks.
    Matches the synchronous design of existing data fetchers.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS data_cache (
        cache_key TEXT PRIMARY KEY,
        data_type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        data_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        hit_count INTEGER DEFAULT 0,
        last_accessed_at TEXT,
        size_bytes INTEGER DEFAULT 0,
        cost_saved_usd REAL DEFAULT 0.0
    );
    CREATE INDEX IF NOT EXISTS idx_cache_ticker ON data_cache(ticker);
    CREATE INDEX IF NOT EXISTS idx_cache_type ON data_cache(data_type);
    CREATE INDEX IF NOT EXISTS idx_cache_expires ON data_cache(expires_at);
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to data/cache.db relative to project root
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "data" / "cache.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._hits = 0
        self._misses = 0

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        """Initialize the database schema."""
        if self._initialized:
            return
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
        self._initialized = True
        logger.info(f"Data cache initialized at {self.db_path}")

    def _generate_key(self, data_type: str, ticker: str, **params) -> str:
        """Generate unique cache key from parameters."""
        key_parts = [data_type, ticker.upper()]
        for k, v in sorted(params.items()):
            key_parts.append(f"{k}={v}")
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _serialize(self, data: Any) -> str:
        """Serialize data to JSON string."""
        try:
            # Handle pandas DataFrame
            if hasattr(data, 'to_dict') and hasattr(data, 'index'):
                # Convert DataFrame to dict, handling timestamp index
                df_dict = data.to_dict(orient="split")
                # Convert any Timestamp objects to ISO strings
                if df_dict.get("index"):
                    df_dict["index"] = [
                        idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                        for idx in df_dict["index"]
                    ]
                return json.dumps({
                    "_type": "dataframe",
                    "data": df_dict,
                    "index_name": getattr(data.index, 'name', None),
                })
            elif is_dataclass(data) and not isinstance(data, type):
                return json.dumps({
                    "_type": "dataclass",
                    "_class": f"{data.__class__.__module__}.{data.__class__.__name__}",
                    "data": self._dataclass_to_dict(data),
                })
            elif isinstance(data, list) and data and is_dataclass(data[0]):
                return json.dumps({
                    "_type": "dataclass_list",
                    "_class": f"{data[0].__class__.__module__}.{data[0].__class__.__name__}",
                    "data": [self._dataclass_to_dict(item) for item in data],
                })
            else:
                return json.dumps({"_type": "raw", "data": data})
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise

    def _dataclass_to_dict(self, obj: Any) -> dict:
        """Convert dataclass to dict, handling nested dataclasses."""
        if is_dataclass(obj) and not isinstance(obj, type):
            result = {}
            for f in fields(obj):
                value = getattr(obj, f.name)
                result[f.name] = self._dataclass_to_dict(value)
            return result
        elif isinstance(obj, list):
            return [self._dataclass_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._dataclass_to_dict(v) for k, v in obj.items()}
        else:
            return obj

    def _deserialize(self, json_str: str) -> Any:
        """Deserialize JSON string to original type."""
        parsed = json.loads(json_str)
        type_hint = parsed.get("_type", "raw")

        if type_hint == "dataframe":
            import pandas as pd
            data_dict = parsed["data"]
            # Convert ISO string index back to DatetimeIndex if applicable
            if data_dict.get("index"):
                try:
                    data_dict["index"] = pd.to_datetime(data_dict["index"])
                except Exception:
                    pass  # Keep as-is if conversion fails
            df = pd.DataFrame(**data_dict)
            if parsed.get("index_name"):
                df.index.name = parsed["index_name"]
            return df
        elif type_hint == "dataclass":
            cls = self._import_class(parsed["_class"])
            return self._dict_to_dataclass(cls, parsed["data"])
        elif type_hint == "dataclass_list":
            cls = self._import_class(parsed["_class"])
            return [self._dict_to_dataclass(cls, item) for item in parsed["data"]]
        else:
            return parsed.get("data")

    def _dict_to_dataclass(self, cls: type, data: dict) -> Any:
        """Convert dict back to dataclass instance, handling nested dataclasses."""
        import typing

        field_types = {f.name: f.type for f in fields(cls)}
        kwargs = {}

        for key, value in data.items():
            if key not in field_types:
                continue

            field_type = field_types[key]

            # Handle None values
            if value is None:
                kwargs[key] = None
                continue

            # Get the origin type for generics (e.g., list, List, Optional)
            origin = typing.get_origin(field_type)
            args = typing.get_args(field_type)

            # Handle list[SomeDataclass] or List[SomeDataclass]
            if origin is list and args and isinstance(value, list):
                inner_type = args[0]
                if is_dataclass(inner_type) and not isinstance(inner_type, type):
                    inner_type = type(inner_type)
                if is_dataclass(inner_type):
                    kwargs[key] = [
                        self._dict_to_dataclass(inner_type, item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    kwargs[key] = value
            # Handle Optional[SomeDataclass]
            elif origin is typing.Union and type(None) in args:
                # Get the non-None type
                non_none_types = [t for t in args if t is not type(None)]
                if non_none_types:
                    inner_type = non_none_types[0]
                    if is_dataclass(inner_type) and isinstance(value, dict):
                        kwargs[key] = self._dict_to_dataclass(inner_type, value)
                    else:
                        kwargs[key] = value
                else:
                    kwargs[key] = value
            # Handle nested dataclass directly
            elif is_dataclass(field_type) and isinstance(value, dict):
                kwargs[key] = self._dict_to_dataclass(field_type, value)
            else:
                kwargs[key] = value

        return cls(**kwargs)

    def _import_class(self, full_class_name: str):
        """Dynamically import a class from its full name."""
        parts = full_class_name.rsplit(".", 1)
        if len(parts) == 2:
            module_name, class_name = parts
            import importlib
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        raise ValueError(f"Invalid class name: {full_class_name}")

    def get(
        self,
        data_type: str,
        ticker: str,
        **params
    ) -> Optional[Any]:
        """
        Retrieve cached data if not expired.

        Returns None if cache miss or expired.
        """
        self.initialize()
        cache_key = self._generate_key(data_type, ticker, **params)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT data_json, expires_at, cost_saved_usd
                FROM data_cache
                WHERE cache_key = ?
                """,
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                self._misses += 1
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                # Expired - delete and return None
                conn.execute(
                    "DELETE FROM data_cache WHERE cache_key = ?",
                    (cache_key,)
                )
                conn.commit()
                self._misses += 1
                logger.debug(f"Cache EXPIRED: {data_type}:{ticker}")
                return None

            # Update hit count and last accessed
            cost = COST_CONFIG.get(data_type, 0.0)
            conn.execute(
                """
                UPDATE data_cache
                SET hit_count = hit_count + 1,
                    last_accessed_at = ?,
                    cost_saved_usd = cost_saved_usd + ?
                WHERE cache_key = ?
                """,
                (datetime.now().isoformat(), cost, cache_key)
            )
            conn.commit()

            self._hits += 1
            logger.debug(f"Cache HIT: {data_type}:{ticker}")
            return self._deserialize(row["data_json"])

    def set(
        self,
        data_type: str,
        ticker: str,
        data: Any,
        **params
    ) -> None:
        """
        Store data in cache with TTL.
        """
        self.initialize()
        cache_key = self._generate_key(data_type, ticker, **params)
        ttl_seconds = TTL_CONFIG.get(data_type, 3600)

        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl_seconds)

        data_json = self._serialize(data)
        size_bytes = len(data_json.encode('utf-8'))

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO data_cache
                (cache_key, data_type, ticker, data_json, created_at,
                 expires_at, hit_count, last_accessed_at, size_bytes, cost_saved_usd)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 0.0)
                """,
                (cache_key, data_type, ticker.upper(), data_json,
                 now.isoformat(), expires_at.isoformat(),
                 now.isoformat(), size_bytes)
            )
            conn.commit()

        logger.debug(f"Cache SET: {data_type}:{ticker}, TTL={ttl_seconds}s, size={size_bytes}B")

    def invalidate(
        self,
        ticker: Optional[str] = None,
        data_type: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            ticker: Invalidate all entries for this ticker
            data_type: Invalidate all entries of this type

        Returns:
            Number of entries deleted
        """
        self.initialize()

        with self._get_connection() as conn:
            if ticker and data_type:
                cursor = conn.execute(
                    "DELETE FROM data_cache WHERE ticker = ? AND data_type = ?",
                    (ticker.upper(), data_type)
                )
            elif ticker:
                cursor = conn.execute(
                    "DELETE FROM data_cache WHERE ticker = ?",
                    (ticker.upper(),)
                )
            elif data_type:
                cursor = conn.execute(
                    "DELETE FROM data_cache WHERE data_type = ?",
                    (data_type,)
                )
            else:
                cursor = conn.execute("DELETE FROM data_cache")

            conn.commit()
            deleted = cursor.rowcount
            logger.info(f"Cache invalidated: {deleted} entries (ticker={ticker}, type={data_type})")
            return deleted

    def cleanup_expired(self) -> int:
        """Remove expired entries. Call periodically."""
        self.initialize()

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM data_cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired cache entries")
            return deleted

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self.initialize()

        with self._get_connection() as conn:
            # Total entries and size
            cursor = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0), COALESCE(SUM(cost_saved_usd), 0) FROM data_cache"
            )
            row = cursor.fetchone()
            total_entries = row[0]
            total_size = row[1]
            total_cost_saved = row[2]

            # By type breakdown
            cursor = conn.execute(
                "SELECT data_type, COUNT(*) FROM data_cache GROUP BY data_type"
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Expired count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM data_cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            expired = cursor.fetchone()[0]

        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size,
            hits=self._hits,
            misses=self._misses,
            total_cost_saved_usd=total_cost_saved,
            by_type=by_type,
            expired_count=expired,
        )


# =============================================================================
# Global singleton
# =============================================================================
_CACHE_INSTANCE: Optional[DataCache] = None


def get_data_cache() -> DataCache:
    """Get the singleton DataCache instance."""
    global _CACHE_INSTANCE
    if _CACHE_INSTANCE is None:
        _CACHE_INSTANCE = DataCache()
    return _CACHE_INSTANCE


# =============================================================================
# Caching Decorator
# =============================================================================
def cached(
    data_type: str,
    ticker_param: str = "ticker",
    exclude_params: Optional[Set[str]] = None
):
    """
    Decorator for caching data fetcher results.

    Works with functions that return (result, error) tuples.
    Only caches successful results (error is None).

    Args:
        data_type: Cache type key (e.g., "fds_prices")
        ticker_param: Name of the ticker parameter in the function
        exclude_params: Set of parameter names to exclude from cache key

    Usage:
        @cached("fds_prices", ticker_param="ticker")
        def fetch_prices(ticker: str, limit: int = 365):
            ...

        @cached("gemini_search", ticker_param="symbol", exclude_params={"api_key"})
        def search_with_gemini(symbol: str, api_key: str, ...):
            ...
    """
    if exclude_params is None:
        exclude_params = set()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_data_cache()

            # Get function signature
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())

            # Build a dict of all arguments
            bound_args = {}
            for i, arg in enumerate(args):
                if i < len(param_names):
                    bound_args[param_names[i]] = arg
            bound_args.update(kwargs)

            # Extract ticker
            ticker = bound_args.get(ticker_param, "")
            if not ticker:
                # Can't cache without ticker
                return func(*args, **kwargs)

            # Build cache params (excluding ticker and excluded params)
            cache_params = {
                k: v for k, v in bound_args.items()
                if k != ticker_param and k not in exclude_params
            }

            # Check cache
            cached_result = cache.get(data_type, ticker, **cache_params)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}({ticker})")
                return (cached_result, None)

            # Call original function
            result, error = func(*args, **kwargs)

            # Cache on success
            if error is None and result is not None:
                cache.set(data_type, ticker, result, **cache_params)
                logger.debug(f"Cached result for {func.__name__}({ticker})")

            return (result, error)

        return wrapper
    return decorator
