"""Smoke tests that verify all modules can be imported without errors.

These tests would have caught:
- The USFullAnalysis dataclass field ordering bug
- The swot/strategy SectionType mismatch
- Any broken import chains or missing dependencies
"""

import importlib
import pytest


def _has_module(name: str) -> bool:
    """Check whether a Python package is importable without side effects."""
    from importlib.util import find_spec
    return find_spec(name) is not None


# Modules gated behind optional backend dependencies.
# When the dep is missing the import will fail for structural reasons
# (transitive import chain), not because our code is broken.
_needs_bcrypt = pytest.mark.skipif(not _has_module("bcrypt"), reason="bcrypt not installed")
_needs_aiosqlite = pytest.mark.skipif(not _has_module("aiosqlite"), reason="aiosqlite not installed")
_needs_weasyprint = pytest.mark.skipif(
    not __import__("os").environ.get("DYLD_LIBRARY_PATH"),
    reason="WeasyPrint requires DYLD_LIBRARY_PATH set for pango/gobject libraries",
)


class TestBackendCoreImports:
    """Verify all backend.core modules import cleanly."""

    @pytest.mark.parametrize("module", [
        pytest.param("backend.core.auth", marks=_needs_bcrypt),
        pytest.param("backend.core.auth_db", marks=_needs_aiosqlite),
        pytest.param("backend.core.base_db", marks=_needs_aiosqlite),
        "backend.core.belief_classifier",
        "backend.core.belief_graph",
        "backend.core.branding_config",
        "backend.core.chart_generator",
        "backend.core.context_manager",
        "backend.core.contradiction_detector",
        "backend.core.cost_tracker",
        "backend.core.exceptions",
        "backend.core.intent_classifier",
        "backend.core.pdf_data_collector",
        pytest.param("backend.core.pdf_generator_v2", marks=_needs_weasyprint),
        "backend.core.rag_engine",
        "backend.core.report_builder",
        "backend.core.report_editor",
        "backend.core.report_rag",
        "backend.core.session",
        pytest.param("backend.core.settings_db", marks=_needs_aiosqlite),
        pytest.param("backend.core.usage_db", marks=_needs_aiosqlite),
        pytest.param("backend.core.watchlist_db", marks=_needs_aiosqlite),
    ])
    def test_import_core_module(self, module):
        importlib.import_module(module)


@pytest.mark.skipif(not _has_module("aiosqlite"), reason="aiosqlite not installed")
class TestBackendRouterImports:
    """Verify all backend.routers modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.routers.analysis",
        "backend.routers.auth",
        "backend.routers.cache",
        "backend.routers.chart",
        "backend.routers.chat",
        "backend.routers.companies",
        "backend.routers.reports",
        "backend.routers.sessions",
        "backend.routers.settings",
        "backend.routers.usage",
        "backend.routers.watchlist",
    ])
    def test_import_router_module(self, module):
        importlib.import_module(module)


class TestBackendModelImports:
    """Verify all backend.models modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.models.auth",
        "backend.models.requests",
        "backend.models.responses",
    ])
    def test_import_model_module(self, module):
        importlib.import_module(module)


class TestBackendServiceImports:
    """Verify all backend.services modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.services.chat_service",
        "backend.services.export_service",
    ])
    def test_import_service_module(self, module):
        importlib.import_module(module)


@pytest.mark.skipif(not _has_module("bcrypt"), reason="bcrypt not installed")
class TestBackendMiddlewareImports:
    """Verify all backend.middleware modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.middleware.auth_middleware",
        "backend.middleware.usage_tracker",
    ])
    def test_import_middleware_module(self, module):
        importlib.import_module(module)


@pytest.mark.skipif(not _has_module("aiosqlite"), reason="aiosqlite not installed")
class TestBackendMainImport:
    """Verify the FastAPI app itself can be imported."""

    def test_import_main(self):
        importlib.import_module("backend.main")

    def test_app_object_exists(self):
        main = importlib.import_module("backend.main")
        assert hasattr(main, "app"), "backend.main must export 'app'"
