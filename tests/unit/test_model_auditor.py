"""Tests for the model auditor module.

Covers:
- Output schema validation (ModelAudit dataclass)
- _build_audit_prompt produces valid text
- _parse_audit_response handles valid and invalid JSON
- Graceful degradation on LLM failure
"""

import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub external dependencies before loading the module.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent / "src_george_researcher"
_SNAPSHOT = dict(sys.modules)


def _make_mod(name: str):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


def _make_pkg(name: str, path: str):
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [path]
        sys.modules[name] = pkg


def _load(file_path: Path, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub the LLM module
_llm_stub = types.ModuleType("src_george_researcher.llm")


@dataclass(frozen=True)
class _StubLLMResponse:
    content: str = ""
    model: str = "stub"
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


_llm_responses = []  # Mutable list so tests can inject responses


def _stub_call_llm(**kwargs):
    if _llm_responses:
        return _llm_responses.pop(0)
    return _StubLLMResponse(success=False, error="No stub response configured")


_llm_stub.call_llm = _stub_call_llm
_llm_stub.LLMResponse = _StubLLMResponse
sys.modules["src_george_researcher.llm"] = _llm_stub

# Stub circuit_breaker and pricing (transitive deps of llm)
_make_mod("src_george_researcher.pricing")
_make_mod("src_george_researcher.circuit_breaker")

# Load the module under test
_make_pkg("src_george_researcher", str(_ROOT))
_make_pkg("src_george_researcher.valuation", str(_ROOT / "valuation"))

_mod = _load(
    _ROOT / "valuation" / "model_auditor.py",
    "src_george_researcher.valuation.model_auditor",
)

# Grab references before restoring
ModelAudit = _mod.ModelAudit
AuditWarning = _mod.AuditWarning
DealRelevance = _mod.DealRelevance
EMPTY_AUDIT = _mod.EMPTY_AUDIT
_build_audit_prompt = _mod._build_audit_prompt
_parse_audit_response = _mod._parse_audit_response
_deterministic_checks = _mod._deterministic_checks
audit_valuation_model = _mod.audit_valuation_model

# Restore sys.modules
_added = set(sys.modules) - set(_SNAPSHOT)
for _key in _added:
    del sys.modules[_key]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _company_context():
    return {
        "ticker": "JNJ",
        "name": "Johnson & Johnson",
        "market_cap": 500e9,
        "sector": "Healthcare",
        "current_price": 155.0,
    }


def _valuation_results():
    return {
        "dcf": {
            "fair_value_per_share": 210.0,
            "current_price": 155.0,
            "enterprise_value": 450e9,
            "pv_terminal_value": 380e9,
            "wacc_components": {
                "wacc": 0.05,
                "risk_free_rate": 0.043,
                "beta": 0.7,
                "equity_risk_premium": 0.055,
                "cost_of_equity": 0.08,
                "weight_equity": 0.95,
            },
            "assumptions": {
                "terminal_growth_rate": 0.025,
            },
        },
        "scenarios": {
            "bull": {"result": {"fair_value_per_share": 280.0}, "probability": 0.25},
            "base": {"result": {"fair_value_per_share": 210.0}, "probability": 0.50},
            "bear": {"result": {"fair_value_per_share": 140.0}, "probability": 0.25},
            "weighted_fair_value": 210.0,
        },
        "precedents": {
            "deals": [
                {"acquirer": "BMS", "target": "Karuna", "premium_pct": 0.50, "ev_to_ebitda": None},
            ],
        },
        "conviction": {"rating": "BUY", "overall_score": 72, "confidence": 75},
    }


def _valid_audit_json():
    return json.dumps({
        "warnings": [
            {"severity": "warning", "section": "dcf", "message": "WACC of 5.0% appears low", "metric": "wacc"},
            {"severity": "critical", "section": "dcf", "message": "TV is 84% of EV", "metric": "tv_pct"},
        ],
        "section_commentary": {
            "dcf": "Terminal value dominates the valuation.",
            "precedents": "Biotech premiums not applicable.",
        },
        "precedent_relevance": [
            {"deal": "BMS/Karuna", "relevance": "low", "reason": "Pre-revenue biotech"},
        ],
        "assumption_notes": {
            "wacc": "CAPM with 4.3% Rf, 5.5% ERP, 0.7 beta.",
        },
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestModelAuditDataclass:
    def test_empty_audit_to_dict(self):
        d = EMPTY_AUDIT.to_dict()
        assert d["warnings"] == []
        assert d["section_commentary"] == {}
        assert d["precedent_relevance"] == []
        assert d["assumption_notes"] == {}

    def test_populated_audit_to_dict(self):
        audit = ModelAudit(
            warnings=[AuditWarning(severity="warning", section="dcf", message="Low WACC")],
            section_commentary={"dcf": "TV is high."},
            precedent_relevance=[DealRelevance(deal="A/B", relevance="low", reason="Not comparable")],
            assumption_notes={"wacc": "CAPM based."},
        )
        d = audit.to_dict()
        assert len(d["warnings"]) == 1
        assert d["warnings"][0]["severity"] == "warning"
        assert "dcf" in d["section_commentary"]
        assert len(d["precedent_relevance"]) == 1
        assert d["assumption_notes"]["wacc"] == "CAPM based."


class TestBuildAuditPrompt:
    def test_contains_company_info(self):
        prompt = _build_audit_prompt(_company_context(), _valuation_results())
        assert "JNJ" in prompt
        assert "Johnson & Johnson" in prompt
        assert "Healthcare" in prompt

    def test_contains_wacc(self):
        prompt = _build_audit_prompt(_company_context(), _valuation_results())
        assert "WACC" in prompt
        assert "5.0%" in prompt

    def test_contains_revenue_when_provided(self):
        ctx = _company_context()
        ctx["revenue"] = 94e9
        prompt = _build_audit_prompt(ctx, _valuation_results())
        assert "Revenue: $94.0B" in prompt

    def test_subject_revenue_in_precedents_section(self):
        ctx = _company_context()
        ctx["revenue"] = 94e9
        prompt = _build_audit_prompt(ctx, _valuation_results())
        assert "Subject company revenue" in prompt

    def test_handles_empty_results(self):
        prompt = _build_audit_prompt(_company_context(), {})
        assert "JNJ" in prompt


class TestParseAuditResponse:
    def test_valid_json(self):
        audit = _parse_audit_response(_valid_audit_json())
        assert len(audit.warnings) == 2
        assert audit.warnings[0].severity == "warning"
        assert "dcf" in audit.section_commentary
        assert len(audit.precedent_relevance) == 1
        assert audit.precedent_relevance[0].relevance == "low"

    def test_code_fenced_json(self):
        text = f"```json\n{_valid_audit_json()}\n```"
        audit = _parse_audit_response(text)
        assert len(audit.warnings) == 2

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_audit_response("this is not json")


class TestDeterministicChecks:
    """Deterministic threshold checks that run before the LLM call."""

    def test_low_wacc_warning(self):
        warnings = _deterministic_checks(_company_context(), _valuation_results())
        wacc_msgs = [w for w in warnings if w.metric == "wacc"]
        assert len(wacc_msgs) == 1
        assert wacc_msgs[0].severity == "warning"
        assert "5.0%" in wacc_msgs[0].message

    def test_critical_wacc_below_4_pct(self):
        results = _valuation_results()
        results["dcf"]["wacc_components"]["wacc"] = 0.03
        warnings = _deterministic_checks(_company_context(), results)
        wacc_msgs = [w for w in warnings if w.metric == "wacc"]
        assert len(wacc_msgs) == 1
        assert wacc_msgs[0].severity == "critical"

    def test_no_wacc_warning_in_normal_range(self):
        results = _valuation_results()
        results["dcf"]["wacc_components"]["wacc"] = 0.10
        warnings = _deterministic_checks(_company_context(), results)
        wacc_msgs = [w for w in warnings if w.metric == "wacc"]
        assert len(wacc_msgs) == 0

    def test_tv_pct_warning(self):
        """TV is 380B/450B = 84.4%, just under 85% threshold: no warning."""
        warnings = _deterministic_checks(_company_context(), _valuation_results())
        tv_msgs = [w for w in warnings if w.metric == "tv_pct"]
        assert len(tv_msgs) == 0

    def test_tv_pct_warning_above_85(self):
        results = _valuation_results()
        results["dcf"]["pv_terminal_value"] = 400e9  # 400/450 = 88.9%
        warnings = _deterministic_checks(_company_context(), results)
        tv_msgs = [w for w in warnings if w.metric == "tv_pct"]
        assert len(tv_msgs) == 1
        assert tv_msgs[0].severity == "warning"

    def test_tv_pct_critical_above_95(self):
        results = _valuation_results()
        results["dcf"]["pv_terminal_value"] = 440e9  # 440/450 = 97.8%
        warnings = _deterministic_checks(_company_context(), results)
        tv_msgs = [w for w in warnings if w.metric == "tv_pct"]
        assert len(tv_msgs) == 1
        assert tv_msgs[0].severity == "critical"

    def test_fair_value_extreme_ratio(self):
        results = _valuation_results()
        results["dcf"]["fair_value_per_share"] = 1000.0  # 1000/155 = 6.5x
        warnings = _deterministic_checks(_company_context(), results)
        fv_msgs = [w for w in warnings if w.metric == "fair_value"]
        assert len(fv_msgs) == 1

    def test_low_equity_weight(self):
        results = _valuation_results()
        results["dcf"]["wacc_components"]["weight_equity"] = 0.05
        warnings = _deterministic_checks(_company_context(), results)
        eq_msgs = [w for w in warnings if w.metric == "weight_equity"]
        assert len(eq_msgs) == 1

    def test_empty_dcf_produces_no_warnings(self):
        warnings = _deterministic_checks(_company_context(), {})
        assert warnings == []


class TestAuditValuationModel:
    def test_deterministic_warnings_on_llm_failure(self):
        """On LLM failure, deterministic warnings are still returned."""
        _llm_responses.clear()
        audit = audit_valuation_model(
            company_context=_company_context(),
            valuation_results=_valuation_results(),
            api_key="test",
            model="test",
        )
        # Fixture has WACC=5% which triggers a deterministic warning
        assert len(audit.warnings) >= 1
        assert any(w.metric == "wacc" for w in audit.warnings)
        assert audit.section_commentary == {}

    def test_merges_deterministic_and_llm_warnings(self):
        _llm_responses.clear()
        _llm_responses.append(_StubLLMResponse(
            content=_valid_audit_json(),
            success=True,
        ))
        audit = audit_valuation_model(
            company_context=_company_context(),
            valuation_results=_valuation_results(),
            api_key="test",
            model="test",
        )
        # Deterministic WACC warning + 2 LLM warnings = at least 3
        assert len(audit.warnings) >= 3
        assert "dcf" in audit.section_commentary
