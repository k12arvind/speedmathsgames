"""AMC 10 topic taxonomy and rule-based auto-tagging."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class TopicRule:
    topic_code: str
    topic_name: str
    subtopic_code: str
    subtopic_name: str
    patterns: Tuple[str, ...]
    weight: int


TOPIC_RULES: Tuple[TopicRule, ...] = (
    TopicRule("geometry", "Geometry", "triangles", "Triangles", (r"\btriangle\b", r"\btriangles\b", r"\bequilateral\b", r"\bisosceles\b", r"\bright triangle\b"), 5),
    TopicRule("geometry", "Geometry", "circles", "Circles", (r"\bcircle\b", r"\bradius\b", r"\bdiameter\b", r"\bcircumference\b", r"\barc\b", r"\bchord\b", r"\btangent\b"), 5),
    TopicRule("geometry", "Geometry", "polygons", "Polygons", (r"\bsquare\b", r"\brectangle\b", r"\bparallelogram\b", r"\btrapezoid\b", r"\bhexagon\b", r"\bpentagon\b", r"\bpolygon\b", r"\bregular\b"), 4),
    TopicRule("geometry", "Geometry", "coordinate_geometry", "Coordinate Geometry", (r"\bcoordinate\b", r"\bgrid\b", r"\bxy-plane\b", r"\bpoint[s]?\s+[A-Z]", r"\bslope\b", r"\bline segment\b"), 4),
    TopicRule("geometry", "Geometry", "solid_geometry", "Solid Geometry", (r"\bcube\b", r"\bprism\b", r"\bcylinder\b", r"\bsphere\b", r"\bvolume\b", r"\bsurface area\b"), 5),
    TopicRule("geometry", "Geometry", "angles", "Angles", (r"\bangle\b", r"\bperpendicular\b", r"\bparallel\b"), 3),
    TopicRule("algebra", "Algebra", "linear_equations", "Linear Equations", (r"\bsolve\b", r"\bequation\b", r"\babsolute value\b", r"\baverage\b", r"\bsum of three numbers\b"), 3),
    TopicRule("algebra", "Algebra", "polynomials", "Polynomials", (r"\bpolynomial\b", r"\bquadratic\b", r"\bcubic\b", r"\broot[s]?\b", r"\bzero[s]?\b", r"\bfactor\b"), 5),
    TopicRule("algebra", "Algebra", "functions", "Functions", (r"\bf\(", r"\bg\(", r"\bfunction\b", r"\bcomposition\b"), 5),
    TopicRule("algebra", "Algebra", "sequences_series", "Sequences and Series", (r"\bsequence\b", r"\bseries\b", r"\barithmetic\b", r"\bgeometric\b", r"\bfibonacci\b"), 5),
    TopicRule("algebra", "Algebra", "inequalities", "Inequalities", (r"\binequalit", r"\bmaximum\b", r"\bminimum\b", r"\bleast\b", r"\bgreatest\b"), 3),
    TopicRule("algebra", "Algebra", "radicals_exponents", "Radicals and Exponents", (r"\bsquare root\b", r"\bcube root\b", r"\bexponent\b", r"\bpower\b", r"\bradical\b"), 4),
    TopicRule("number_theory", "Number Theory", "divisibility", "Divisibility", (r"\bdivisible\b", r"\bmultiple\b", r"\bfactor\b", r"\bdivisor\b", r"\bremainder\b", r"\bmod\b"), 5),
    TopicRule("number_theory", "Number Theory", "primes", "Primes", (r"\bprime\b", r"\bcomposite\b", r"\bgcd\b", r"\bgreatest common divisor\b", r"\blcm\b", r"\bleast common multiple\b"), 5),
    TopicRule("number_theory", "Number Theory", "digits_bases", "Digits and Bases", (r"\bdigit\b", r"\bdigits\b", r"\bbase\b", r"\bdecimal\b", r"\bunits position\b"), 5),
    TopicRule("counting_probability", "Counting and Probability", "counting", "Counting", (r"\bhow many\b", r"\barrangement\b", r"\bpermutation\b", r"\bcombination\b", r"\bsubset\b", r"\bchoose\b"), 5),
    TopicRule("counting_probability", "Counting and Probability", "probability", "Probability", (r"\bprobability\b", r"\brandom\b", r"\bwithout replacement\b", r"\bwith replacement\b"), 5),
    TopicRule("counting_probability", "Counting and Probability", "combinatorics", "Combinatorics", (r"\bcoloring\b", r"\bpaths\b", r"\bcommittee\b", r"\bcase[s]?\b"), 4),
    TopicRule("logic_misc", "Logic and Miscellaneous", "logic", "Logic", (r"\btruth\b", r"\bliar\b", r"\balternat", r"\balways lie\b", r"\balways tell the truth\b"), 6),
    TopicRule("logic_misc", "Logic and Miscellaneous", "rates_word_problems", "Rates and Word Problems", (r"\bmiles per\b", r"\blaps\b", r"\bspeed\b", r"\brate\b", r"\bminutes\b", r"\bhour\b"), 3),
)


TOPIC_LOOKUP = {
    "geometry": "Geometry",
    "algebra": "Algebra",
    "number_theory": "Number Theory",
    "counting_probability": "Counting and Probability",
    "logic_misc": "Logic and Miscellaneous",
}


def _normalize_text(parts: Iterable[str]) -> str:
    combined = " ".join(part for part in parts if part)
    return re.sub(r"\s+", " ", combined).strip().lower()


def classify_question(question_text: str, solution_text: str) -> dict:
    """Return a reviewable auto-topic tag for a question."""
    haystack = _normalize_text((question_text, solution_text))
    if not haystack:
        return {
            "topic_code": "logic_misc",
            "topic_name": TOPIC_LOOKUP["logic_misc"],
            "subtopic_code": "unclassified",
            "subtopic_name": "Unclassified",
            "confidence": 0.1,
            "reasoning": "No extracted text was available for auto-tagging.",
        }

    scored: List[tuple[int, TopicRule, List[str]]] = []
    for rule in TOPIC_RULES:
        matched = [pattern for pattern in rule.patterns if re.search(pattern, haystack, re.IGNORECASE)]
        if matched:
            score = rule.weight * len(matched)
            scored.append((score, rule, matched))

    if not scored:
        return {
            "topic_code": "logic_misc",
            "topic_name": TOPIC_LOOKUP["logic_misc"],
            "subtopic_code": "unclassified",
            "subtopic_name": "Unclassified",
            "confidence": 0.2,
            "reasoning": "No topic rules matched, so this question needs manual review.",
        }

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_rule, matched = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    margin = best_score - second_score

    if best_score >= 8 and margin >= 4:
        confidence = 0.9
    elif best_score >= 5 and margin >= 2:
        confidence = 0.75
    elif best_score >= 4:
        confidence = 0.6
    else:
        confidence = 0.45

    snippets = ", ".join(matched[:3])
    return {
        "topic_code": best_rule.topic_code,
        "topic_name": best_rule.topic_name,
        "subtopic_code": best_rule.subtopic_code,
        "subtopic_name": best_rule.subtopic_name,
        "confidence": confidence,
        "reasoning": f"Matched topic rules: {snippets}",
    }

