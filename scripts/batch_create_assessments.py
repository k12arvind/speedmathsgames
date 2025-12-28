#!/usr/bin/env python3
"""
Batch create assessments for all small PDFs (≤13 pages).
Questions are tagged with exact PDF filename for clarity.
"""

import os
import sys
import json
import time
import fitz  # PyMuPDF
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.questions_db import QuestionsDatabase
from server.topic_extractor import TopicExtractor
from generate_flashcards_streaming import generate_flashcards_for_topics
import anthropic
import random

# Constants
MAX_PAGES = 13
BATCH_SIZE = 25  # For MCQ generation

def get_small_pdfs():
    """Get all PDFs with ≤13 pages from the 3 folders."""
    folders = [
        Path.home() / "saanvi" / "Legaledgedailygk",
        Path.home() / "saanvi" / "LegalEdgeweeklyGK", 
        Path.home() / "saanvi" / "weeklyGKCareerLauncher"
    ]
    
    small_pdfs = []
    
    for folder in folders:
        for pdf_path in sorted(folder.glob("*.pdf")):
            # Skip tracked files
            if "_tracked" in pdf_path.name:
                continue
            
            try:
                doc = fitz.open(str(pdf_path))
                pages = doc.page_count
                doc.close()
                
                if pages <= MAX_PAGES:
                    small_pdfs.append({
                        'path': str(pdf_path),
                        'filename': pdf_path.name,
                        'folder': folder.name,
                        'pages': pages
                    })
            except Exception as e:
                print(f"Error reading {pdf_path.name}: {e}")
    
    return small_pdfs


def extract_source_and_week(filename, folder):
    """Extract source name and week from filename."""
    filename_lower = filename.lower()
    
    # Determine source
    if folder == "Legaledgedailygk":
        source = "toprankers"  # Daily current affairs
    elif folder == "LegalEdgeweeklyGK":
        source = "legaledge"
    elif folder == "weeklyGKCareerLauncher":
        source = "career_launcher"
    else:
        source = "unknown"
    
    # Extract week/date
    now = datetime.now()
    if "december" in filename_lower or "dec" in filename_lower:
        month = "Dec"
    elif "november" in filename_lower or "nov" in filename_lower:
        month = "Nov"
    else:
        month = now.strftime("%b")
    
    # Try to extract week number
    import re
    week_match = re.search(r'week[_-]?(\d+)', filename_lower)
    if week_match:
        week_num = week_match.group(1)
        week = f"2025_{month}_W{week_num}"
    else:
        # Daily - use date
        date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?', filename_lower)
        if date_match:
            day = date_match.group(1)
            week = f"2025_{month}_D{day}"
        else:
            week = f"2025_{month}"
    
    return source, week


def generate_mcq_choices(client, questions):
    """Generate MCQ choices for a batch of questions."""
    if not questions:
        return {}
    
    questions_text = []
    for i, q in enumerate(questions):
        questions_text.append(f"""[Question {i+1}]
Question: {q['question']}
Correct Answer: {q['answer']}
""")

    prompt = f"""Generate 3 plausible but INCORRECT answer choices for each question.

Questions:
{''.join(questions_text)}

Return ONLY a JSON array:
[{{"question_index": 1, "distractors": ["wrong1", "wrong2", "wrong3"]}}, ...]

No markdown, no explanation."""

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()
        
        # Clean markdown
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
        
        results = json.loads(response_text)
        
        output = {}
        for item in results:
            idx = item.get('question_index', 0) - 1
            if 0 <= idx < len(questions):
                distractors = item.get('distractors', [])
                if len(distractors) >= 3:
                    correct_answer = questions[idx]['answer']
                    choices = distractors[:3] + [correct_answer]
                    random.shuffle(choices)
                    correct_index = choices.index(correct_answer)
                    output[idx] = {'choices': choices, 'correct_index': correct_index}
        
        return output
        
    except Exception as e:
        print(f"    ❌ Error generating choices: {e}")
        return {}


