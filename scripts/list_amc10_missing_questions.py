#!/usr/bin/env python3
"""List missing AMC 10 question numbers by contest."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    db_path = root / "amc10_practice.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT contest_id, contest_label, question_count
            FROM amc10_contests
            ORDER BY year, contest_label
            """
        )
        rows = cursor.fetchall()
        for row in rows:
            contest_id = row["contest_id"]
            cursor.execute(
                """
                SELECT problem_number
                FROM amc10_questions
                WHERE contest_id = ?
                ORDER BY problem_number
                """,
                (contest_id,),
            )
            present = {result["problem_number"] for result in cursor.fetchall()}
            missing = [number for number in range(1, 26) if number not in present]
            if missing:
                print(f"{row['contest_label']}: missing {missing}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

