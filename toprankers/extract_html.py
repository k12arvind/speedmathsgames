#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract_html.py

Extracts current affairs content from TopRankers HTML pages.
Converts HTML structure to clean text format suitable for flashcard generation.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def fetch_html_content(url: str) -> str:
    """Fetch HTML content from URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL: {e}")


def extract_date_from_url(url: str) -> str:
    """Extract date from TopRankers URL pattern."""
    # Pattern: current-affairs-19th-december-2025
    match = re.search(r'current-affairs-(\d+)(?:st|nd|rd|th)?-(\w+)-(\d{4})', url)
    if match:
        day, month, year = match.groups()
        # Convert month name to number
        months = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        month_num = months.get(month.lower(), '01')
        return f"{year}_{month.title()[:3]}_D{int(day):02d}"

    # Fallback to current date
    from datetime import datetime
    now = datetime.now()
    return f"{now.year}_{now.strftime('%b')}_D{now.day:02d}"


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def extract_topics_from_html(html_content: str) -> List[Dict[str, str]]:
    """Extract structured topics from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    topics = []

    # Find all topic headings (colored brown/maroon with strong tag)
    topic_headings = soup.find_all('span', style=lambda s: s and 'color:#a52a2a' in s.lower())

    for heading_span in topic_headings:
        strong_tag = heading_span.find('strong')
        if not strong_tag:
            continue

        topic_title = clean_text(strong_tag.get_text())
        if not topic_title or len(topic_title) < 5:
            continue

        # Find the parent element and extract following content
        parent = heading_span.find_parent(['p', 'div', 'h2', 'h3'])
        if not parent:
            continue

        # Collect content following this heading until next heading
        content_parts = []
        current_element = parent.find_next_sibling()

        while current_element:
            # Stop if we hit another topic heading
            if current_element.find('span', style=lambda s: s and 'color:#a52a2a' in s.lower()):
                break

            # Extract text from paragraphs
            if current_element.name == 'p':
                text = clean_text(current_element.get_text())
                if text and len(text) > 10:
                    content_parts.append(text)

            # Extract bullet points from lists
            elif current_element.name in ['ul', 'ol']:
                for li in current_element.find_all('li', recursive=False):
                    text = clean_text(li.get_text())
                    if text and len(text) > 5:
                        content_parts.append(f"• {text}")

            current_element = current_element.find_next_sibling()

        # Only add topic if we found content
        if content_parts:
            topics.append({
                'title': topic_title,
                'content': '\n'.join(content_parts)
            })

    return topics


def format_for_flashcard_generation(topics: List[Dict[str, str]], url: str = None) -> str:
    """Format extracted topics for flashcard generation."""
    output_parts = []

    if url:
        output_parts.append(f"Source URL: {url}\n")
        output_parts.append("="*80 + "\n\n")

    for idx, topic in enumerate(topics, 1):
        output_parts.append(f"=== TOPIC {idx}: {topic['title']} ===\n\n")
        output_parts.append(topic['content'])
        output_parts.append("\n\n" + "="*80 + "\n\n")

    return ''.join(output_parts)


def extract_html_to_text(url_or_file: str, output_path: Path = None) -> str:
    """
    Extract content from TopRankers HTML (URL or local file).
    Returns formatted text ready for flashcard generation.
    """
    # Determine if input is URL or file
    if url_or_file.startswith('http://') or url_or_file.startswith('https://'):
        print(f"🌐 Fetching content from URL...")
        html_content = fetch_html_content(url_or_file)
        source_url = url_or_file
    else:
        # Local HTML file
        file_path = Path(url_or_file).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"HTML file not found: {file_path}")

        print(f"📄 Reading HTML file: {file_path.name}")
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        source_url = None

    print("✅ HTML loaded")

    # Extract structured topics
    print("🔍 Extracting topics...")
    topics = extract_topics_from_html(html_content)
    print(f"✅ Found {len(topics)} topics")

    if not topics:
        raise ValueError("No topics found in HTML content. Check the HTML structure.")

    # Format for flashcard generation
    formatted_text = format_for_flashcard_generation(topics, source_url)

    # Save to file if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        print(f"💾 Saved extracted content to: {output_path}")

    return formatted_text


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_html.py <url_or_file> [output.txt]")
        print("\nExamples:")
        print("  python extract_html.py https://www.toprankers.com/current-affairs-19th-december-2025")
        print("  python extract_html.py inbox/page.html")
        print("  python extract_html.py inbox/page.html output.txt")
        sys.exit(1)

    url_or_file = sys.argv[1]
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("extracted_content.txt")

    print("="*60)
    print("TopRankers HTML Content Extractor")
    print("="*60 + "\n")

    try:
        extracted_text = extract_html_to_text(url_or_file, output_path)
        print(f"\n✅ Extracted {len(extracted_text)} characters")

        # Show preview
        print("\n" + "="*60)
        print("PREVIEW (first 500 characters)")
        print("="*60)
        print(extracted_text[:500])
        if len(extracted_text) > 500:
            print("\n... (truncated)")

        print("\n✅ Done!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
