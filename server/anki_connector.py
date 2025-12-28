#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
anki_connector.py

Integration with AnkiConnect to fetch questions for assessments.
"""

import requests
from typing import List, Dict, Optional


class AnkiConnector:
    """Connects to Anki via AnkiConnect API."""

    def __init__(self, url: str = "http://localhost:8765"):
        self.url = url

    def _request(self, action: str, params: Optional[Dict] = None) -> any:
        """Make a request to AnkiConnect."""
        payload = {
            "action": action,
            "version": 6,
            "params": params or {}
        }

        try:
            response = requests.post(self.url, json=payload, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise RuntimeError(f"AnkiConnect error: {data['error']}")

            return data.get("result")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Cannot connect to Anki. Make sure Anki is running with AnkiConnect plugin.")
        except requests.exceptions.Timeout:
            raise TimeoutError("AnkiConnect request timed out.")

    def test_connection(self) -> bool:
        """Test if Anki is running and AnkiConnect is available."""
        try:
            version = self._request("version")
            return version is not None
        except:
            return False

    def get_deck_names(self) -> List[str]:
        """Get all deck names."""
        return self._request("deckNames")

    def get_notes_by_tags(self, tags: List[str]) -> List[int]:
        """Get note IDs by tags."""
        query = " OR ".join([f"tag:{tag}" for tag in tags])
        return self._request("findNotes", {"query": query})

    def get_notes_by_source_date(self, source_date: str) -> List[int]:
        """Get notes for a specific source date (PDF) or PDF filename."""
        # Try multiple search strategies:
        # 1. Daily date format: week:2025_Dec_D19 (from source_date: 2025-12-19)
        # 2. Weekly format: week:2025_Dec_W1 (from source_date: 2025_Dec_W1)
        # 3. Direct source tag: source:2025-12-19
        # 4. PDF filename tag: source:{filename}
        # 5. Search by Source field content

        # Strategy 1: Convert date format 2025-12-19 → 2025_Dec_D19
        if "-" in source_date and len(source_date.split("-")) == 3:
            parts = source_date.split("-")
            year, month, day = parts
            month_abbr = {
                "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
                "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
                "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
            }.get(month, month)
            week_tag = f"{year}_{month_abbr}_D{int(day)}"
            query = f"tag:week:{week_tag}"
            result = self._request("findNotes", {"query": query})
            if result:
                return result

        # Strategy 2: Weekly format (source_date might already be in week format)
        if "W" in source_date or "WEEK" in source_date.upper():
            query = f"tag:week:{source_date}"
            result = self._request("findNotes", {"query": query})
            if result:
                return result

        # Strategy 3: Direct source tag
        query = f"tag:source:{source_date}"
        result = self._request("findNotes", {"query": query})
        if result:
            return result

        # Strategy 4: Try with .pdf extension removed
        clean_name = source_date.replace('.pdf', '').replace('.PDF', '')
        query = f"tag:source:{clean_name}"
        result = self._request("findNotes", {"query": query})
        if result:
            return result

        # Strategy 5: Search by Source field content (for any PDF filename)
        # This handles cases where cards have the PDF name in the Source field
        query = f'"Source:{source_date}"'
        result = self._request("findNotes", {"query": query})
        if result:
            return result
        
        # Strategy 6: Partial match on Source field (without extension)
        query = f'"Source:*{clean_name}*"'
        result = self._request("findNotes", {"query": query})
        if result:
            return result

        # Strategy 7: Search in CLAT deck for any notes containing this filename
        # Use wildcard search on source field
        query = f'deck:CLAT* "Source:*{clean_name[:30]}*"'
        result = self._request("findNotes", {"query": query})
        if result:
            return result

        return []

    def get_note_info(self, note_ids: List[int]) -> List[Dict]:
        """Get detailed information about notes."""
        if not note_ids:
            return []

        notes_info = self._request("notesInfo", {"notes": note_ids})

        # Parse and structure the data
        questions = []
        for note in notes_info:
            # Extract fields
            fields = note.get("fields", {})
            front = fields.get("Front", {}).get("value", "")
            back = fields.get("Back", {}).get("value", "")

            # Extract category from tags
            tags = note.get("tags", [])
            category = "General"
            for tag in tags:
                if tag.startswith("topic:"):
                    category = tag.replace("topic:", "").replace("_", " ")
                    break

            questions.append({
                "note_id": note["noteId"],
                "question": front,
                "answer": back,
                "category": category,
                "tags": tags,
                "deck": note.get("deckName", "")
            })

        return questions

    def get_questions_for_pdf(self, source_date: str) -> List[Dict]:
        """Get all questions for a specific PDF (by source date)."""
        note_ids = self.get_notes_by_source_date(source_date)
        return self.get_note_info(note_ids)

    def get_questions_by_note_ids(self, note_ids: List[str]) -> List[Dict]:
        """Get questions by Anki note IDs."""
        # Convert to integers if they're strings
        note_ids = [int(nid) if isinstance(nid, str) else nid for nid in note_ids]
        return self.get_note_info(note_ids)

    def get_questions_by_category(self, category: str, limit: Optional[int] = None) -> List[Dict]:
        """Get questions by category."""
        # Convert category to tag format
        category_tag = category.replace(" ", "_")
        query = f"tag:topic:{category_tag}"

        note_ids = self._request("findNotes", {"query": query})

        if limit:
            note_ids = note_ids[:limit]

        return self.get_note_info(note_ids)

    def get_all_clat_questions(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all CLAT GK questions."""
        query = "deck:CLAT*"
        note_ids = self._request("findNotes", {"query": query})

        if limit:
            note_ids = note_ids[:limit]

        return self.get_note_info(note_ids)

    def get_categories(self) -> List[str]:
        """Get all unique categories from CLAT GK deck."""
        # Get all CLAT notes
        note_ids = self._request("findNotes", {"query": "deck:CLAT*"})

        if not note_ids:
            return []

        # Get note info
        notes = self.get_note_info(note_ids[:100])  # Sample first 100 for categories

        # Extract unique categories
        categories = set()
        for note in notes:
            categories.add(note["category"])

        return sorted(list(categories))


if __name__ == '__main__':
    # Test AnkiConnect
    connector = AnkiConnector()

    print("Testing AnkiConnect connection...")

    if connector.test_connection():
        print("✅ Connected to Anki!")

        # Get decks
        decks = connector.get_deck_names()
        clat_decks = [d for d in decks if 'CLAT' in d]
        print(f"\n📚 CLAT Decks found: {len(clat_decks)}")
        for deck in clat_decks:
            print(f"   • {deck}")

        # Get categories
        print("\n📊 Categories:")
        categories = connector.get_categories()
        for cat in categories:
            print(f"   • {cat}")

        # Get sample questions
        print("\n❓ Sample questions:")
        questions = connector.get_all_clat_questions(limit=3)
        for q in questions:
            print(f"\n   Q: {q['question'][:80]}...")
            print(f"   A: {q['answer'][:80]}...")
            print(f"   Category: {q['category']}")

    else:
        print("❌ Cannot connect to Anki. Make sure:")
        print("   1. Anki is running")
        print("   2. AnkiConnect plugin is installed")
        print("   3. AnkiConnect is listening on port 8765")
