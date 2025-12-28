#!/usr/bin/env python3
"""
Migrate Anki Questions to Local Database

This script imports all existing CLAT GK questions from Anki into the local
questions database, making the system independent of AnkiConnect for tests.

Usage:
    python scripts/migrate_anki_to_local_db.py
    
Requirements:
    - Anki must be running with AnkiConnect addon
"""

import sys
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.questions_db import QuestionsDatabase


def anki_request(action: str, params: dict = None) -> any:
    """Make a request to AnkiConnect."""
    request_data = {
        "action": action,
        "version": 6
    }
    if params:
        request_data["params"] = params
    
    try:
        req = urllib.request.Request(
            'http://localhost:8765',
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req, timeout=30)
        result = json.loads(response.read().decode('utf-8'))
        
        if result.get('error'):
            raise Exception(f"AnkiConnect error: {result['error']}")
        
        return result.get('result')
    except urllib.error.URLError as e:
        raise Exception(f"Cannot connect to Anki. Make sure Anki is running with AnkiConnect addon. Error: {e}")


def get_all_clat_notes() -> List[int]:
    """Get all note IDs from CLAT GK decks."""
    print("📚 Finding all CLAT GK notes...")
    
    # Search for notes in CLAT decks
    note_ids = anki_request("findNotes", {"query": "deck:CLAT*"})
    print(f"   Found {len(note_ids)} notes in CLAT decks")
    
    return note_ids


def get_notes_info(note_ids: List[int]) -> List[Dict]:
    """Get detailed info for notes."""
    if not note_ids:
        return []
    
    return anki_request("notesInfo", {"notes": note_ids})


def extract_pdf_filename_from_tags(tags: List[str]) -> Optional[str]:
    """Extract PDF filename from Anki tags.
    
    Tags are typically:
    - source:career_launcher or source:legaledge
    - week:2025_Dec_W2 or week:2025_Dec_D19
    - topic:Economy_Business
    - sid:career_launcher_2025_dec_w2_0001
    
    We need to map these back to PDF filenames.
    """
    source = None
    week = None
    
    for tag in tags:
        if tag.startswith('source:'):
            source = tag.split(':', 1)[1]
        elif tag.startswith('week:'):
            week = tag.split(':', 1)[1]
    
    if source and week:
        # Construct a pseudo-filename from source and week
        return f"{source}_{week}"
    
    return None


def extract_category_from_deck(deck_name: str) -> str:
    """Extract category from deck name.
    
    e.g., "CLAT GK::Economy & Business" -> "Economy & Business"
    """
    if '::' in deck_name:
        return deck_name.split('::')[-1]
    return deck_name


def migrate_notes_to_local_db(db: QuestionsDatabase) -> Dict[str, int]:
    """Migrate all Anki notes to local database."""
    
    # Get all note IDs
    note_ids = get_all_clat_notes()
    
    if not note_ids:
        print("❌ No notes found in Anki!")
        return {}
    
    # Get note info in batches
    batch_size = 100
    all_notes = []
    
    print(f"\n📥 Fetching note details in batches of {batch_size}...")
    
    for i in range(0, len(note_ids), batch_size):
        batch = note_ids[i:i + batch_size]
        notes = get_notes_info(batch)
        all_notes.extend(notes)
        print(f"   Fetched {min(i + batch_size, len(note_ids))}/{len(note_ids)} notes...")
    
    print(f"\n📝 Processing {len(all_notes)} notes...")
    
    # Group notes by PDF source
    pdf_groups = defaultdict(list)
    skipped = 0
    
    for note in all_notes:
        fields = note.get('fields', {})
        tags = note.get('tags', [])
        
        # Get question and answer
        front = fields.get('Front', {}).get('value', '')
        back = fields.get('Back', {}).get('value', '')
        
        if not front or not back:
            skipped += 1
            continue
        
        # Clean HTML from fields
        import re
        front = re.sub(r'<[^>]+>', '', front).strip()
        back = re.sub(r'<[^>]+>', '', back).strip()
        
        # Extract PDF source from tags
        pdf_source = extract_pdf_filename_from_tags(tags)
        
        if not pdf_source:
            # Use a default if no source found
            pdf_source = "unknown_source"
        
        # Extract other metadata
        deck = note.get('modelName', 'CLAT GK')
        for tag in tags:
            if 'CLAT' in tag:
                deck = tag
                break
        
        # Get category from tags
        category = "General"
        for tag in tags:
            if tag.startswith('topic:'):
                category = tag.split(':', 1)[1].replace('_', ' ')
                break
        
        pdf_groups[pdf_source].append({
            'front': front,
            'back': back,
            'deck': deck,
            'category': category,
            'tags': tags,
            'anki_note_id': str(note.get('noteId', ''))
        })
    
    print(f"   Grouped into {len(pdf_groups)} PDF sources")
    print(f"   Skipped {skipped} notes (missing front/back)")
    
    # Import to local database
    print(f"\n💾 Importing to local database...")
    
    stats = {}
    total_imported = 0
    
    for pdf_source, questions in sorted(pdf_groups.items()):
        # Add .pdf extension if not present
        pdf_filename = pdf_source if pdf_source.endswith('.pdf') else f"{pdf_source}.pdf"
        
        # Extract source_name and week from the tags of first question
        source_name = None
        week_tag = None
        if questions:
            for tag in questions[0].get('tags', []):
                if tag.startswith('source:'):
                    source_name = tag.split(':', 1)[1]
                elif tag.startswith('week:'):
                    week_tag = tag.split(':', 1)[1]
        
        imported = db.add_questions_batch(
            pdf_filename=pdf_filename,
            questions=questions,
            source_name=source_name,
            week_tag=week_tag
        )
        
        stats[pdf_filename] = imported
        total_imported += imported
        
        if imported > 0:
            print(f"   ✅ {pdf_filename}: {imported} questions")
    
    print(f"\n🎉 Migration complete!")
    print(f"   Total imported: {total_imported} questions")
    print(f"   PDF sources: {len(stats)}")
    
    return stats


def main():
    print("=" * 60)
    print("ANKI TO LOCAL DATABASE MIGRATION")
    print("=" * 60)
    print()
    
    # Check Anki connection
    print("🔌 Checking AnkiConnect...")
    try:
        version = anki_request("version")
        print(f"   AnkiConnect version: {version}")
    except Exception as e:
        print(f"❌ {e}")
        print("\nPlease make sure:")
        print("  1. Anki is running")
        print("  2. AnkiConnect addon is installed (code: 2055492159)")
        print("  3. No dialogs are open in Anki")
        sys.exit(1)
    
    # Initialize local database
    print("\n📂 Initializing local database...")
    db = QuestionsDatabase()
    
    # Check existing questions
    existing = db.get_all_pdf_question_counts()
    if existing:
        print(f"   Found {sum(existing.values())} existing questions in {len(existing)} PDFs")
        
        response = input("\n⚠️  Do you want to skip existing PDFs? (y/n): ").strip().lower()
        skip_existing = response == 'y'
    else:
        skip_existing = False
    
    # Run migration
    print()
    stats = migrate_notes_to_local_db(db)
    
    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    
    # Get final counts
    final_counts = db.get_all_pdf_question_counts()
    print(f"\nLocal database now contains:")
    print(f"  📄 {len(final_counts)} PDFs")
    print(f"  ❓ {sum(final_counts.values())} questions")
    
    print("\nTop 10 PDFs by question count:")
    sorted_pdfs = sorted(final_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for pdf, count in sorted_pdfs:
        print(f"  • {pdf[:60]}: {count} questions")


if __name__ == "__main__":
    main()

