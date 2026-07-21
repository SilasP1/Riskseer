"""Copy a bundled Riskseer fixture into the live data input directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


FILES = (
    "events.csv",
    "tickets.csv",
    "assets.csv",
    "field_reports.csv",
    "markings.csv",
    "positive_responses.csv",
)


def load_dataset(name: str) -> list[str]:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    fixture_root = (data_dir / "test_data").resolve()
    source_dir = (fixture_root / name).resolve()
    if fixture_root not in source_dir.parents or not source_dir.is_dir():
        raise SystemExit(f"Dataset not found: {name}")

    copied: list[str] = []
    for filename in FILES:
        source = source_dir / filename
        destination = data_dir / filename
        if source.is_file():
            shutil.copy2(source, destination)
            copied.append(filename)
            continue

        if filename in FILES[:3]:
            raise SystemExit(f"Required fixture file is missing: {source}")

        if destination.is_file():
            header = destination.read_text(encoding="utf-8-sig").splitlines()[:1]
            destination.write_text((header[0] + "\n") if header else "", encoding="utf-8")

    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", default="demo_three_cases")
    args = parser.parse_args()
    copied = load_dataset(args.dataset)
    print(f"Loaded {args.dataset}: {', '.join(copied)}")


if __name__ == "__main__":
    main()
