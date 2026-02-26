"""
FastAPI routers for George Research API.

Each router handles a specific domain of functionality:
- analysis: Stock analysis initiation and job queue management
- auth: User authentication (register, login, logout, refresh tokens)
- cache: Cache statistics, invalidation, and cleanup
- chart: Technical chart data with indicators
- chat: Conversational chat with analyst (SSE streaming)
- companies: Company classification and lookup
- reports: Report retrieval and export (PDF, markdown)
- sessions: Session management (list, resume, delete)
- usage: User API usage tracking and cost monitoring
"""

from . import analysis, auth, cache, chart, chat, companies, reports, sessions, usage

__all__ = ["analysis", "auth", "cache", "chart", "chat", "companies", "reports", "sessions", "usage"]
