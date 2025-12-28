#!/usr/bin/env python3
"""
One-time script to generate MCQ choices for all questions that don't have them.
This will make all future tests instant (no on-demand generation).
"""

import os
import sys
import json
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from server.questions_db import QuestionsDatabase

def generate_choices_batch(client, questions: list) -> dict:
    """Generate MCQ choices for a batch of questions using Claude API."""
    
    # Prepare batch prompt
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

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",  # Faster model for simple distractor generation
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
                    # Create choices with correct answer at random position
                    import random
                    correct_answer = questions[idx]['answer']
                    choices = distractors[:3] + [correct_answer]
                    random.shuffle(choices)
                    correct_index = choices.index(correct_answer)
                    
                    output[idx] = {
                        'choices': choices,
                        'correct_index': correct_index
                    }
        
        return output
        
    except Exception as e:
        print(f"    ❌ Error generating choices: {e}")
        return {}


def main():
    print("=" * 60)
    print("🚀 Generating MCQ Choices for All Questions")
    print("=" * 60)
    
    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set!")
        print("   Run: source ~/.zshrc")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    questions_db = QuestionsDatabase()
    
    # Get questions without choices
    conn = questions_db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT q.question_id, q.question_text, q.answer_text, q.category, q.pdf_filename
        FROM questions q
        WHERE q.question_id NOT IN (SELECT question_id FROM question_choices)
        ORDER BY q.question_id
    """)
    
    questions_without_choices = []
    for row in cursor.fetchall():
        questions_without_choices.append({
            'question_id': row['question_id'],
            'question': row['question_text'],
            'answer': row['answer_text'],
            'category': row['category'],
            'pdf_filename': row['pdf_filename']
        })
    
    conn.close()
    
    total = len(questions_without_choices)
    print(f"\n📊 Found {total} questions without choices")
    
    if total == 0:
        print("✅ All questions already have choices!")
        return
    
    # Process in batches - LARGER batches = FASTER
    batch_size = 25  # Increased from 10 to 25
    processed = 0
    success = 0
    failed = 0
    
    print(f"\n⏱️  Processing in batches of {batch_size} (optimized for speed)...")
    print(f"   Estimated time: {(total // batch_size) * 4} seconds\n")
    
    start_time = time.time()
    
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = questions_without_choices[batch_start:batch_end]
        
        print(f"📦 Batch {batch_start//batch_size + 1}/{(total + batch_size - 1)//batch_size}: Questions {batch_start+1}-{batch_end}")
        
        results = generate_choices_batch(client, batch)
        
        # Save results
        for local_idx, choices_data in results.items():
            question = batch[local_idx]
            question_id = question['question_id']
            
            saved = questions_db.save_mcq_choices(
                question_id=question_id,
                choices=choices_data['choices'],
                correct_index=choices_data['correct_index']
            )
            
            if saved:
                success += 1
            else:
                failed += 1
        
        batch_failed = len(batch) - len(results)
        failed += batch_failed
        
        processed += len(batch)
        
        # Progress
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (total - processed) / rate if rate > 0 else 0
        
        print(f"   ✅ Generated: {len(results)}/{len(batch)} | Total: {success}/{processed} | ETA: {int(remaining)}s")
        
        # Rate limiting - minimal delay (Claude API handles its own rate limits)
        if batch_end < total:
            time.sleep(0.5)
    
    elapsed_total = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"   Total questions processed: {processed}")
    print(f"   Successfully generated: {success}")
    print(f"   Failed: {failed}")
    print(f"   Time taken: {int(elapsed_total)}s ({elapsed_total/60:.1f} minutes)")
    print(f"   Rate: {processed/elapsed_total:.1f} questions/second")
    print("=" * 60)
    
    # Verify
    cursor = questions_db._get_connection().cursor()
    cursor.execute("SELECT COUNT(*) FROM question_choices")
    final_count = cursor.fetchone()[0]
    print(f"\n✅ Total questions with choices now: {final_count}")


if __name__ == "__main__":
    main()