def process_pdf(pdf_info, questions_db, topic_extractor, anthropic_client):
    """Process a single PDF: extract topics, generate questions, generate choices."""
    
    filename = pdf_info['filename']
    filepath = pdf_info['path']
    folder = pdf_info['folder']
    
    print(f"\n{'='*60}")
    print(f"📄 Processing: {filename}")
    print(f"   Folder: {folder} | Pages: {pdf_info['pages']}")
    print(f"{'='*60}")
    
    # Get source and week for tagging
    source, week = extract_source_and_week(filename, folder)
    print(f"   Source: {source} | Week: {week}")
    
    # Step 1: Extract topics from PDF
    print(f"\n   📝 Step 1: Extracting topics...")
    try:
        topics = topic_extractor.extract_topics_from_pdf(filepath)
        print(f"      Found {len(topics)} topics")
    except Exception as e:
        print(f"      ❌ Error extracting topics: {e}")
        import traceback
        traceback.print_exc()
        return 0
    
    if not topics:
        print(f"      ⚠️ No topics found, skipping")
        return 0
    
    # Step 2: Generate flashcards/questions
    print(f"\n   🎯 Step 2: Generating questions...")
    try:
        result = generate_flashcards_for_topics(
            topics,
            source,
            week,
            start_sid=1,
            progress_callback=lambda msg: print(f"      {msg}")
        )
        cards = result.get('cards', [])
        print(f"      Generated {len(cards)} questions")
    except Exception as e:
        print(f"      ❌ Error generating questions: {e}")
        return 0
    
    if not cards:
        print(f"      ⚠️ No questions generated, skipping")
        return 0
    
    # Step 3: Save questions to database with EXACT PDF FILENAME
    print(f"\n   💾 Step 3: Saving to database...")
    saved_count = questions_db.add_questions_batch(
        pdf_filename=filename,  # Use exact filename!
        questions=cards,
        source_name=source,
        week_tag=week
    )
    print(f"      Saved {saved_count} questions (tagged to: {filename})")
    
    # Step 4: Generate MCQ choices
    print(f"\n   🎲 Step 4: Generating MCQ choices...")
    
    # Get questions we just saved
    saved_questions = questions_db.get_questions_for_pdf(filename)
    
    # Generate choices in batches
    choices_generated = 0
    for batch_start in range(0, len(saved_questions), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(saved_questions))
        batch = saved_questions[batch_start:batch_end]
        
        # Prepare for MCQ generation
        batch_for_mcq = [{'question': q['question'], 'answer': q['answer']} for q in batch]
        
        results = generate_mcq_choices(anthropic_client, batch_for_mcq)
        
        # Save choices
        for local_idx, choices_data in results.items():
            question = batch[local_idx]
            questions_db.save_mcq_choices(
                question_id=question['question_id'],
                choices=choices_data['choices'],
                correct_index=choices_data['correct_index']
            )
            choices_generated += 1
        
        print(f"      Batch {batch_start//BATCH_SIZE + 1}: {len(results)}/{len(batch)} choices generated")
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n   ✅ Complete: {saved_count} questions, {choices_generated} choices")
    return saved_count


def main():
    print("=" * 70)
    print("🚀 BATCH ASSESSMENT CREATION")
    print("=" * 70)
    
    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set!")
        sys.exit(1)
    
    # Initialize
    db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')
    questions_db = QuestionsDatabase(db_path)
    topic_extractor = TopicExtractor(db_path)
    anthropic_client = anthropic.Anthropic(api_key=api_key)
    
    # Get small PDFs
    small_pdfs = get_small_pdfs()
    print(f"\n📊 Found {len(small_pdfs)} small PDFs (≤{MAX_PAGES} pages)")
    
    # Check which already have questions
    pdfs_to_process = []
    for pdf in small_pdfs:
        existing = questions_db.get_question_count_for_pdf(pdf['filename'])
        if existing > 0:
            print(f"   ⏭️ Skipping {pdf['filename']} - already has {existing} questions")
        else:
            pdfs_to_process.append(pdf)
    
    print(f"\n📋 PDFs to process: {len(pdfs_to_process)}")
    
    if not pdfs_to_process:
        print("\n✅ All PDFs already processed!")
        return
    
    # Process each PDF
    total_questions = 0
    processed_count = 0
    start_time = time.time()
    
    for i, pdf in enumerate(pdfs_to_process):
        print(f"\n[{i+1}/{len(pdfs_to_process)}]", end="")
        questions = process_pdf(pdf, questions_db, topic_extractor, anthropic_client)
        total_questions += questions
        if questions > 0:
            processed_count += 1
    
    elapsed = time.time() - start_time
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)
    print(f"   PDFs processed: {processed_count}/{len(pdfs_to_process)}")
    print(f"   Total questions: {total_questions}")
    print(f"   Time: {int(elapsed)}s ({elapsed/60:.1f} minutes)")
    
    # Verify
    print("\n📋 Questions per PDF:")
    for pdf in pdfs_to_process:
        count = questions_db.get_question_count_for_pdf(pdf['filename'])
        status = "✅" if count > 0 else "❌"
        print(f"   {status} {pdf['filename']}: {count} questions")
    
    print("\n🎉 Done! All PDFs ready for testing.")


if __name__ == "__main__":
    main()

