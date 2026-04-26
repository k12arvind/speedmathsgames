"""AMC 10 PDF parser and importer."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import fitz

from amc10.db import AMC10Database
from amc10.topics import classify_question


QUESTION_START_RE = re.compile(r"(?m)^\s*[,;:.\-]?\s*(?P<num>(?:[1-9]|1\d|2[0-5]))(?:[.,:]|\s)\s*")
SOLUTION_START_RE = re.compile(r"(?m)^\s*[,;:.\-]?\s*(?:Problem\s+)?(?P<num>(?:[1-9]|1\d|2[0-5]))\s*(?:[.,:]|\s)")
ANSWER_RE = re.compile(r"Answer\s*\(([A-E])\)\s*:")
CHOICE_MARKER_RE = re.compile(r"\(([A-E])\)")
PLAIN_CHOICE_MARKER_RE = re.compile(r"(?m)^\s*([A-E])(?:[\).:]|\s)\s+")


@dataclass(frozen=True)
class ContestMetadata:
    year: int
    season: Optional[str]
    contest_code: Optional[str]
    contest_label: str
    problems_pdf_path: str
    solutions_pdf_path: str


def _normalize_text(text: str) -> str:
    text = text.replace("\x0c", " ").replace("\u00ad", "")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_page_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if re.match(r"^\d{4}\s+AMC\s+10.*(Problems|Solutions)\s+\d+$", line):
            continue
        if re.match(r"^(First\s+AMC\s+10|Solutions\s+\d{4}\s+AMC\s+10)\s+\d+$", line):
            continue
        if re.match(r"^(MAA American Mathematics Competitions|American Mathematics Competitions)$", line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _looks_like_admin_page(text: str) -> bool:
    lower = text.lower()
    admin_markers = (
        "write to us",
        "publications",
        "order total",
        "teacher's manual",
        "administration on an earlier date",
        "please read the manual",
        "priority mail",
        "invoice will be sent",
        "publication orders",
    )
    return any(marker in lower for marker in admin_markers)


def _ocr_page(page: fitz.Page, columns: int = 1) -> str:
    rect = page.rect
    clips = [rect]
    if columns == 2:
        midpoint = rect.width / 2
        clips = [
            fitz.Rect(rect.x0, rect.y0, midpoint, rect.y1),
            fitz.Rect(midpoint, rect.y0, rect.x1, rect.y1),
        ]

    outputs = []
    for clip in clips:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            pix.save(str(temp_path))
            result = subprocess.run(
                ["/usr/local/bin/tesseract", str(temp_path), "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                check=False,
            )
            outputs.append(result.stdout)
        finally:
            temp_path.unlink(missing_ok=True)

    return "\n".join(output.strip() for output in outputs if output.strip())


def _extract_pages(pdf_path: Path, document_type: str) -> List[str]:
    doc = fitz.open(str(pdf_path))
    pages: List[str] = []
    for page in doc:
        text = page.get_text("text")
        if len(text.strip()) < 40:
            columns = 2 if document_type == "problems" else 1
            text = _ocr_page(page, columns=columns)
        cleaned = _clean_page_text(text)
        if _looks_like_admin_page(cleaned) and cleaned.count("?") < 2 and "Answer (" not in cleaned:
            cleaned = ""
        pages.append(cleaned)
    return pages


def _parse_problem_metadata(pdf_path: Path) -> ContestMetadata:
    stem = pdf_path.stem
    if not stem.endswith("_Problems"):
        raise ValueError(f"Expected a problems PDF, got {pdf_path.name}")

    parts = stem.split("_")
    year = int(parts[0])
    season = None
    contest_code = None
    if len(parts) >= 5 and parts[1] in {"Spring", "Fall"}:
        season = parts[1]
        contest_code = parts[4]
    elif len(parts) >= 4 and parts[2] == "Contest":
        contest_code = parts[3]

    label_parts = [str(year)]
    if season:
        label_parts.append(season)
    if contest_code:
        label_parts.append(f"Contest {contest_code}")
    else:
        label_parts.append("Main")

    solutions_pdf_path = str(pdf_path).replace("_Problems.pdf", "_Solutions.pdf")
    return ContestMetadata(
        year=year,
        season=season,
        contest_code=contest_code,
        contest_label=" ".join(label_parts),
        problems_pdf_path=str(pdf_path),
        solutions_pdf_path=solutions_pdf_path,
    )


def _build_text_with_pages(pages: Iterable[str], document_type: str) -> str:
    chunks = []
    for index, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue
        chunks.append(f"\n[[PAGE:{index}]]\n{page_text}\n")
    return "".join(chunks)


def _find_choice_markers(content: str) -> List[re.Match[str]]:
    parenthetical = list(CHOICE_MARKER_RE.finditer(content))
    if len(parenthetical) >= 5:
        return parenthetical[:5]
    plain = list(PLAIN_CHOICE_MARKER_RE.finditer(content))
    if len(plain) >= 5:
        return plain[:5]
    return parenthetical[:5] if parenthetical else plain[:5]


def _parse_question_block(number: int, block: str, page_start: Optional[int], page_end: Optional[int]) -> Dict[str, object]:
    content = QUESTION_START_RE.sub("", block, count=1).strip()
    option_matches = _find_choice_markers(content)
    parse_status = "parsed"
    parse_notes = None
    choices = {"A": None, "B": None, "C": None, "D": None, "E": None}

    if len(option_matches) >= 5:
        question_text = content[:option_matches[0].start()].strip()
        for opt_index, option_match in enumerate(option_matches):
            label = option_match.group(1)
            choice_end = option_matches[opt_index + 1].start() if opt_index + 1 < len(option_matches) else len(content)
            choices[label] = content[option_match.end():choice_end].strip()
    else:
        question_text = content
        parse_status = "needs_review"
        parse_notes = f"Expected 5 answer choices, found {len(option_matches)}."

    return {
        "problem_number": number,
        "question_text": _normalize_text(question_text),
        "question_text_raw": block,
        "choice_a": _normalize_text(choices["A"] or ""),
        "choice_b": _normalize_text(choices["B"] or ""),
        "choice_c": _normalize_text(choices["C"] or ""),
        "choice_d": _normalize_text(choices["D"] or ""),
        "choice_e": _normalize_text(choices["E"] or ""),
        "problem_page_start": page_start,
        "problem_page_end": page_end,
        "parse_status": parse_status,
        "parse_notes": parse_notes,
    }


def _page_for_offset(text: str, offset: int) -> Optional[int]:
    page = None
    for match in re.finditer(r"\[\[PAGE:(\d+)]]", text):
        if match.start() <= offset:
            page = int(match.group(1))
        else:
            break
    return page


def _split_questions(problem_text: str) -> List[Dict[str, object]]:
    matches = list(QUESTION_START_RE.finditer(problem_text))
    candidates = []
    for idx, match in enumerate(matches):
        number = int(match.group("num"))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(problem_text)
        block = problem_text[match.start():end].strip()
        page_start = _page_for_offset(problem_text, match.start())
        page_end = _page_for_offset(problem_text, max(match.start(), end - 1))
        candidates.append(_parse_question_block(number, block, page_start, page_end))

    best_by_number: Dict[int, Dict[str, object]] = {}
    for candidate in candidates:
        number = int(candidate["problem_number"])
        if not 1 <= number <= 25:
            continue
        choice_count = sum(1 for key in ("choice_a", "choice_b", "choice_c", "choice_d", "choice_e") if candidate.get(key))
        score = choice_count * 100 + len(candidate.get("question_text", ""))
        previous = best_by_number.get(number)
        if previous is None:
            best_by_number[number] = candidate
            continue
        previous_choice_count = sum(1 for key in ("choice_a", "choice_b", "choice_c", "choice_d", "choice_e") if previous.get(key))
        previous_score = previous_choice_count * 100 + len(previous.get("question_text", ""))
        if score > previous_score:
            best_by_number[number] = candidate

    return [best_by_number[number] for number in sorted(best_by_number)]


def _split_solutions(solution_text: str) -> Dict[int, Dict[str, object]]:
    matches = list(SOLUTION_START_RE.finditer(solution_text))
    candidates: Dict[int, List[Dict[str, object]]] = {}
    for idx, match in enumerate(matches):
        number = int(match.group("num"))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(solution_text)
        block = solution_text[match.start():end].strip()
        answer_match = ANSWER_RE.search(block)
        page_start = _page_for_offset(solution_text, match.start())
        page_end = _page_for_offset(solution_text, max(match.start(), end - 1))
        if answer_match:
            correct_choice = answer_match.group(1)
            prompt_block = block[:answer_match.start()].strip()
            solution_body = block[answer_match.end():].strip()
            parse_status = "parsed"
            parse_notes = None
        else:
            correct_choice = None
            prompt_block = block
            solution_body = block
            parse_status = "needs_review"
            parse_notes = "Could not locate official answer marker."

        candidates.setdefault(number, []).append(
            {
                "correct_choice": correct_choice,
                "prompt_block": prompt_block,
                "official_solution": _normalize_text(solution_body),
                "official_solution_raw": block,
                "solution_page_start": page_start,
                "solution_page_end": page_end,
                "solution_parse_status": parse_status,
                "solution_parse_notes": parse_notes,
            }
        )

    results: Dict[int, Dict[str, object]] = {}
    for number, blocks in candidates.items():
        if not 1 <= number <= 25:
            continue
        blocks.sort(key=lambda item: (1 if item.get("correct_choice") else 0, len(item.get("official_solution", ""))), reverse=True)
        results[number] = blocks[0]

    return results


def parse_contest(problem_pdf_path: Path) -> Tuple[ContestMetadata, List[Dict[str, object]]]:
    metadata = _parse_problem_metadata(problem_pdf_path)
    solution_pdf_path = Path(metadata.solutions_pdf_path)
    if not solution_pdf_path.exists():
        raise FileNotFoundError(f"Missing solutions PDF for {problem_pdf_path.name}")

    problem_pages = _extract_pages(problem_pdf_path, document_type="problems")
    solution_pages = _extract_pages(solution_pdf_path, document_type="solutions")

    problem_text = _build_text_with_pages(problem_pages, document_type="problems")
    solution_text = _build_text_with_pages(solution_pages, document_type="solutions")

    questions = _split_questions(problem_text)
    solutions = _split_solutions(solution_text)

    merged = []
    question_map = {question["problem_number"]: question for question in questions}
    for question in questions:
        solution = solutions.get(question["problem_number"], {})
        combined_statuses = {question.get("parse_status"), solution.get("solution_parse_status")}
        parse_status = "parsed" if combined_statuses == {"parsed"} else "needs_review"
        parse_notes = "; ".join(
            note for note in (question.get("parse_notes"), solution.get("solution_parse_notes")) if note
        ) or None

        merged_question = {
            **question,
            "correct_choice": solution.get("correct_choice"),
            "official_solution": solution.get("official_solution"),
            "official_solution_raw": solution.get("official_solution_raw"),
            "solution_page_start": solution.get("solution_page_start"),
            "solution_page_end": solution.get("solution_page_end"),
            "parse_status": parse_status,
            "parse_notes": parse_notes,
        }
        merged.append(merged_question)

    for number, solution in sorted(solutions.items()):
        if number in question_map:
            continue
        fallback_question = _parse_question_block(
            number=number,
            block=solution.get("prompt_block") or solution.get("official_solution_raw") or "",
            page_start=solution.get("solution_page_start"),
            page_end=solution.get("solution_page_end"),
        )
        fallback_question.update(
            {
                "correct_choice": solution.get("correct_choice"),
                "official_solution": solution.get("official_solution"),
                "official_solution_raw": solution.get("official_solution_raw"),
                "solution_page_start": solution.get("solution_page_start"),
                "solution_page_end": solution.get("solution_page_end"),
                "parse_status": "fallback_from_solution",
                "parse_notes": "Problem statement reconstructed from official solution pamphlet.",
            }
        )
        merged.append(fallback_question)

    merged.sort(key=lambda item: item["problem_number"])

    return metadata, merged


def import_amc10_folder(folder: Path, db: AMC10Database) -> Dict[str, int]:
    problem_pdfs = sorted(folder.glob("*_Problems.pdf"))
    contests_imported = 0
    questions_imported = 0

    for problem_pdf in problem_pdfs:
        metadata, questions = parse_contest(problem_pdf)
        contest_id = db.upsert_contest(
            {
                "year": metadata.year,
                "season": metadata.season,
                "contest_code": metadata.contest_code,
                "contest_label": metadata.contest_label,
                "problems_pdf_path": metadata.problems_pdf_path,
                "solutions_pdf_path": metadata.solutions_pdf_path,
                "import_status": "parsed",
                "question_count": len(questions),
            }
        )
        db.replace_contest_questions(contest_id, questions)

        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT question_id, question_text, official_solution
                FROM amc10_questions
                WHERE contest_id = ?
                ORDER BY problem_number
                """,
                (contest_id,),
            )
            topic_rows = []
            for row in cursor.fetchall():
                classified = classify_question(row["question_text"], row["official_solution"] or "")
                topic_rows.append({"question_id": row["question_id"], **classified})
        finally:
            conn.close()

        db.replace_auto_tags(contest_id, topic_rows)
        contests_imported += 1
        questions_imported += len(questions)

    return {"contests_imported": contests_imported, "questions_imported": questions_imported}
