#!/usr/bin/env python3
"""
Assessment Processor
Orchestrates topic-by-topic assessment creation with continuous progress updates.
"""

import os
import sys
import json
import sqlite3
import random
from pathlib import Path
from typing import Dict, List
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file BEFORE importing anthropic
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

import anthropic

from server.topic_extractor import TopicExtractor
from server.assessment_jobs_db import AssessmentJobsDB
from server.pdf_chunker import PdfChunker
from server.questions_db import QuestionsDatabase
from server.pdf_scanner import relative_to_absolute  # Cross-machine path compatibility
from generate_flashcards_streaming import generate_flashcards_for_topics
from import_to_anki import add_note_to_anki, ensure_decks_exist, check_anki_connect


class AssessmentProcessor:
    """Orchestrate topic-by-topic assessment creation with progress tracking."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        if db_path is None:
            db_path = str(Path.home() / 'clat_preparation' / 'revision_tracker.db')

        self.db_path = db_path
        self.topic_extractor = TopicExtractor(db_path)
        self.jobs_db = AssessmentJobsDB(db_path)
        self.pdf_chunker = PdfChunker(db_path)
        self.questions_db = QuestionsDatabase(db_path)  # Local questions storage
        
        # Initialize Anthropic client for MCQ generation
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.anthropic_client = anthropic.Anthropic(api_key=api_key) if api_key else None

    def generate_mcq_choices_for_questions(self, pdf_filename: str, job_id: str = None) -> int:
        """
        Generate MCQ choices for all questions of a PDF that don't have choices yet.
        
        This is called DURING assessment creation to ensure tests are instant.
        
        Returns: Number of choices generated
        """
        if not self.anthropic_client:
            if self.progress_callback and job_id:
                self.progress_callback(job_id, "⚠️ Skipping MCQ generation (no API key)")
            return 0
        
        # Get questions without choices for this PDF
        conn = self.questions_db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT q.question_id, q.question_text, q.answer_text
            FROM questions q
            WHERE q.pdf_filename = ?
            AND q.question_id NOT IN (SELECT question_id FROM question_choices)
            ORDER BY q.question_id
        """, (pdf_filename,))
        
        questions = []
        for row in cursor.fetchall():
            questions.append({
                'question_id': row['question_id'],
                'question': row['question_text'],
                'answer': row['answer_text']
            })
        conn.close()
        
        if not questions:
            return 0
        
        if self.progress_callback and job_id:
            self.progress_callback(job_id, f"🎯 Generating MCQ choices for {len(questions)} questions...")
        
        # Process in batches
        batch_size = 10
        generated = 0
        
        for batch_start in range(0, len(questions), batch_size):
            batch_end = min(batch_start + batch_size, len(questions))
            batch = questions[batch_start:batch_end]
            
            try:
                results = self._generate_choices_batch(batch)
                
                # Save results
                for local_idx, choices_data in results.items():
                    question = batch[local_idx]
                    saved = self.questions_db.save_mcq_choices(
                        question_id=question['question_id'],
                        choices=choices_data['choices'],
                        correct_index=choices_data['correct_index']
                    )
                    if saved:
                        generated += 1
                
                if self.progress_callback and job_id:
                    self.progress_callback(
                        job_id, 
                        f"   Generated choices: {generated}/{len(questions)}"
                    )
                    
            except Exception as e:
                print(f"Error generating choices batch: {e}")
        
        return generated

    def _generate_choices_batch(self, questions: list) -> dict:
        """Generate MCQ choices for a batch of questions using Claude API."""
        
        questions_text = []
        for i, q in enumerate(questions):
            questions_text.append(f"""[Question {i+1}]
Question: {q['question']}
Correct Answer: {q['answer']}
""")

        prompt = f"""You are an expert at creating multiple choice questions for CLAT (Common Law Admission Test) General Knowledge preparation.

Given the following questions with their correct answers, generate 3 plausible but INCORRECT answer choices (distractors) for each question.

Guidelines:
- Distractors should be plausible but clearly wrong
- Use similar format/structure as correct answer
- For names: use other real people in similar roles
- For numbers: use nearby numbers or related statistics
- For dates: use nearby dates or related events
- For places: use other locations in same category

Questions:
{''.join(questions_text)}

Return ONLY a JSON array with one object per question:
[
  {{"question_index": 1, "distractors": ["wrong1", "wrong2", "wrong3"]}},
  ...
]

No markdown, no explanation - just the JSON array."""

        message = self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()
        
        # Clean markdown if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
        
        results = json.loads(response_text)
        
        # Process results
        output = {}
        for item in results:
            idx = item.get('question_index', 0) - 1  # Convert to 0-indexed
            if 0 <= idx < len(questions):
                distractors = item.get('distractors', [])
                if len(distractors) >= 3:
                    correct_answer = questions[idx]['answer']
                    choices = distractors[:3] + [correct_answer]
                    random.shuffle(choices)
                    correct_index = choices.index(correct_answer)
                    
                    output[idx] = {
                        'choices': choices,
                        'correct_index': correct_index
                    }
        
        return output

    def get_chunks_for_pdf(self, parent_pdf_id: str) -> List[Dict]:
        """
        Get all chunks for a PDF.

        If PDF is not chunked, treat the PDF itself as a single "chunk".
        """
        chunks = self.pdf_chunker.get_chunks(parent_pdf_id)

        if not chunks:
            # PDF is not chunked - treat entire PDF as one chunk
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT filename, filepath
                    FROM pdfs
                    WHERE filename = ?
                """, (parent_pdf_id,))

                pdf = cursor.fetchone()

                if pdf:
                    # Create pseudo-chunk for non-chunked PDF
                    # Expand relative path to absolute for current machine
                    absolute_path = relative_to_absolute(pdf['filepath'])
                    chunks = [{
                        'chunk_id': 0,
                        'chunk_filename': pdf['filename'],
                        'chunk_path': absolute_path,
                        'chunk_number': 1,
                        'parent_pdf_id': parent_pdf_id
                    }]

            finally:
                conn.close()

        return chunks

    def mark_chunk_complete(self, chunk_id: int, card_count: int):
        """Mark a chunk as having assessments created."""
        if chunk_id == 0:
            # Pseudo-chunk for non-chunked PDF - skip
            return

        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE pdf_chunks
                SET assessment_created = 1,
                    assessment_card_count = ?,
                    assessment_created_at = datetime('now')
                WHERE chunk_id = ?
            """, (card_count, chunk_id))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to mark chunk complete: {e}")

        finally:
            conn.close()

    def progress_callback(self, job_id: str, message: str):
        """Callback for progress updates."""
        print(f"[{job_id}] {message}")
        # Update job status message
        self.jobs_db.update_progress(
            job_id,
            status_message=message
        )

    def process_pdf_assessment(
        self,
        job_id: str,
        parent_pdf_id: str,
        source: str,
        week: str,
        batch_size: int = 3
    ):
        """
        Process assessment creation for a PDF (all chunks).

        This is the main orchestration method that:
        1. Gets all chunks for the PDF
        2. For each chunk:
           - Extracts topics
           - Batches into groups of 2-3
           - For each batch:
             - Skips duplicates (overlapping pages)
             - Sends to Claude (10-15s)
             - Imports to Anki
             - Updates progress
        3. Marks chunks as complete

        Args:
            job_id: Job ID for progress tracking
            parent_pdf_id: Parent PDF filename
            source: Source identifier
            week: Week identifier
            batch_size: Topics per batch (default 3)
        """
        try:
            # Update job status
            self.jobs_db.update_progress(
                job_id,
                status='processing',
                status_message='Starting assessment creation...'
            )

            # Check AnkiConnect
            self.progress_callback(job_id, 'Checking AnkiConnect...')
            try:
                version = check_anki_connect()
                self.progress_callback(job_id, f'✅ AnkiConnect version {version}')
            except Exception as e:
                raise RuntimeError(f"AnkiConnect not available: {e}")

            # Ensure decks exist
            self.progress_callback(job_id, 'Ensuring Anki decks exist...')
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
            ensure_decks_exist(DECKS)

            # Get all chunks for this PDF
            chunks = self.get_chunks_for_pdf(parent_pdf_id)

            if not chunks:
                raise RuntimeError(f"No chunks found for PDF: {parent_pdf_id}")

            self.jobs_db.update_progress(
                job_id,
                total_chunks=len(chunks),
                current_chunk=0,
                status_message=f'Found {len(chunks)} chunk(s) to process'
            )

            total_cards_overall = 0
            global_sid = 1  # Track SID across batches

            # Process each chunk
            for chunk_idx, chunk in enumerate(chunks, 1):
                chunk_path = chunk['chunk_path']
                chunk_name = chunk['chunk_filename']

                self.progress_callback(
                    job_id,
                    f'Processing chunk {chunk_idx}/{len(chunks)}: {chunk_name}'
                )

                self.jobs_db.update_progress(
                    job_id,
                    current_chunk=chunk_idx,
                    current_batch=0,
                    status_message=f'Extracting topics from chunk {chunk_idx}...'
                )

                # Extract topics from chunk
                try:
                    topics = self.topic_extractor.extract_topics_from_pdf(chunk_path)
                except Exception as e:
                    self.progress_callback(
                        job_id,
                        f'⚠️  Failed to extract topics from {chunk_name}: {e}'
                    )
                    continue

                if not topics:
                    self.progress_callback(
                        job_id,
                        f'⚠️  No topics found in {chunk_name}, skipping'
                    )
                    continue

                self.progress_callback(
                    job_id,
                    f'✅ Extracted {len(topics)} topics from {chunk_name}'
                )

                # Batch topics
                topic_batches = self.topic_extractor.batch_topics(topics, batch_size)

                self.jobs_db.update_progress(
                    job_id,
                    total_batches=len(topic_batches),
                    status_message=f'Batched into {len(topic_batches)} batches'
                )

                chunk_cards_total = 0

                # Process each batch
                for batch_idx, batch in enumerate(topic_batches, 1):
                    # Filter out duplicates
                    unique_topics = []
                    duplicate_count = 0

                    for topic in batch:
                        if self.topic_extractor.is_duplicate_topic(topic['hash'], parent_pdf_id):
                            duplicate_count += 1
                        else:
                            unique_topics.append(topic)

                    if duplicate_count > 0:
                        self.progress_callback(
                            job_id,
                            f'Batch {batch_idx}/{len(topic_batches)}: Skipped {duplicate_count} duplicate topic(s)'
                        )

                    if not unique_topics:
                        self.progress_callback(
                            job_id,
                            f'Batch {batch_idx}/{len(topic_batches)}: All topics already processed (overlap)'
                        )
                        continue

                    # Show topic titles being processed
                    topic_titles = [t['title'][:50] for t in unique_topics]
                    self.progress_callback(
                        job_id,
                        f'Batch {batch_idx}/{len(topic_batches)}: Processing topics - {", ".join(topic_titles)}'
                    )

                    # Update progress
                    self.jobs_db.update_progress(
                        job_id,
                        current_batch=batch_idx,
                        status_message=f'Chunk {chunk_idx}: Batch {batch_idx}/{len(topic_batches)} - Processing {len(unique_topics)} topics'
                    )

                    # Send to Claude API
                    self.progress_callback(
                        job_id,
                        f'Batch {batch_idx}: Waiting for Claude response (10-15 seconds)...'
                    )

                    # Generate flashcards for this batch
                    try:
                        result = generate_flashcards_for_topics(
                            unique_topics,
                            source,
                            week,
                            start_sid=global_sid,
                            progress_callback=lambda msg: self.progress_callback(job_id, msg)
                        )

                        cards = result.get('cards', [])
                        batch_card_count = len(cards)

                        # STEP 1: Save to local database (SOURCE OF TRUTH)
                        self.progress_callback(
                            job_id,
                            f'Saving {batch_card_count} cards to database...'
                        )

                        saved_count = self.questions_db.add_questions_batch(
                            pdf_filename=parent_pdf_id,
                            questions=cards,
                            source_name=source,
                            week_tag=week
                        )
                        
                        self.progress_callback(
                            job_id,
                            f'✅ Saved {saved_count} cards to database'
                        )

                        # STEP 2: Generate MCQ choices for instant tests
                        self.progress_callback(
                            job_id,
                            f'🎯 Generating MCQ choices for test...'
                        )
                        
                        mcq_generated = self.generate_mcq_choices_for_questions(parent_pdf_id, job_id)
                        
                        if mcq_generated > 0:
                            self.progress_callback(
                                job_id,
                                f'✅ Generated {mcq_generated} MCQ choices'
                            )

                        # STEP 3: Also import to Anki (for flashcard practice, optional)
                        self.progress_callback(
                            job_id,
                            f'Importing {batch_card_count} cards to Anki...'
                        )

                        anki_imported = 0
                        for card in cards:
                            try:
                                add_note_to_anki(
                                    card['deck'],
                                    card['front'],
                                    card['back'],
                                    card['tags']
                                )
                                anki_imported += 1
                            except Exception as e:
                                # Anki import is optional - don't fail if it doesn't work
                                print(f"Warning: Failed to import card to Anki: {e}")

                        if anki_imported > 0:
                            self.progress_callback(
                                job_id,
                                f'✅ Also imported {anki_imported} cards to Anki'
                            )

                        # Use saved_count as the authoritative count
                        chunk_cards_total += saved_count
                        total_cards_overall += saved_count
                        global_sid += batch_card_count

                        # Mark topics as processed
                        for topic in unique_topics:
                            self.topic_extractor.mark_topic_processed(
                                topic['hash'],
                                parent_pdf_id,
                                chunk['chunk_id'],
                                topic['title'],
                                card_count=0  # We don't track per-topic card count
                            )

                        self.progress_callback(
                            job_id,
                            f'✅ Batch {batch_idx} complete: {saved_count} cards saved (Total: {total_cards_overall})'
                        )

                        # Calculate progress percentage
                        chunks_done = chunk_idx - 1
                        current_chunk_progress = batch_idx / len(topic_batches)
                        overall_progress = int(((chunks_done + current_chunk_progress) / len(chunks)) * 100)

                        self.jobs_db.update_progress(
                            job_id,
                            total_cards=total_cards_overall,
                            progress_percentage=min(overall_progress, 99)  # Reserve 100 for completion
                        )

                    except Exception as e:
                        self.progress_callback(
                            job_id,
                            f'❌ Batch {batch_idx} failed: {e}'
                        )
                        # Continue with next batch

                # Mark chunk as complete
                if chunk['chunk_id'] != 0:
                    self.mark_chunk_complete(chunk['chunk_id'], chunk_cards_total)

                self.progress_callback(
                    job_id,
                    f'✅ Chunk {chunk_idx} complete: {chunk_cards_total} cards'
                )

            # Mark job as complete
            self.jobs_db.mark_complete(job_id, total_cards_overall)

            self.progress_callback(
                job_id,
                f'🎉 Assessment creation complete! Generated {total_cards_overall} flashcards across {len(chunks)} chunk(s)'
            )

        except Exception as e:
            # Mark job as failed
            error_msg = str(e)
            self.jobs_db.mark_failed(job_id, error_msg)
            self.progress_callback(job_id, f'❌ Assessment creation failed: {error_msg}')
            raise


if __name__ == "__main__":
    # CLI entry point for background processing
    if len(sys.argv) < 5:
        print("Usage: python assessment_processor.py <job_id> <parent_pdf_id> <source> <week>")
        sys.exit(1)

    job_id = sys.argv[1]
    parent_pdf_id = sys.argv[2]
    source = sys.argv[3]
    week = sys.argv[4]

    print(f"Starting assessment processor for job {job_id}")
    print(f"  PDF: {parent_pdf_id}")
    print(f"  Source: {source}")
    print(f"  Week: {week}")

    processor = AssessmentProcessor()

    try:
        processor.process_pdf_assessment(job_id, parent_pdf_id, source, week)
        print(f"\n✅ Job {job_id} completed successfully")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
