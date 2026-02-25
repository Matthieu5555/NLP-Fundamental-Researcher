"""Smoke tests that verify all modules can be imported without errors.

These tests would have caught:
- The USFullAnalysis dataclass field ordering bug
- The swot/strategy SectionType mismatch
- Any broken import chains or missing dependencies
"""

import importlib
import pytest


class TestBackendCoreImports:
    """Verify all backend.core modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.core.auth",
        "backend.core.auth_db",
        "backend.core.base_db",
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
        pytest.param("backend.core.pdf_generator_v2", marks=pytest.mark.skipif(
            not __import__("os").environ.get("DYLD_LIBRARY_PATH"),
            reason="WeasyPrint requires DYLD_LIBRARY_PATH set for pango/gobject libraries"
        )),
        "backend.core.rag_engine",
        "backend.core.report_builder",
        "backend.core.report_editor",
        "backend.core.report_rag",
        "backend.core.report_updater",
        "backend.core.session",
        "backend.core.settings_db",
        "backend.core.usage_db",
        "backend.core.watchlist_db",
    ])
    def test_import_core_module(self, module):
        importlib.import_module(module)


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


class TestBackendMiddlewareImports:
    """Verify all backend.middleware modules import cleanly."""

    @pytest.mark.parametrize("module", [
        "backend.middleware.auth_middleware",
        "backend.middleware.usage_tracker",
    ])
    def test_import_middleware_module(self, module):
        importlib.import_module(module)


class TestBackendMainImport:
    """Verify the FastAPI app itself can be imported."""

    def test_import_main(self):
        importlib.import_module("backend.main")

    def test_app_object_exists(self):
        main = importlib.import_module("backend.main")
        assert hasattr(main, "app"), "backend.main must export 'app'"
