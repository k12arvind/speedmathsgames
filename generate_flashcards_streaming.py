#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_flashcards_streaming.py

Generates flashcards for CLAT GK from topic batches (2-3 topics at a time).
This enables continuous progress updates instead of blocking 60-90 seconds.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

from anthropic import Anthropic


# Deck definitions (same as original)
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


BATCH_FLASHCARD_PROMPT = """You are generating flashcards for CLAT GK from a batch of 2-3 topics.
Output ONLY valid JSON in this exact schema:

{{{{
  "source": "{source}",
  "week": "{week}",
  "cards": [
    {{{{
      "deck": "CLAT GK::Awards / Sports / Defence",
      "front": "What is the question?",
      "back": "Concise answer.",
      "tags": ["source:{source}", "week:{week}", "topic:Awards_Sports_Defence", "sid:{source}_{week}_####"]
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

2. Create AS MANY cards as needed to cover EVERY factual point in the topics. For CLAT exam prep, DO NOT miss any:
   - Names (people, organizations, places)
   - Dates (when events happened)
   - Numbers (statistics, rankings, amounts)
   - What/Who/Where/When/Why facts
   - Key terms and definitions
   - Relationships between entities
   Aim for 8-15 cards PER TOPIC to ensure comprehensive coverage. More is better than missing facts.

3. front must be a single clear question.

4. back must be concise and unambiguous (1–2 lines).

5. tags must include EXACTLY these formats (NO spaces in tags):
   - source:{source}
   - week:{week}
   - topic:<OneOf: Awards_Sports_Defence, Economy_Business, Environment_Science, Government_Schemes_Reports, International_Affairs, Polity_Constitution, Static_GK, Supreme_Court_High_Court>
   - sid:{source}_{week}_#### (zero-padded 4-digit unique number, use lowercase for source and week in sid)

6. Return JSON only, no commentary, no markdown code blocks.

7. For the sid tag, use sequential numbers starting from {start_sid:04d}.

Topic Content:
{topics_text}
"""


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


def validate_batch_output(data: Dict[str, Any], source: str, week: str) -> List[str]:
    """Validate the batch JSON output and return list of errors."""
    errors = []

    # Check top-level structure
    if "source" not in data:
        errors.append("Missing top-level key 'source'")

    if "week" not in data:
        errors.append("Missing top-level key 'week'")

    if "cards" not in data:
        errors.append("Missing top-level key 'cards'")
        return errors

    cards = data["cards"]
    if not isinstance(cards, list):
        errors.append("'cards' must be a list")
        return errors

    # Check card count (smaller range for batches)
    if len(cards) < 5:
        errors.append(f"Too few cards: {len(cards)} (minimum 5 for a batch)")
    elif len(cards) > 40:
        errors.append(f"Too many cards: {len(cards)} (maximum 100 for a batch)")

    # Validate each card
    for idx, card in enumerate(cards, start=1):
        errors.extend(validate_card(card, idx))

    return errors


def generate_flashcards_for_topics(
    topic_batch: List[Dict],
    source: str,
    week: str,
    start_sid: int = 1,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Generate flashcards for a batch of 2-3 topics.

    Args:
        topic_batch: List of topic dicts with 'title' and 'content'
        source: Source identifier (e.g., 'career_launcher', 'legaledge')
        week: Week identifier (e.g., '2025_Dec_W4')
        start_sid: Starting SID number for this batch
        progress_callback: Optional callback for progress updates

    Returns:
        Dict with 'cards', 'source', 'week', 'topic_count', 'card_count'

    Raises:
        RuntimeError: If API call fails or validation fails
    """

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
        )

    # Format topics text
    topics_text = ""
    for i, topic in enumerate(topic_batch, 1):
        topics_text += f"\n\n=== TOPIC {i}: {topic['title']} ===\n"
        topics_text += topic['content']

    if progress_callback:
        topic_titles = [t['title'][:50] for t in topic_batch]
        progress_callback(f"Sending {len(topic_batch)} topics to Claude: {', '.join(topic_titles)}")

    # Create prompt
    prompt = BATCH_FLASHCARD_PROMPT.format(
        topics_text=topics_text,
        source=source,
        week=week,
        start_sid=start_sid
    )

    if progress_callback:
        progress_callback(f"Waiting for Claude response (10-15 seconds)...")

    # Call Claude API
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=16000,  # Increased for comprehensive question coverage
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

    if progress_callback:
        progress_callback("Received response from Claude, parsing...")

    # Remove markdown code blocks if present
    if response_text.startswith('```'):
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)

    # Clean up the response text
    response_text = response_text.strip()

    # Parse JSON
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response: {e}\nResponse preview: {response_text[:500]}"
        if progress_callback:
            progress_callback(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

    if progress_callback:
        progress_callback(f"Parsed {len(data.get('cards', []))} cards, validating...")

    # Validate output
    validation_errors = validate_batch_output(data, source, week)

    if validation_errors:
        error_msg = f"Validation failed:\n" + "\n".join(validation_errors[:5])
        if progress_callback:
            progress_callback(f"⚠️  {error_msg}")
        # Don't raise - just log warnings (cards may still be importable)
        print(f"⚠️  Validation warnings: {len(validation_errors)} issues found")

    # Add metadata
    result = {
        'source': source,
        'week': week,
        'cards': data.get('cards', []),
        'topic_count': len(topic_batch),
        'card_count': len(data.get('cards', [])),
        'validation_errors': validation_errors
    }

    if progress_callback:
        progress_callback(f"✅ Generated {result['card_count']} cards from {result['topic_count']} topics")

    return result


if __name__ == "__main__":
    # Test batch generation
    import sys

    if len(sys.argv) < 4:
        print("Usage: python generate_flashcards_streaming.py <source> <week> <test_mode>")
        print("\nExample:")
        print("  python generate_flashcards_streaming.py career_launcher 2025_Dec_W4 test")
        sys.exit(1)

    source = sys.argv[1]
    week = sys.argv[2]

    # Create test topics
    test_topics = [
        {
            'title': 'Test Topic 1',
            'content': 'This is test content about Indian Constitution Article 370.',
            'hash': 'test1'
        },
        {
            'title': 'Test Topic 2',
            'content': 'This is test content about Supreme Court judgement on privacy rights.',
            'hash': 'test2'
        }
    ]

    def progress_cb(msg):
        print(f"[PROGRESS] {msg}")

    print(f"Testing batch flashcard generation for {source}/{week}...\n")

    result = generate_flashcards_for_topics(
        test_topics,
        source,
        week,
        start_sid=1,
        progress_callback=progress_cb
    )

    print(f"\nResult:")
    print(f"  Topics: {result['topic_count']}")
    print(f"  Cards: {result['card_count']}")
    print(f"  Validation errors: {len(result['validation_errors'])}")

    if result['cards']:
        print(f"\nFirst card:")
        print(json.dumps(result['cards'][0], indent=2))
