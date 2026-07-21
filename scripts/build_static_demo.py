"""Build the normalized three-case payload used by the GitHub Pages demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api  # noqa: E402
import main  # noqa: E402


FIXTURE = ROOT / "data" / "test_data" / "demo_three_cases"
OUTPUT = ROOT / "Riskseer Frontend" / "public" / "demo_cases.json"


def optional_loader(loader, filename: str):
    path = FIXTURE / filename
    return loader(path) if path.exists() else []


def build_payload() -> dict:
    cases, _ = main.run_pipeline(
        events=main.load_events(FIXTURE / "events.csv"),
        tickets=main.load_tickets(FIXTURE / "tickets.csv"),
        assets=main.load_assets(FIXTURE / "assets.csv"),
        field_reports=optional_loader(main.load_field_reports, "field_reports.csv"),
        markings=optional_loader(main.load_markings, "markings.csv"),
        positive_responses=optional_loader(
            main.load_positive_responses,
            "positive_responses.csv",
        ),
    )
    normalized = [api.normalize_case(main.dataclass_to_plain(case)) for case in cases]
    return {"case_count": len(normalized), "cases": normalized, "demo_mode": True}


def main_entry() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_payload(), indent=2), encoding="utf-8")
    print(f"Wrote static demo payload to {OUTPUT}")


if __name__ == "__main__":
    main_entry()
