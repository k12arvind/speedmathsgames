#!/usr/bin/env python3
"""Export AMC 10 questions and topic tags for manual review."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    db_path = root / "amc10_practice.db"
    output_path = root / "amc10_topic_review.csv"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                q.question_id,
                c.contest_label,
                c.year,
                c.season,
                c.contest_code,
                q.problem_number,
                q.question_text,
                q.correct_choice,
                q.official_solution,
                q.parse_status,
                q.parse_notes,
                t.topic_code,
                t.topic_name,
                t.subtopic_code,
                t.subtopic_name,
                t.confidence,
                t.reasoning,
                t.tag_source
            FROM amc10_questions q
            JOIN amc10_contests c ON c.contest_id = q.contest_id
            LEFT JOIN amc10_question_topics t
              ON t.question_id = q.question_id
             AND t.is_active = 1
             AND t.is_primary = 1
            ORDER BY c.year, c.contest_label, q.problem_number
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    fieldnames = [
        "question_id",
        "contest_label",
        "year",
        "season",
        "contest_code",
        "problem_number",
        "question_text",
        "correct_choice",
        "official_solution",
        "parse_status",
        "parse_notes",
        "current_topic_code",
        "current_topic_name",
        "current_subtopic_code",
        "current_subtopic_name",
        "confidence",
        "reasoning",
        "tag_source",
        "override_topic_code",
        "override_topic_name",
        "override_subtopic_code",
        "override_subtopic_name",
        "override_reasoning",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "question_id": row["question_id"],
                    "contest_label": row["contest_label"],
                    "year": row["year"],
                    "season": row["season"],
                    "contest_code": row["contest_code"],
                    "problem_number": row["problem_number"],
                    "question_text": row["question_text"],
                    "correct_choice": row["correct_choice"],
                    "official_solution": row["official_solution"],
                    "parse_status": row["parse_status"],
                    "parse_notes": row["parse_notes"],
                    "current_topic_code": row["topic_code"],
                    "current_topic_name": row["topic_name"],
                    "current_subtopic_code": row["subtopic_code"],
                    "current_subtopic_name": row["subtopic_name"],
                    "confidence": row["confidence"],
                    "reasoning": row["reasoning"],
                    "tag_source": row["tag_source"],
                    "override_topic_code": "",
                    "override_topic_name": "",
                    "override_subtopic_code": "",
                    "override_subtopic_name": "",
                    "override_reasoning": "",
                }
            )

    print(output_path)


if __name__ == "__main__":
    main()

