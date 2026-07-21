from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parents[1]


def load_fixture(name: str):
    directory = ROOT / "data" / "test_data" / name
    return {
        "events": main.load_events(directory / "events.csv"),
        "tickets": main.load_tickets(directory / "tickets.csv"),
        "assets": main.load_assets(directory / "assets.csv"),
        "field_reports": main.load_field_reports(directory / "field_reports.csv")
        if (directory / "field_reports.csv").exists()
        else [],
        "markings": main.load_markings(directory / "markings.csv")
        if (directory / "markings.csv").exists()
        else [],
        "positive_responses": main.load_positive_responses(directory / "positive_responses.csv")
        if (directory / "positive_responses.csv").exists()
        else [],
    }


def trend_index(cases):
    payload = main.build_case_trend_history_payload(cases)
    return {
        key: case
        for case in payload["cases"]
        for key in case["trend_keys"]
    }


def test_three_case_decisions_are_coherent():
    cases, _ = main.run_pipeline(**load_fixture("demo_three_cases"))
    by_story = {case.event_ids[0].split("-")[1]: case for case in cases}

    assert len(cases) == 3
    assert by_story["A"].evaluation.decision_state.value == "SAFE_TO_PROCEED"
    assert by_story["A"].evaluation.response_posture.value == "MONITOR"
    assert by_story["B"].evaluation.decision_state.value == "PROCEED_WITH_VERIFICATION"
    assert by_story["B"].evaluation.response_posture.value == "VERIFY_BEFORE_PROCEEDING"
    assert by_story["B"].evaluation.responsibility_integrity.decision_support_integrity.state.value == "DEGRADED"
    assert by_story["C"].evaluation.decision_state.value == "STOP_WORK"
    assert by_story["C"].evaluation.response_posture.value == "HOLD_WORK"


def test_staged_fixture_preserves_three_case_threads_and_prior_snapshots():
    stage_one, _ = main.run_pipeline(**load_fixture("rim_rich/stage_01_baseline"))
    stage_two, matches = main.run_pipeline(
        **load_fixture("rim_rich/stage_02_evolution"),
        prior_cases=deepcopy(stage_one),
        prior_trend_index=trend_index(stage_one),
    )

    assert len(stage_one) == len(stage_two) == 3
    assert len(matches) == 3
    assert {case.case_id for case in stage_two} == {case.case_id for case in stage_one}
    assert all(len(case.event_ids) == 20 for case in stage_two)
    assert all(case.metadata.get("prior_state_snapshot") for case in stage_two)
    by_story = {case.event_ids[0].split("-")[1]: case for case in stage_two}
    assert by_story["B"].metadata["trend"] == "WORSENING"


def test_source_adaptor_contract_imports_and_preserves_unknowns():
    from source_adaptors import PositiveResponseAdaptor, SourceQuality

    result = PositiveResponseAdaptor().adapt({"response_id": "PR-1"})
    assert isinstance(result.quality, SourceQuality)
    assert result.records[0]["clear_to_excavate"] is None
    assert "observed_at" in result.quality.missing_fields


def test_static_pages_payload_uses_normalized_demo_cases():
    from scripts.build_static_demo import build_payload

    payload = build_payload()
    assert payload["case_count"] == 3
    by_decision = {case["decision_state"]: case for case in payload["cases"]}
    assert by_decision["SAFE_TO_PROCEED"]["response_posture"] == "MONITOR"
    assert (
        by_decision["PROCEED_WITH_VERIFICATION"]["response_posture"]
        == "VERIFY_BEFORE_PROCEEDING"
    )
    assert by_decision["STOP_WORK"]["response_posture"] == "HOLD_WORK"
