"""
Classify NSEJS questions into subject (physics/chemistry/biology/maths)
and (for physics) into a topic taxonomy. Uses the Anthropic API.

Reads:  nsejs_<paper>_raw.json  (one element from physics/nsejs/)
Writes: nsejs_<paper>_classified.json — same records plus
        { subject, subject_confidence, topic_code, topic_name,
          subtopic_code, subtopic_name, difficulty }

Topic taxonomy used (matches physics_question_topics conventions):

  topic_code         topic_name                  example subtopics
  ─────────────────  ──────────────────────────  ────────────────────────────
  mechanics          Mechanics                   kinematics, dynamics,
                                                 work-energy-power, gravitation,
                                                 fluids, elasticity
  thermal            Heat & Thermodynamics       temperature, calorimetry,
                                                 kinetic theory, laws
  waves              Waves & Sound               sound, superposition, doppler,
                                                 standing waves, oscillations
  optics             Optics                      reflection, refraction, lenses,
                                                 wave optics
  electricity        Electricity                 current, circuits, capacitance,
                                                 ohms-law
  magnetism          Magnetism                   magnetic-field, induction,
                                                 emi, motors
  modern             Modern Physics              atomic, nuclear, photoelectric,
                                                 quantum, relativity
  general            General                     anything that doesn't fit
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env if present (we keep ANTHROPIC_API_KEY there)
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from anthropic import Anthropic


CLASSIFY_MODEL = 'claude-sonnet-4-20250514'
TAXONOMY = {
    'mechanics':   'Mechanics',
    'thermal':     'Heat & Thermodynamics',
    'waves':       'Waves & Sound',
    'optics':      'Optics',
    'electricity': 'Electricity',
    'magnetism':   'Magnetism',
    'modern':      'Modern Physics',
    'general':     'General',
}


SYSTEM_PROMPT = """You are classifying NSEJS exam questions for a physics practice app.

For each question you will receive a record with:
  - number: the original question number in the paper
  - body: the question text (may reference figures we don't have)
  - choices: a/b/c/d
  - correct: the correct option letter (sometimes missing)
  - solution: a brief solution (sometimes missing)

Return one JSON object per question with these fields:
  {
    "number": <same number>,
    "subject": "physics" | "chemistry" | "biology" | "maths",
    "subject_confidence": "high" | "medium" | "low",
    "topic_code": one of [mechanics, thermal, waves, optics, electricity,
                          magnetism, modern, general],   // ONLY for physics
    "topic_name": human-readable form,                   // ONLY for physics
    "subtopic_code": short code, e.g. "kinematics", "circuits", "lenses",
    "subtopic_name": human-readable subtopic,
    "difficulty": "easy" | "medium" | "hard",            // your honest read
    "skip_reason": optional — set ONLY if the question is unanswerable
                   without a figure we don't have. Otherwise omit/null.
  }

Rules:
- Output ONLY a single JSON ARRAY of these objects, in the order received.
- For non-physics subjects you MAY omit topic_*/subtopic_* fields.
- If `correct` is missing but you can derive it from the solution, do so and
  add it as "correct" in the response. Otherwise omit.
- "Difficulty" should reflect how hard a 9th-grade Indian student would find
  it: easy = direct formula, medium = needs 2-3 step reasoning,
  hard = multiple concepts or tricky setup.
- Be conservative with subject_confidence. If body is short and ambiguous
  (e.g. just an equation), use "medium" or "low".
"""


def classify_batch(client: Anthropic, questions: list[dict]) -> list[dict]:
    """Classify all questions in one Claude call. Cheap & faster than per-Q."""
    user_msg = (
        'Here are the questions to classify. Return a JSON array.\n\n' +
        json.dumps(questions, ensure_ascii=False)
    )
    resp = client.messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_msg}],
    )
    text = resp.content[0].text.strip()
    # Be forgiving: sometimes models wrap JSON in ```json ... ```
    if text.startswith('```'):
        text = text.split('```', 2)[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip().rstrip('`').strip()
    return json.loads(text)


def main(paper_id: str = '2019_20'):
    raw_path = Path(__file__).parent / f'nsejs_{paper_id}_raw.json'
    out_path = Path(__file__).parent / f'nsejs_{paper_id}_classified.json'
    if not raw_path.exists():
        print(f'no such file: {raw_path}', file=sys.stderr)
        sys.exit(1)

    raw = json.loads(raw_path.read_text())
    questions = raw['questions']

    client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
    # Trim solution for the classification request — we don't need the full
    # math, just enough to disambiguate subject. Cuts tokens significantly.
    payload = []
    for q in questions:
        payload.append({
            'number': q['number'],
            'body': q['body'][:600],
            'choices': q['choices'],
            'correct': q.get('correct'),
            'solution': (q.get('solution') or '')[:200],
            'has_figure': q.get('has_figure', False),
        })

    print(f'Classifying {len(payload)} questions...', file=sys.stderr)
    classified = classify_batch(client, payload)

    # Merge classification onto raw records
    by_num = {c['number']: c for c in classified}
    out_qs = []
    for q in questions:
        c = by_num.get(q['number']) or {}
        merged = {**q, **c}
        # If Claude inferred a "correct" letter (when raw was missing), prefer Claude's
        if not merged.get('correct') and c.get('correct'):
            merged['correct'] = c['correct']
        out_qs.append(merged)

    by_subject = {}
    for q in out_qs:
        by_subject[q.get('subject', '?')] = by_subject.get(q.get('subject', '?'), 0) + 1
    print(f'Subject distribution: {by_subject}', file=sys.stderr)
    by_topic = {}
    for q in out_qs:
        if q.get('subject') == 'physics':
            t = q.get('topic_code', 'general')
            by_topic[t] = by_topic.get(t, 0) + 1
    print(f'Physics topic distribution: {by_topic}', file=sys.stderr)

    out_path.write_text(json.dumps({**raw, 'questions': out_qs}, indent=2, ensure_ascii=False))
    print(f'Wrote {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '2019_20')
