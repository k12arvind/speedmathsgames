"""
Image Extractor Module for Book Practice
Uses Claude Vision API to extract questions from book page images
"""

import base64
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from anthropic import Anthropic
import os

# Math notation conversion mapping
MATH_CONVERSIONS = {
    '1/2': '½', '1/3': '⅓', '1/4': '¼', '2/3': '⅔', '3/4': '¾',
    '1/5': '⅕', '2/5': '⅖', '3/5': '⅗', '4/5': '⅘',
    '1/6': '⅙', '5/6': '⅚', '1/7': '⅐', '1/8': '⅛', '3/8': '⅜',
    '5/8': '⅝', '7/8': '⅞', '1/9': '⅑', '1/10': '⅒',
    '^2': '²', '^3': '³', '^4': '⁴', '^5': '⁵',
    '^6': '⁶', '^7': '⁷', '^8': '⁸', '^9': '⁹', '^0': '⁰',
    '^n': 'ⁿ', '^-1': '⁻¹', '^-2': '⁻²',
    '_0': '₀', '_1': '₁', '_2': '₂', '_3': '₃', '_4': '₄',
    '_5': '₅', '_6': '₆', '_7': '₇', '_8': '₈', '_9': '₉',
    'sqrt': '√', 'infinity': '∞', 'pi': 'π',
    '>=': '≥', '<=': '≤', '!=': '≠', '~=': '≈',
    '+-': '±', '-+': '∓',
}


