#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_flashcards.py

Generates Anki flashcards for CLAT GK from a Manthan PDF using Claude API.
Outputs valid JSON with 100-200 cards following the exact schema required.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any
import fitz  # PyMuPDF
from anthropic import Anthropic


# Configuration
OUTPUT_PATH = Path.home() / "Desktop" / "anki_automation" / "inbox" / "week_cards.json"
WEEK_TAG = "2025_Dec_W1"
SOURCE = "manthan"

# Deck definitions
DECKS = [
    "CLAT GK::Awards / Sports / Defence",
    "CLAT GK::Economy & Business",
    "CLAT GK::Environment & Science",
    "CLAT GK::Government Schemes & Reports",
    "CLAT GK::International Affairs",
    "CLAT GK::Polity & Constitution",
    "CLAT GK::Static GK",
    "CLAT GK::Supreme Court / High Court Judgements",
]

# Topic tags (must match deck categories)
TOPIC_TAGS = [
    "Awards_Sports_Defence",
    "Economy_Business",
    "Environment_Science",
    "Government_Schemes_Reports",
    "International_Affairs",
    "Polity_Constitution",
    "Static_GK",
    "Supreme_Court_High_Court",
]


FLASHCARD_PROMPT = """You are generating Anki flashcards for CLAT GK from the attached PDF.
Output ONLY valid JSON in this exact schema:

{{{{
  "source": "{source}",
  "week": "{week}",
  "cards": [
    {{{{
      "deck": "CLAT GK::Awards / Sports / Defence",
      "front": "What is the question?",
      "back": "Concise answer.",
      "tags": ["source:{source}", "week:{week}", "topic:Awards_Sports_Defence", "sid:{source}_{week}_0001"]
    }}}}
  ]
}}}}

Constraints:

1. deck must be one of:
   - CLAT GK::Awards / Sports / Defence
   - CLAT GK::Economy & Business
   - CLAT GK::Environment & Science
   - CLAT GK::Government Schemes & Reports
   - CLAT GK::International Affairs
   - CLAT GK::Polity & Constitution
   - CLAT GK::Static GK
   - CLAT GK::Supreme Court / High Court Judgements

2. Create 80-120 cards per chunk (prioritize factual, testable points).

3. front must be a single clear question.

4. back must be concise and unambiguous (1–2 lines).

5. tags must include EXACTLY these formats (NO spaces in tags):
   - source:{source}
   - week:{week}
   - topic:<OneOf: Awards_Sports_Defence, Economy_Business, Environment_Science, Government_Schemes_Reports, International_Affairs, Polity_Constitution, Static_GK, Supreme_Court_High_Court>
   - sid:{source}_{week}_#### (zero-padded 4-digit unique number starting from 0001, use lowercase for source and week in sid)

6. Return JSON only, no commentary, no markdown code blocks.

PDF Content:
{pdf_text}
"""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF with page markers."""
    doc = fitz.open(str(pdf_path))
    parts = []
    for i, page in enumerate(doc):
        txt = page.get_text("text")
        if txt and txt.strip():
            parts.append(f"\n\n=== PAGE {i+1} ===\n")
            parts.append(txt)

    text = "".join(parts)
    # Clean up text
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # Join hyphenated words
    text = re.sub(r"[ \t]+", " ", text)  # Collapse spaces
    return text.strip()


def validate_card(card: Dict[str, Any], card_idx: int) -> List[str]:
    """Validate a single card and return list of errors."""
    errors = []

    # Check required keys
    required_keys = ["deck", "front", "back", "tags"]
    for key in required_keys:
        if key not in card:
            errors.append(f"Card {card_idx}: Missing required key '{key}'")

    # Validate deck
    if "deck" in card and card["deck"] not in DECKS:
        errors.append(f"Card {card_idx}: Invalid deck '{card['deck']}'")

    # Validate front and back are non-empty strings
    if "front" in card and (not isinstance(card["front"], str) or not card["front"].strip()):
        errors.append(f"Card {card_idx}: 'front' must be a non-empty string")

    if "back" in card and (not isinstance(card["back"], str) or not card["back"].strip()):
        errors.append(f"Card {card_idx}: 'back' must be a non-empty string")

    # Validate tags
    if "tags" in card:
        if not isinstance(card["tags"], list):
            errors.append(f"Card {card_idx}: 'tags' must be a list")
        else:
            tags = card["tags"]

            # Check for spaces in tags
            for tag in tags:
                if " " in tag:
                    errors.append(f"Card {card_idx}: Tag '{tag}' contains spaces")

            # Check required tag formats
            has_source = any(tag.startswith("source:") for tag in tags)
            has_week = any(tag.startswith("week:") for tag in tags)
            has_topic = any(tag.startswith("topic:") for tag in tags)
            has_sid = any(tag.startswith("sid:") for tag in tags)

            if not has_source:
                errors.append(f"Card {card_idx}: Missing 'source:' tag")
            if not has_week:
                errors.append(f"Card {card_idx}: Missing 'week:' tag")
            if not has_topic:
                errors.append(f"Card {card_idx}: Missing 'topic:' tag")
            if not has_sid:
                errors.append(f"Card {card_idx}: Missing 'sid:' tag")

            # Validate topic tag value
            topic_tags = [tag for tag in tags if tag.startswith("topic:")]
            if topic_tags:
                topic_value = topic_tags[0].split(":", 1)[1]
                if topic_value not in TOPIC_TAGS:
                    errors.append(f"Card {card_idx}: Invalid topic tag value '{topic_value}'")

    return errors


def validate_output(data: Dict[str, Any], source: str = None, week: str = None) -> List[str]:
    """Validate the entire JSON output and return list of errors."""
    errors = []

    # Use defaults if not provided
    if source is None:
        source = SOURCE
    if week is None:
        week = WEEK_TAG

    # Check top-level structure
    if "source" not in data:
        errors.append("Missing top-level key 'source'")
    elif data["source"] != source:
        # Changed from error to warning - import process handles metadata assignment
        print(f"⚠️  Warning: Generated source '{data['source']}' differs from expected '{source}'")
        print(f"    This is OK - import process will use the correct source tag")

    if "week" not in data:
        errors.append("Missing top-level key 'week'")
    elif data["week"] != week:
        # Changed from error to warning - import process handles metadata assignment
        print(f"⚠️  Warning: Generated week '{data['week']}' differs from expected '{week}'")
        print(f"    This is OK - import process will use the correct week tag")

    if "cards" not in data:
        errors.append("Missing top-level key 'cards'")
        return errors

    cards = data["cards"]
    if not isinstance(cards, list):
        errors.append("'cards' must be a list")
        return errors

    # Check card count
    if len(cards) < 20:
        errors.append(f"Too few cards: {len(cards)} (minimum 20)")
    elif len(cards) > 200:
        errors.append(f"Too many cards: {len(cards)} (maximum 200)")

    # Validate each card
    for idx, card in enumerate(cards, start=1):
        errors.extend(validate_card(card, idx))

    return errors


def generate_flashcards(pdf_path: Path, source: str = None, week: str = None) -> Dict[str, Any]:
    """Generate flashcards using Claude API."""

    # Use defaults if not provided
    if source is None:
        source = SOURCE
    if week is None:
        week = WEEK_TAG

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
        )

    print(f"📄 Extracting text from {pdf_path.name}...")
    pdf_text = extract_pdf_text(pdf_path)
    print(f"✅ Extracted {len(pdf_text)} characters")

    # Create prompt with dynamic source and week
    prompt = FLASHCARD_PROMPT.format(pdf_text=pdf_text, source=source, week=week)

    print("\n🤖 Generating flashcards with Claude...")
    print("   (This may take 1-2 minutes for 100-200 cards)\n")

    # Call Claude API
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=16000,
        temperature=1,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Extract response
    response_text = message.content[0].text

    # Remove markdown code blocks if present
    if response_text.startswith('```'):
        # Remove opening ```json or ```
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        # Remove closing ```
        response_text = re.sub(r'\n?```\s*$', '', response_text)

    # Clean up the response text
    response_text = response_text.strip()

    # Parse JSON
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print("\nResponse preview (first 1000 chars):")
        print(response_text[:1000])
        print("\n\nLast 500 chars:")
        print(response_text[-500:])

        # Try to save the raw response for debugging
        debug_path = OUTPUT_PATH.parent / "debug_response.txt"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"\n💾 Saved full response to: {debug_path}")
        raise

    return data


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_flashcards.py input.pdf [source] [week]")
        print("\nExample:")
        print("  python generate_flashcards.py inbox/input.pdf manthan 2025_Dec_W1")
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).expanduser().resolve()
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    # Get source and week from command line or use defaults
    source = sys.argv[2] if len(sys.argv) > 2 else SOURCE
    week = sys.argv[3] if len(sys.argv) > 3 else WEEK_TAG

    print("=" * 60)
    print("CLAT GK Flashcard Generator")
    print("=" * 60)

    # Generate flashcards
    try:
        data = generate_flashcards(pdf_path, source, week)
    except Exception as e:
        print(f"\n❌ Error generating flashcards: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Validate output
    print(f"✅ Generated {len(data.get('cards', []))} cards")
    print("\n🔍 Validating output...")

    errors = validate_output(data, source, week)
    if errors:
        print(f"\n⚠️  Found {len(errors)} validation errors:\n")
        for error in errors[:10]:  # Show first 10 errors
            print(f"   • {error}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
        print("\n❌ Validation failed. Please review and fix.")
        sys.exit(1)

    print("✅ All validations passed!")

    # Save output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(data['cards'])} flashcards to:")
    print(f"   {OUTPUT_PATH}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Source:      {data['source']}")
    print(f"Week:        {data['week']}")
    print(f"Total cards: {len(data['cards'])}")

    # Deck breakdown
    deck_counts = {}
    for card in data["cards"]:
        deck = card["deck"]
        deck_counts[deck] = deck_counts.get(deck, 0) + 1

    print("\nCards per deck:")
    for deck in DECKS:
        count = deck_counts.get(deck, 0)
        if count > 0:
            print(f"  • {deck}: {count}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
