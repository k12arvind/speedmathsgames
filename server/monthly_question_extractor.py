#!/usr/bin/env python3
"""
Monthly Question Extractor

Extracts embedded questions from Monthly CLAT Post PDFs.
Unlike daily/weekly PDFs where Claude generates questions,
Monthly PDFs already contain practice questions and answer keys.

Question Format in PDFs:
- Section headers identify category (Polity & Governance, Economy, etc.)
- PRACTICE QUESTIONS section contains numbered questions
- Each question has (a), (b), (c), (d) choices
- ANSWER KEY section provides correct answers

Usage:
    extractor = MonthlyQuestionExtractor()
    questions = extractor.extract_from_chunk(chunk_path)
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import PyPDF2


class MonthlyQuestionExtractor:
    """Extract embedded questions from Monthly CLAT Post PDFs."""

    # Category headers commonly found in CLAT Post PDFs
    CATEGORY_PATTERNS = [
        r'Polity\s*[&and]*\s*Governance',
        r'Economy',
        r'Environment',
        r'Science\s*[&and]*\s*Technology',
        r'International\s*Relations',
        r'Awards?\s*[&and]*\s*Honours?',
        r'Sports',
        r'Art\s*[&and]*\s*Culture',
        r'Current\s*Events?',
        r'Legal\s*(?:Affairs?|Updates?)',
        r'Social\s*Issues?',
    ]

    def __init__(self):
        """Initialize extractor."""
        self._compiled_category_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.CATEGORY_PATTERNS
        ]

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract all text from a PDF file."""
        text_parts = []
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}")
            return ""
        return "\n".join(text_parts)

    def extract_from_chunk(self, chunk_path: str) -> List[Dict]:
        """
        Extract questions from a chunked PDF.

        Returns list of:
        {
            'question_text': str,
            'choices': ['A', 'B', 'C', 'D'],
            'correct_index': int,  # 0-3
            'category': str  # 'Polity & Governance', etc.
        }
        """
        text = self.extract_text_from_pdf(chunk_path)
        if not text:
            return []

        questions = []

        # Try method 1: Find PRACTICE QUESTIONS sections
        practice_sections = self._find_practice_sections(text)

        if practice_sections:
            for section_text, category in practice_sections:
                # Parse questions from this section
                section_questions = self._parse_questions(section_text)

                # Try to find answer key for this section
                answer_key = self._find_answer_key_for_section(text, section_text)

                # Apply answers to questions
                for i, q in enumerate(section_questions):
                    q['category'] = category
                    # Try to get answer from key (1-indexed)
                    if answer_key and (i + 1) in answer_key:
                        q['correct_index'] = answer_key[i + 1]
                    questions.append(q)
        else:
            # Method 2: Direct extraction - questions embedded in content
            # Monthly CLAT Post format has questions inline with (a)(b)(c)(d) choices
            questions = self._extract_inline_questions(text)

        return questions

    def _extract_inline_questions(self, text: str) -> List[Dict]:
        """
        Extract questions that are embedded directly in text with (a)(b)(c)(d) choices.

        Format: "Question text here?\n(a) choice A (b) choice B (c) choice C (d) choice D"
        The questions may or may not be numbered.
        """
        questions = []

        # Pattern to match MCQ blocks: question ending with ? followed by 4 choices
        # This handles both numbered and unnumbered questions
        pattern = re.compile(
            r'([A-Z][^?]*\?)\s*'  # Question text ending with ?
            r'\(a\)\s*([^(]+)'    # Choice a
            r'\(b\)\s*([^(]+)'    # Choice b
            r'\(c\)\s*([^(]+)'    # Choice c
            r'\(d\)\s*([^(\n]+)',  # Choice d
            re.IGNORECASE | re.DOTALL
        )

        for i, match in enumerate(pattern.finditer(text)):
            question_text = match.group(1).strip()
            choice_a = match.group(2).strip()
            choice_b = match.group(3).strip()
            choice_c = match.group(4).strip()
            choice_d = match.group(5).strip()

            # Clean up question text - remove line breaks, extra whitespace
            question_text = re.sub(r'\s+', ' ', question_text).strip()

            # Skip if question is too short (likely a parsing error)
            if len(question_text) < 15:
                continue

            # Clean up choices
            choices = [
                self._clean_choice(choice_a),
                self._clean_choice(choice_b),
                self._clean_choice(choice_c),
                self._clean_choice(choice_d)
            ]

            # Skip if any choice is empty
            if not all(choices):
                continue

            # Detect category from surrounding text (look back up to 5000 chars)
            context_start = max(0, match.start() - 5000)
            context = text[context_start:match.start()]
            category = self._detect_category(context)

            questions.append({
                'question_text': question_text,
                'choices': choices,
                'correct_index': 0,  # No answer key in inline format
                'category': category,
                'question_number': i + 1
            })

        return questions

    def _clean_choice(self, choice: str) -> str:
        """Clean up a choice text - remove trailing question starts, etc."""
        # Remove any text that looks like the start of another question
        choice = re.sub(r'\n\d+\..*$', '', choice, flags=re.DOTALL)
        # Remove excess whitespace
        choice = re.sub(r'\s+', ' ', choice).strip()
        return choice

    def _find_practice_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Find all PRACTICE QUESTIONS sections and their categories.

        Returns list of (section_text, category_name) tuples.
        """
        sections = []

        # Pattern to find PRACTICE QUESTIONS header
        practice_pattern = re.compile(
            r'PRACTICE\s*QUESTIONS?',
            re.IGNORECASE
        )

        # Find all practice question sections
        matches = list(practice_pattern.finditer(text))

        for i, match in enumerate(matches):
            start_pos = match.start()

            # End is either next PRACTICE QUESTIONS or ANSWER KEY or end of text
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                # Try to find ANSWER KEY
                answer_key_match = re.search(
                    r'ANSWER\s*KEY',
                    text[start_pos:],
                    re.IGNORECASE
                )
                if answer_key_match:
                    end_pos = start_pos + answer_key_match.end() + 500  # Include answer key
                else:
                    end_pos = len(text)

            section_text = text[start_pos:end_pos]

            # Detect category by looking at text before this section
            # Look back up to 2000 characters for a category header
            lookback_start = max(0, start_pos - 2000)
            lookback_text = text[lookback_start:start_pos]
            category = self._detect_category(lookback_text)

            sections.append((section_text, category))

        return sections

    def _parse_questions(self, section_text: str) -> List[Dict]:
        """Parse numbered questions with choices from a section."""
        questions = []

        # Pattern to match numbered questions
        # Format: "1. Question text here?\n   (a) choice A    (b) choice B..."
        question_pattern = re.compile(
            r'(\d+)\.\s*(.+?)(?=\n\s*(?:\d+\.|ANSWER|$))',
            re.DOTALL
        )

        for match in question_pattern.finditer(section_text):
            q_num = int(match.group(1))
            q_text = match.group(2).strip()

            # Parse choices from the question text
            choices, question_only = self._extract_choices(q_text)

            if len(choices) >= 2:  # At least 2 choices for a valid MCQ
                questions.append({
                    'question_text': question_only.strip(),
                    'choices': choices,
                    'correct_index': 0,  # Default, will be updated from answer key
                    'question_number': q_num
                })

        return questions

    def _extract_choices(self, text: str) -> Tuple[List[str], str]:
        """
        Extract choices (a), (b), (c), (d) from question text.

        Returns (list of choices, question text without choices).
        """
        choices = []

        # Pattern for choices: (a) text  or  a) text  or  A. text
        choice_patterns = [
            # Standard: (a) choice text
            r'\(([a-dA-D])\)\s*([^()\n]+?)(?=\s*\([a-dA-D]\)|\s*$)',
            # Alternative: a) choice text
            r'(?:^|\s)([a-dA-D])\)\s*([^()\n]+?)(?=\s*[a-dA-D]\)|\s*$)',
            # With periods: a. choice text
            r'(?:^|\s)([a-dA-D])\.\s*([^.\n]+?)(?=\s*[a-dA-D]\.|\s*$)',
        ]

        # Try each pattern
        for pattern in choice_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            if matches:
                choices = [m.group(2).strip() for m in matches]
                break

        # If we found choices, extract question text (before first choice)
        if choices:
            first_choice_match = re.search(r'\([a-dA-D]\)', text, re.IGNORECASE)
            if first_choice_match:
                question_only = text[:first_choice_match.start()].strip()
            else:
                question_only = text
        else:
            question_only = text

        # Clean up question text
        question_only = re.sub(r'\s+', ' ', question_only).strip()

        # Ensure we have exactly 4 choices, pad with empty if needed
        while len(choices) < 4:
            choices.append('')
        choices = choices[:4]  # Limit to 4

        return choices, question_only

    def _find_answer_key_for_section(self, full_text: str, section_text: str) -> Dict[int, int]:
        """
        Find and parse ANSWER KEY to get correct answers.

        Returns dict mapping question_number -> correct_index (0-3).
        """
        # Find ANSWER KEY section
        answer_key_match = re.search(
            r'ANSWER\s*KEY[^\n]*\n(.+?)(?=\n\s*\n\s*[A-Z]|$)',
            full_text,
            re.IGNORECASE | re.DOTALL
        )

        if not answer_key_match:
            return {}

        answer_text = answer_key_match.group(1)

        # Parse answer key format: "1. (d)  2. (a)  3. (b)..."
        # or: "1-d  2-a  3-b..."
        # or: "1.d  2.a  3.b..."
        answers = {}

        # Pattern: number followed by letter
        answer_pattern = re.compile(
            r'(\d+)\s*[\.\-\)]\s*\(?([a-dA-D])\)?',
            re.IGNORECASE
        )

        for match in answer_pattern.finditer(answer_text):
            q_num = int(match.group(1))
            answer_letter = match.group(2).lower()
            # Convert letter to index: a=0, b=1, c=2, d=3
            answer_index = ord(answer_letter) - ord('a')
            answers[q_num] = answer_index

        return answers

    def _detect_category(self, text: str) -> str:
        """Detect category from section headers."""
        # Look for category headers in the text (find the last/most recent one)
        last_match = None
        last_pos = -1

        for pattern in self._compiled_category_patterns:
            for match in pattern.finditer(text):
                if match.start() > last_pos:
                    last_pos = match.start()
                    last_match = match

        if last_match:
            # Normalize the category name
            cat = last_match.group(0).strip()
            # Title case and normalize
            cat = cat.title().replace('  ', ' ')
            cat = cat.replace(' And ', ' & ')
            return cat

        return "General Knowledge"  # Default category


def extract_questions_from_monthly_chunk(chunk_path: str) -> List[Dict]:
    """
    Convenience function to extract questions from a monthly PDF chunk.

    Args:
        chunk_path: Path to the chunked PDF file

    Returns:
        List of question dictionaries
    """
    extractor = MonthlyQuestionExtractor()
    return extractor.extract_from_chunk(chunk_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python monthly_question_extractor.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"Extracting questions from: {pdf_path}")
    extractor = MonthlyQuestionExtractor()
    questions = extractor.extract_from_chunk(pdf_path)

    print(f"\nFound {len(questions)} questions:\n")
    for i, q in enumerate(questions, 1):
        print(f"Q{i}. {q['question_text'][:100]}...")
        print(f"    Category: {q['category']}")
        print(f"    Choices: {len(q['choices'])} options")
        print(f"    Correct: {chr(ord('a') + q['correct_index'])}")
        print()