class BookImageExtractor:
    """Extracts questions from book page images using Claude Vision API"""

    EXTRACTION_PROMPT = """Extract information from this textbook page from RS Aggarwal's Quantitative Aptitude book.

FIRST, look at the page header/top for:
1. Page number (usually in the corner, e.g., "487" or "■ 487")
2. Topic/Chapter name (e.g., "Alligation or Mixture", "Time and Work", "Percentage")

THEN, extract all questions marked with a tick (✓), check mark, or any hand-drawn mark next to them.

For each marked question, provide:
- question_number: The question number (e.g., 17, 18)
- question_text: The full question text
  - Convert fractions to Unicode where possible: 3/5 → ⅗, 1/2 → ½, 1/4 → ¼, 2/3 → ⅔, 3/4 → ¾
  - Use × for multiplication, ÷ for division
  - Use superscript for powers: x² not x^2, m³ not m^3
  - Keep ratios as "3 : 5" (with spaces)
  - Keep decimal numbers as-is
- choices: Answer options as object {a, b, c, d} or {a, b, c, d, e}
  - Each choice should be the exact text after the option letter
  - Apply same Unicode conversions to choices
- source_exam: If visible (e.g., "IBPS PO Prelims 23/09/2023", "SSC CGL", "CAT 2022")

IMPORTANT:
- Include ANY question with a visible mark next to it (tick, check, pencil mark, pen mark)
- Look carefully for marks - they may be in pencil, pen, or highlighter
- Preserve all mathematical notation and symbols accurately

Return ONLY valid JSON in this exact format:
{
  "page_number": 487,
  "topic_name": "Alligation or Mixture",
  "questions": [
    {
      "question_number": 17,
      "question_text": "The full question text here...",
      "choices": {
        "a": "Option A text",
        "b": "Option B text",
        "c": "Option C text",
        "d": "Option D text"
      },
      "source_exam": "IBPS PO 2023"
    }
  ]
}

If page_number or topic_name not visible, use null.
If no marked questions found, return: {"page_number": null, "topic_name": null, "questions": []}"""

    ANSWER_KEY_PROMPT = """Extract answers from this answer key page.
This is an answer key page from RS Aggarwal's book.

For each answer visible, extract:
- The question number
- The correct answer choice (a, b, c, d, or e)

Return ONLY a valid JSON object mapping question numbers to correct answers.
Format:
{
  "1": "b",
  "2": "a",
  "3": "d",
  "17": "c"
}

Only include answers that are clearly visible on this page."""

    def __init__(self, api_key: str = None):
        """Initialize the extractor with Anthropic API key"""
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=self.api_key)

    def extract_questions(self, image_path: str) -> Tuple[Dict, str]:
        """
        Extract questions from a book page image

        Returns:
            Tuple of (result_dict, raw_response)
            result_dict contains: page_number, topic_name, questions
        """
        # Read and encode the image
        image_data = self._encode_image(image_path)
        if not image_data:
            return {'page_number': None, 'topic_name': None, 'questions': []}, "Error: Could not read image file"

        # Determine media type
        media_type = self._get_media_type(image_path)

        try:
            # Call Claude Vision API
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": self.EXTRACTION_PROMPT
                            }
                        ]
                    }
                ]
            )

            raw_response = response.content[0].text

            # Parse the JSON response - now expecting object with page_number, topic_name, questions
            result = self._parse_extraction_response(raw_response)

            # Apply math conversions to questions
            for q in result.get('questions', []):
                q['question_text'] = self._apply_math_conversions(q.get('question_text', ''))
                if 'choices' in q:
                    for key in q['choices']:
                        q['choices'][key] = self._apply_math_conversions(q['choices'][key])

            return result, raw_response

        except Exception as e:
            return {'page_number': None, 'topic_name': None, 'questions': []}, f"Error: {str(e)}"

    def _parse_extraction_response(self, raw_response: str) -> Dict:
        """Parse the extraction response which includes page_number, topic_name, and questions"""
        # Try to find JSON in the response
        text = raw_response.strip()

        # Remove markdown code blocks if present
        if text.startswith('```'):
            lines = text.split('\n')
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's just ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines)

        try:
            data = json.loads(text)
            # Handle new format
            if isinstance(data, dict) and 'questions' in data:
                return {
                    'page_number': data.get('page_number'),
                    'topic_name': data.get('topic_name'),
                    'questions': data.get('questions', [])
                }
            # Handle old format (array of questions)
            elif isinstance(data, list):
                return {
                    'page_number': None,
                    'topic_name': None,
                    'questions': data
                }
            return {'page_number': None, 'topic_name': None, 'questions': []}
        except json.JSONDecodeError:
            # Try to extract JSON from text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start:end])
                    if isinstance(data, dict) and 'questions' in data:
                        return {
                            'page_number': data.get('page_number'),
                            'topic_name': data.get('topic_name'),
                            'questions': data.get('questions', [])
                        }
                except json.JSONDecodeError:
                    pass
            return {'page_number': None, 'topic_name': None, 'questions': []}

    def extract_answers(self, image_path: str) -> Tuple[Dict[int, str], str]:
        """
        Extract answers from an answer key page

        Returns:
            Tuple of (answers_dict, raw_response)
        """
        image_data = self._encode_image(image_path)
        if not image_data:
            return {}, "Error: Could not read image file"

        media_type = self._get_media_type(image_path)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": self.ANSWER_KEY_PROMPT
                            }
                        ]
                    }
                ]
            )

            raw_response = response.content[0].text

            # Parse the JSON response
            answers = self._parse_answer_response(raw_response)

            return answers, raw_response

        except Exception as e:
            return {}, f"Error: {str(e)}"

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Read and base64 encode an image file"""
        try:
            path = Path(image_path)
            if not path.exists():
                return None

            with open(path, 'rb') as f:
                return base64.standard_b64encode(f.read()).decode('utf-8')
        except Exception:
            return None

    def _get_media_type(self, image_path: str) -> str:
        """Determine the MIME type of an image"""
        ext = Path(image_path).suffix.lower()
        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.heif': 'image/heif',
        }
        return media_types.get(ext, 'image/jpeg')

    def _parse_json_response(self, response: str) -> List[Dict]:
        """Parse JSON array from Claude's response"""
        # Try to find JSON array in the response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith('```'):
            lines = response.split('\n')
            # Remove first and last lines (```json and ```)
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith('```') and not in_json:
                    in_json = True
                    continue
                elif line.startswith('```') and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response = '\n'.join(json_lines)

        # Try to find array brackets
        start_idx = response.find('[')
        end_idx = response.rfind(']')

        if start_idx != -1 and end_idx != -1:
            json_str = response[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # Try parsing the whole response
        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        return []

    def _parse_answer_response(self, response: str) -> Dict[int, str]:
        """Parse answer key JSON from Claude's response"""
        response = response.strip()

        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith('```') and not in_json:
                    in_json = True
                    continue
                elif line.startswith('```') and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response = '\n'.join(json_lines)

        # Try to find object brackets
        start_idx = response.find('{')
        end_idx = response.rfind('}')

        if start_idx != -1 and end_idx != -1:
            json_str = response[start_idx:end_idx + 1]
            try:
                raw_answers = json.loads(json_str)
                # Convert string keys to integers
                return {int(k): v.lower() for k, v in raw_answers.items()}
            except (json.JSONDecodeError, ValueError):
                pass

        return {}

    def _apply_math_conversions(self, text: str) -> str:
        """Apply Unicode math conversions to text"""
        if not text:
            return text

        result = text

        # Apply direct conversions
        for pattern, replacement in MATH_CONVERSIONS.items():
            result = result.replace(pattern, replacement)

        # Convert remaining simple fractions like 3/5, 7/8, etc.
        # that aren't in our mapping
        result = self._convert_fraction_notation(result)

        return result

    def _convert_fraction_notation(self, text: str) -> str:
        """Convert fraction notation where possible"""
        # This handles cases not in MATH_CONVERSIONS
        # For complex fractions, we keep the a/b notation
        return text


def save_uploaded_image(file_data: bytes, topic_id: int, page_number: int = None,
                        is_answer_key: bool = False, upload_dir: str = None) -> str:
    """
    Save an uploaded image file and return the path

    Args:
        file_data: Raw bytes of the uploaded file
        topic_id: ID of the topic this page belongs to
        page_number: Optional page number
        is_answer_key: Whether this is an answer key page
        upload_dir: Base directory for uploads

    Returns:
        Path to the saved file
    """
    if upload_dir is None:
        upload_dir = Path(__file__).parent / 'uploads'
    else:
        upload_dir = Path(upload_dir)

    # Choose subdirectory
    if is_answer_key:
        subdir = upload_dir / 'answer_keys'
    else:
        subdir = upload_dir / 'pages'

    # Ensure directory exists
    subdir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    import time
    timestamp = int(time.time() * 1000)
    if page_number:
        filename = f"topic_{topic_id}_page_{page_number}_{timestamp}.jpg"
    else:
        filename = f"topic_{topic_id}_{timestamp}.jpg"

    filepath = subdir / filename

    # Save the file
    with open(filepath, 'wb') as f:
        f.write(file_data)

    return str(filepath)


def compress_image(image_path: str, max_width: int = 1920) -> str:
    """
    Compress image to reduce size while maintaining quality

    Args:
        image_path: Path to the original image
        max_width: Maximum width in pixels

    Returns:
        Path to compressed image (may be same as original if no compression needed)
    """
    try:
        from PIL import Image

        img = Image.open(image_path)

        # Only resize if larger than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save with good quality
            output_path = image_path.rsplit('.', 1)[0] + '_compressed.jpg'
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            return output_path

        return image_path

    except ImportError:
        # PIL not available, return original
        return image_path
    except Exception:
        return image_path
