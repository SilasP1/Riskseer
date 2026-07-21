"""Bounded OpenAI investigator for already-evaluated Riskseer cases.

The deterministic backend owns case identity, evidence, decision state,
urgency, and posture. This module only produces a cited operator brief from
that saved truth and rejects citations that are not in the case catalog.
"""

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DEFAULT_MODEL = "gpt-5.6"


class InvestigatorUnavailable(RuntimeError):
    pass


class InvalidInvestigation(RuntimeError):
    pass


class CitedFinding(BaseModel):
    statement: str = Field(description="A concise statement grounded in the case record")
    citation_ids: List[str] = Field(description="One or more citation IDs returned by the tools")


class InvestigationDraft(BaseModel):
    summary: str
    what_looks_normal: List[CitedFinding] = Field(default_factory=list)
    weak_support: List[CitedFinding] = Field(default_factory=list)
    unknowns: List[CitedFinding] = Field(default_factory=list)
    why_it_matters_now: List[CitedFinding] = Field(default_factory=list)
    recommended_checks: List[CitedFinding] = Field(default_factory=list)


class InvestigationBrief(InvestigationDraft):
    case_id: str
    backend_decision_state: str
    backend_urgency: str
    backend_response_posture: str
    model: str


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    raise InvalidInvestigation("Investigator returned an unsupported output type")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def build_evidence_catalog(case: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {
        "BACKEND-DECISION": {
            "kind": "BACKEND_TRUTH",
            "statement": (
                f"Decision {_text(case.get('decision_state'))}; urgency {_text(case.get('urgency'))}; "
                f"posture {_text(case.get('response_posture'))}"
            ),
            "source_ids": [],
        }
    }

    layers = case.get("evidence_layers") if isinstance(case.get("evidence_layers"), dict) else {}
    for layer_name in ("observed", "derived", "inferred", "assumed"):
        items = layers.get(layer_name) if isinstance(layers.get(layer_name), list) else []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            citation_id = f"{layer_name.upper()}-{index}"
            catalog[citation_id] = {
                "kind": layer_name.upper(),
                "statement": _text(item.get("statement")),
                "source_ids": list(item.get("source_ids") or []),
                "confidence": item.get("confidence"),
            }

    temporal = case.get("temporal_change")
    if isinstance(temporal, dict) and temporal:
        catalog["BACKEND-TEMPORAL"] = {
            "kind": "BACKEND_TRUTH",
            "statement": _text(temporal),
            "source_ids": list(case.get("event_ids") or []),
        }

    for index, observation in enumerate(case.get("observations") or [], start=1):
        if not isinstance(observation, dict):
            continue
        catalog[f"OBSERVATION-{index}"] = {
            "kind": "OBSERVED",
            "statement": _text(observation.get("summary") or observation.get("observation_type")),
            "source_ids": [
                source_id
                for source_id in (
                    observation.get("event_id"),
                    observation.get("ticket_id"),
                    observation.get("asset_id"),
                    observation.get("field_report_id"),
                    observation.get("marking_id"),
                    observation.get("response_id"),
                )
                if source_id
            ],
        }
    return catalog


def finalize_brief(
    case: Dict[str, Any],
    draft: InvestigationDraft | Dict[str, Any],
    *,
    model: str,
) -> InvestigationBrief:
    draft_data = _as_dict(draft)
    parsed = InvestigationDraft(**draft_data)
    catalog_ids = set(build_evidence_catalog(case))

    for section_name in (
        "what_looks_normal",
        "weak_support",
        "unknowns",
        "why_it_matters_now",
        "recommended_checks",
    ):
        for finding in getattr(parsed, section_name):
            if not finding.citation_ids:
                raise InvalidInvestigation(f"{section_name} contains an uncited statement")
            unknown = sorted(set(finding.citation_ids) - catalog_ids)
            if unknown:
                raise InvalidInvestigation(
                    f"{section_name} cites IDs that are not in this case: {', '.join(unknown)}"
                )

    return InvestigationBrief(
        **_as_dict(parsed),
        case_id=_text(case.get("case_id")),
        backend_decision_state=_text(case.get("decision_state")),
        backend_urgency=_text(case.get("urgency")),
        backend_response_posture=_text(case.get("response_posture")),
        model=model,
    )


def investigator_status() -> Dict[str, Any]:
    try:
        import agents  # noqa: F401
        sdk_available = True
    except ImportError:
        sdk_available = False
    return {
        "available": bool(os.getenv("OPENAI_API_KEY")) and sdk_available,
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "sdk_available": sdk_available,
        "model": os.getenv("RISKSEER_OPENAI_MODEL", DEFAULT_MODEL),
    }


def build_agent(case: Dict[str, Any], model: str) -> Any:
    try:
        from agents import Agent, function_tool
    except ImportError as exc:
        raise InvestigatorUnavailable(
            "OpenAI Agents SDK is not installed. Run: pip install -r requirements.txt"
        ) from exc

    catalog = build_evidence_catalog(case)

    @function_tool
    def get_case_decision() -> Dict[str, Any]:
        """Return immutable official Riskseer decision truth for this case."""
        return {
            "case_id": case.get("case_id"),
            "decision_state": case.get("decision_state"),
            "urgency": case.get("urgency"),
            "response_posture": case.get("response_posture"),
            "operator_summary": case.get("operator_summary"),
            "citation_id": "BACKEND-DECISION",
        }

    @function_tool
    def get_case_evidence(
        layer: Literal["observed", "derived", "inferred", "assumed", "all"] = "all",
    ) -> Dict[str, Any]:
        """Return bounded evidence with valid citation IDs, optionally by evidence layer."""
        wanted = layer.upper()
        return {
            citation_id: item
            for citation_id, item in catalog.items()
            if layer == "all" or item.get("kind") == wanted
        }

    @function_tool
    def get_case_change() -> Dict[str, Any]:
        """Return saved temporal change, why-now signals, and current recommended checks."""
        return {
            "temporal_change": case.get("temporal_change"),
            "why_now": case.get("why_now") or [],
            "recommended_actions": case.get("recommended_actions") or [],
            "citation_ids": [
                value for value in ("BACKEND-TEMPORAL", "BACKEND-DECISION") if value in catalog
            ],
        }

    return Agent(
        name="Riskseer Investigator",
        model=model,
        instructions=(
            "You investigate one already-evaluated excavation risk case. Use the tools before answering. "
            "Riskseer's backend decision, urgency, and posture are immutable; never replace or soften them. "
            "Separate observed, derived, inferred, and assumed material. Every finding and every recommended "
            "check must cite one or more citation IDs exactly as returned by a tool. Do not assign blame, make "
            "legal conclusions, or invent missing facts. Keep the brief concise and useful to an operator."
        ),
        tools=[get_case_decision, get_case_evidence, get_case_change],
        output_type=InvestigationDraft,
    )


async def investigate_case(
    case: Dict[str, Any],
    *,
    runner: Optional[Callable[..., Awaitable[Any]]] = None,
    model: Optional[str] = None,
) -> InvestigationBrief:
    if not os.getenv("OPENAI_API_KEY") and runner is None:
        raise InvestigatorUnavailable("OPENAI_API_KEY is not configured")

    selected_model = model or os.getenv("RISKSEER_OPENAI_MODEL", DEFAULT_MODEL)
    agent = build_agent(case, selected_model)
    prompt = (
        f"Investigate case {case.get('case_id')}. Explain what looks normal, what is weak or unknown, "
        "why it matters now, and the smallest useful checks. Preserve the official backend posture."
    )

    if runner is None:
        from agents import Runner
        result = await Runner.run(agent, input=prompt, max_turns=6)
    else:
        result = await runner(agent=agent, input=prompt, max_turns=6)

    output = getattr(result, "final_output", result)
    return finalize_brief(case, output, model=selected_model)
