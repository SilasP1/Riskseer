from __future__ import annotations

import pytest

from investigator import (
    InvalidInvestigation,
    InvestigationDraft,
    build_agent,
    build_evidence_catalog,
    finalize_brief,
)


@pytest.fixture
def case():
    return {
        "case_id": "00002",
        "decision_state": "PROCEED_WITH_VERIFICATION",
        "urgency": "HIGH",
        "response_posture": "VERIFY_BEFORE_PROCEEDING",
        "operator_summary": "Pause and verify.",
        "event_ids": ["E-1"],
        "observations": [{"summary": "Activity observed", "event_id": "E-1"}],
        "evidence_layers": {
            "observed": [{"statement": "One event was observed", "source_ids": ["E-1"]}],
            "derived": [{"statement": "Ticket support is incomplete", "source_ids": ["E-1"]}],
            "inferred": [],
            "assumed": [],
        },
        "temporal_change": {"trend": "WORSENING"},
    }


def test_catalog_keeps_evidence_layers_distinct(case):
    catalog = build_evidence_catalog(case)
    assert catalog["OBSERVED-1"]["kind"] == "OBSERVED"
    assert catalog["DERIVED-1"]["kind"] == "DERIVED"
    assert catalog["BACKEND-DECISION"]["kind"] == "BACKEND_TRUTH"


def test_final_brief_copies_backend_truth_and_accepts_valid_citations(case):
    draft = InvestigationDraft(
        summary="Support is incomplete, so verify before proceeding.",
        what_looks_normal=[{"statement": "Activity is documented", "citation_ids": ["OBSERVED-1"]}],
        weak_support=[{"statement": "Ticket support is incomplete", "citation_ids": ["DERIVED-1"]}],
        unknowns=[],
        why_it_matters_now=[{"statement": "The trend is worsening", "citation_ids": ["BACKEND-TEMPORAL"]}],
        recommended_checks=[{"statement": "Verify the ticket basis", "citation_ids": ["BACKEND-DECISION"]}],
    )
    brief = finalize_brief(case, draft, model="test-model")
    assert brief.backend_decision_state == case["decision_state"]
    assert brief.backend_response_posture == case["response_posture"]


def test_final_brief_rejects_invented_citations(case):
    draft = InvestigationDraft(
        summary="Bad citation",
        weak_support=[{"statement": "Unsupported", "citation_ids": ["MADE-UP-9"]}],
    )
    with pytest.raises(InvalidInvestigation, match="not in this case"):
        finalize_brief(case, draft, model="test-model")


def test_agent_has_bounded_tools_and_structured_output(case):
    agent = build_agent(case, "gpt-5.6")
    assert agent.output_type is not None
    assert len(agent.tools) == 3
