#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
import_to_anki.py

Imports generated flashcards JSON into Anki using AnkiConnect.
Automatically creates decks if they don't exist.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import requests


# AnkiConnect configuration
ANKI_CONNECT_URL = "http://localhost:8765"
ANKI_CONNECT_VERSION = 6

# Default input file
DEFAULT_INPUT = Path.home() / "Desktop" / "anki_automation" / "inbox" / "week_cards.json"


def anki_connect_request(action: str, params: Dict[str, Any] = None) -> Any:
    """Send request to AnkiConnect."""
    payload = {
        "action": action,
        "version": ANKI_CONNECT_VERSION,
        "params": params or {}
    }

    try:
        response = requests.post(ANKI_CONNECT_URL, json=payload, timeout=30)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "❌ Cannot connect to Anki.\n"
            "Please ensure:\n"
            "  1. Anki is running\n"
            "  2. AnkiConnect add-on is installed (code: 2055492159)\n"
            "  3. Anki is not showing any dialog boxes"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("❌ AnkiConnect request timed out")

    data = response.json()

    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error: {data['error']}")

    return data.get("result")


def check_anki_connect() -> str:
    """Check if AnkiConnect is available and return version."""
    try:
        version = anki_connect_request("version")
        return str(version)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to AnkiConnect: {e}")


def ensure_decks_exist(decks: List[str]) -> None:
    """Create decks if they don't exist."""
    print("\n📁 Ensuring decks exist...")
    for deck in decks:
        anki_connect_request("createDeck", {"deck": deck})
        print(f"   ✓ {deck}")


def add_note_to_anki(deck: str, front: str, back: str, tags: List[str]) -> int:
    """Add a single note to Anki. Returns note ID."""
    # Try to use custom CLAT GK Card style, fall back to Basic if not available
    note = {
        "deckName": deck,
        "modelName": "CLAT GK Card",  # Custom beautiful style
        "fields": {
            "Front": front,
            "Back": back
        },
        "tags": tags,
        "options": {
            "allowDuplicate": True
        }
    }

    try:
        return anki_connect_request("addNote", {"note": note})
    except RuntimeError as e:
        # If custom model doesn't exist, fall back to Basic
        if "model was not found" in str(e).lower():
            note["modelName"] = "Basic"
            return anki_connect_request("addNote", {"note": note})
        raise


def import_cards(cards_data: Dict[str, Any]) -> Dict[str, Any]:
    """Import all cards from JSON data."""
    cards = cards_data.get("cards", [])
    source = cards_data.get("source", "unknown")
    week = cards_data.get("week", "unknown")

    if not cards:
        raise ValueError("No cards found in JSON data")

    # Get unique decks
    decks = sorted(set(card["deck"] for card in cards))
    ensure_decks_exist(decks)

    print(f"\n📥 Importing {len(cards)} cards...")
    print(f"   Source: {source}")
    print(f"   Week: {week}\n")

    # Import cards
    imported = 0
    failed = 0
    failed_cards = []

    for idx, card in enumerate(cards, 1):
        try:
            note_id = add_note_to_anki(
                deck=card["deck"],
                front=card["front"],
                back=card["back"],
                tags=card["tags"]
            )
            imported += 1

            # Progress indicator
            if idx % 10 == 0:
                print(f"   Imported {idx}/{len(cards)} cards...")

        except Exception as e:
            failed += 1
            failed_cards.append({
                "index": idx,
                "deck": card.get("deck"),
                "front": card.get("front", "")[:50],
                "error": str(e)
            })

    # Final summary
    print(f"\n{'='*60}")
    print("IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successfully imported: {imported} cards")

    if failed > 0:
        print(f"❌ Failed: {failed} cards")
        print("\nFailed cards:")
        for fc in failed_cards[:5]:  # Show first 5 failures
            print(f"   • Card {fc['index']}: {fc['front']}...")
            print(f"     Error: {fc['error']}")
        if len(failed_cards) > 5:
            print(f"   ... and {len(failed_cards) - 5} more")

    # Deck breakdown
    deck_counts = {}
    for card in cards:
        deck = card["deck"]
        deck_counts[deck] = deck_counts.get(deck, 0) + 1

    print("\nCards per deck:")
    for deck in sorted(deck_counts.keys()):
        print(f"  • {deck}: {deck_counts[deck]}")

    return {
        "imported": imported,
        "failed": failed,
        "total": len(cards),
        "decks": deck_counts
    }


def main():
    # Determine input file
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        input_path = DEFAULT_INPUT

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        print("\nUsage: python import_to_anki.py [cards.json]")
        sys.exit(1)

    print("="*60)
    print("CLAT GK Anki Importer")
    print("="*60)
    print(f"\n📄 Loading cards from: {input_path.name}")

    # Load JSON
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            cards_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        sys.exit(1)

    print(f"✅ Loaded {len(cards_data.get('cards', []))} cards")

    # Check AnkiConnect
    print("\n🔌 Connecting to Anki...")
    try:
        version = check_anki_connect()
        print(f"✅ AnkiConnect v{version}")
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # Import cards
    try:
        result = import_cards(cards_data)
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Import completed!")
    print("\n💡 Tip: Press 'Y' in Anki to sync cards to AnkiWeb")


if __name__ == "__main__":
    main()
