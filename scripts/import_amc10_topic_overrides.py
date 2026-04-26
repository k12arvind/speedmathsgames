#!/usr/bin/env python3
"""Import manual AMC 10 topic overrides from the review CSV."""

from __future__ import annotations

import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amc10.db import AMC10Database


def main() -> None:
    csv_path = ROOT / "amc10_topic_review.csv"
    db = AMC10Database(str(ROOT / "amc10_practice.db"))
    updates = 0

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            topic_code = (row.get("override_topic_code") or "").strip()
            topic_name = (row.get("override_topic_name") or "").strip()
            if not topic_code or not topic_name:
                continue
            db.set_manual_override(
                question_id=int(row["question_id"]),
                topic_code=topic_code,
                topic_name=topic_name,
                subtopic_code=(row.get("override_subtopic_code") or "").strip() or None,
                subtopic_name=(row.get("override_subtopic_name") or "").strip() or None,
                reasoning=(row.get("override_reasoning") or "").strip() or "Imported from review CSV.",
            )
            updates += 1

    print(f"Applied {updates} manual overrides from {csv_path}")


if __name__ == "__main__":
    main()
