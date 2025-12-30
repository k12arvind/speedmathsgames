#!/usr/bin/env python3
"""
Populate math questions database with 60 questions per topic (20 per difficulty).
Uses Anthropic API to generate high-quality math questions.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from math_module.math_db import MathDatabase

# Topics and their descriptions for AI generation
TOPICS = {
    'arithmetic': 'basic arithmetic: addition, subtraction, multiplication, division of whole numbers',
    'fractions': 'fraction operations: adding, subtracting, multiplying, dividing fractions',
    'decimals': 'decimal calculations: operations with decimal numbers',
    'equations': 'simple algebraic equations: solve for x type problems',
    'profit_loss': 'profit and loss word problems: cost price, selling price, discount',
    'bodmas': 'BODMAS/order of operations: expressions with multiple operations'
}

DIFFICULTIES = ['easy', 'medium', 'hard']
QUESTIONS_PER_BATCH = 10
TARGET_PER_DIFFICULTY = 20  # 20 per difficulty × 3 = 60 per topic

def generate_questions(client, topic: str, topic_desc: str, difficulty: str, count: int) -> list:
    """Generate math questions using Claude."""
    
    difficulty_guide = {
        'easy': 'simple problems suitable for grade 5-6, single step calculations',
        'medium': 'moderate problems for grade 7-8, may require 2-3 steps',
        'hard': 'challenging problems for grade 9-10, multi-step with reasoning'
    }
    
    prompt = f"""Generate exactly {count} {difficulty} difficulty math questions on {topic_desc}.

Difficulty level: {difficulty_guide[difficulty]}

For EACH question provide a JSON object with these exact fields:
- question_text: The math question (clear and concise)
- correct_answer: The numerical or text answer
- choice_a, choice_b, choice_c, choice_d: Four multiple choice options
- correct_choice: Which letter is correct (A, B, C, or D)
- explanation: Brief explanation of the solution

Return ONLY a valid JSON array of {count} question objects. No markdown, no extra text."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        
        # Clean markdown if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        questions = json.loads(text)
        return questions if isinstance(questions, list) else []
        
    except Exception as e:
        print(f"    ❌ Error generating: {e}")
        return []

def main():
    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set!")
        print("Run: source ~/.zshrc")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    db = MathDatabase()
    
    print("\n" + "="*60)
    print("🧮 Math Questions Generator")
    print("="*60)
    
    # Check current counts
    stats = db.get_database_stats()
    print(f"\nCurrent questions: {stats['total_questions']}")
    for topic, count in stats.get('by_topic', {}).items():
        print(f"  {topic}: {count}")
    
    total_added = 0
    
    for topic, topic_desc in TOPICS.items():
        print(f"\n📚 Topic: {topic.upper()}")
        
        for difficulty in DIFFICULTIES:
            # Check how many we already have
            current = db.count_questions(topic=topic, difficulty=difficulty)
            needed = max(0, TARGET_PER_DIFFICULTY - current)
            
            if needed == 0:
                print(f"  ✅ {difficulty}: Already have {current} questions")
                continue
            
            print(f"  🔄 {difficulty}: Have {current}, generating {needed} more...")
            
            # Generate in batches
            generated = 0
            while generated < needed:
                batch_size = min(QUESTIONS_PER_BATCH, needed - generated)
                questions = generate_questions(client, topic, topic_desc, difficulty, batch_size)
                
                if not questions:
                    print(f"    ⚠️ No questions returned, retrying...")
                    time.sleep(2)
                    continue
                
                # Add to database
                for q in questions:
                    try:
                        db.add_question(
                            topic=topic,
                            difficulty=difficulty,
                            question_text=q.get('question_text', ''),
                            correct_answer=str(q.get('correct_answer', '')),
                            choices={
                                'A': str(q.get('choice_a', '')),
                                'B': str(q.get('choice_b', '')),
                                'C': str(q.get('choice_c', '')),
                                'D': str(q.get('choice_d', ''))
                            },
                            correct_choice=q.get('correct_choice', 'A'),
                            explanation=q.get('explanation', '')
                        )
                        generated += 1
                        total_added += 1
                    except Exception as e:
                        print(f"    ⚠️ Error adding question: {e}")
                
                print(f"    Added {len(questions)} questions ({generated}/{needed})")
                time.sleep(1)  # Rate limiting
    
    # Final stats
    print("\n" + "="*60)
    print("📊 Final Statistics")
    print("="*60)
    
    stats = db.get_database_stats()
    print(f"\nTotal questions: {stats['total_questions']}")
    print("\nBy Topic:")
    for topic, count in stats.get('by_topic', {}).items():
        print(f"  {topic}: {count}")
    print("\nBy Difficulty:")
    for diff, count in stats.get('by_difficulty', {}).items():
        print(f"  {diff}: {count}")
    
    print(f"\n✅ Added {total_added} new questions!")
    db.close()

if __name__ == '__main__':
    main()

