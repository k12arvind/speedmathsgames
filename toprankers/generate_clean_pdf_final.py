#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_clean_pdf_final.py

Generates clean PDF from TopRankers with inferred category headings
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.colors import HexColor

# Import HTML extraction
from extract_html import fetch_html_content, extract_topics_from_html


def extract_date_from_url(url: str) -> str:
    """Extract readable date from URL."""
    match = re.search(r'current-affairs-(\d+)(?:st|nd|rd|th)?-(\w+)-(\d{4})', url)
    if match:
        day, month, year = match.groups()
        return f"{int(day)} {month.title()} {year}"
    return datetime.now().strftime("%d %B %Y")


def infer_category(topic_title: str, topic_content: str) -> str:
    """Infer category from topic title and content using keywords."""

    combined_text = (topic_title + " " + topic_content).lower()

    # Category keywords mapping
    category_patterns = {
        'National': ['india', 'delhi', 'ministry', 'prime minister', 'cabinet', 'government',
                     'parliament', 'lok sabha', 'rajya sabha', 'scheme', 'yojana', 'national'],
        'International': ['country', 'nation', 'world', 'global', 'foreign', 'agreement',
                         'treaty', 'embassy', 'international', 'bilateral', 'summit', 'un', 'united nations'],
        'Environment': ['environment', 'climate', 'forest', 'wildlife', 'pollution', 'ecology',
                       'green', 'carbon', 'emission', 'biodiversity', 'conservation', 'hills', 'mining'],
        'Economy': ['economy', 'economic', 'gdp', 'inflation', 'finance', 'bank', 'fiscal',
                   'budget', 'investment', 'market', 'trade', 'rupee', 'currency', 'banknote', 'rial', 'polymer'],
        'Sports': ['sport', 'game', 'championship', 'tournament', 'athlete', 'player', 'medal',
                  'olympic', 'cricket', 'football', 'tennis'],
        'Awards': ['award', 'prize', 'honour', 'recognition', 'chevalier', 'confer', 'felicitate', 'medal'],
        'Defence': ['defence', 'defense', 'military', 'army', 'navy', 'air force', 'soldier',
                   'weapon', 'security', 'border'],
        'Polity': ['polity', 'constitution', 'law', 'court', 'justice', 'judicial', 'legal',
                  'rights', 'fundamental', 'amendment', 'supreme court', 'high court'],
        'Education': ['education', 'university', 'college', 'student', 'academic', 'school',
                     'learning', 'institution', 'iit', 'niti', 'internationalisation'],
        'Science & Technology': ['science', 'technology', 'research', 'innovation', 'discovery',
                                'satellite', 'space', 'digital', 'ai', 'artificial intelligence'],
        'Health': ['health', 'medical', 'hospital', 'disease', 'medicine', 'healthcare', 'doctor']
    }

    # Score each category
    scores = {}
    for category, keywords in category_patterns.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        if score > 0:
            scores[category] = score

    # Return category with highest score
    if scores:
        return max(scores, key=scores.get)

    return 'General'


def group_topics_by_category(topics: list) -> dict:
    """Group topics by inferred categories."""
    categorized = {}

    for topic in topics:
        category = infer_category(topic['title'], topic['content'])

        if category not in categorized:
            categorized[category] = []

        categorized[category].append(topic)

    # Sort categories in preferred order
    category_order = ['National', 'International', 'Environment', 'Economy',
                     'Sports', 'Awards', 'Defence', 'Polity', 'Education',
                     'Science & Technology', 'Health', 'General']

    ordered = {}
    for cat in category_order:
        if cat in categorized:
            ordered[cat] = categorized[cat]

    return ordered


def create_pdf_from_url(url: str, output_path: Path):
    """Generate clean PDF with categories from TopRankers URL."""

    print("="*60)
    print("TopRankers Clean PDF Generator (with Categories)")
    print("="*60 + "\n")

    # Fetch and extract content
    print(f"🌐 Fetching content from URL...")
    html_content = fetch_html_content(url)
    print("✅ HTML loaded")

    print("🔍 Extracting topics...")
    topics = extract_topics_from_html(html_content)
    print(f"✅ Found {len(topics)} topics")

    if not topics:
        raise ValueError("No topics found in HTML content")

    # Group by category
    print("📂 Categorizing topics...")
    categories = group_topics_by_category(topics)
    print(f"✅ Organized into {len(categories)} categories")

    # Extract date from URL
    date_str = extract_date_from_url(url)

    # Create PDF
    print(f"\n📄 Creating PDF...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Set up PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Build styles
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#2c3e50'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    # Date style
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )

    # Category box style
    category_box_style = ParagraphStyle(
        'CategoryBox',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=HexColor('#FFFFFF'),
        spaceAfter=15,
        spaceBefore=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )

    # Topic heading style
    topic_style = ParagraphStyle(
        'TopicHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=HexColor('#c0392b'),
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    # Body text style
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#2c3e50'),
        spaceAfter=7,
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        leading=14
    )

    # Bullet style
    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#34495e'),
        spaceAfter=6,
        leftIndent=20,
        fontName='Helvetica',
        leading=12
    )

    # Build content
    story = []

    # Add title
    story.append(Paragraph("Daily Current Affairs", title_style))
    story.append(Paragraph(date_str, date_style))
    story.append(Spacer(1, 0.1*inch))

    # Add content by category
    for category_name, topic_list in categories.items():
        # Category heading as colored box
        # Create a table with colored background for the category
        category_table = Table(
            [[Paragraph(f"<b>{category_name}</b>", category_box_style)]],
            colWidths=[6.5*inch]
        )
        category_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#d35400')),  # Orange background
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        story.append(category_table)
        story.append(Spacer(1, 0.15*inch))

        # Add topics in this category
        for topic in topic_list:
            # Topic heading
            topic_title = topic['title'].strip()
            topic_title = topic_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(topic_title, topic_style))

            # Topic content
            content = topic['content'].strip()
            lines = content.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                if line.startswith('•'):
                    bullet_text = line[1:].strip()
                    story.append(Paragraph(f"• {bullet_text}", bullet_style))
                else:
                    story.append(Paragraph(line, body_style))

            story.append(Spacer(1, 0.12*inch))

    # Add footer
    story.append(Spacer(1, 0.3*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#95a5a6'),
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    story.append(Paragraph(f"Source: TopRankers.com | Generated on {datetime.now().strftime('%d %B %Y')}", footer_style))

    # Build PDF
    doc.build(story)

    print(f"✅ PDF created successfully!")
    print(f"\n📁 Saved to: {output_path}")
    print(f"📊 File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"📂 Categories: {', '.join(categories.keys())}")
    print(f"📝 Total topics: {len(topics)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_clean_pdf_final.py <url> [output_path]")
        print("\nExamples:")
        print("  python generate_clean_pdf_final.py https://www.toprankers.com/current-affairs-23rd-december-2025")
        sys.exit(1)

    url = sys.argv[1]

    # Default output path
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2]).expanduser().resolve()
    else:
        date_match = re.search(r'(\d+)(?:st|nd|rd|th)?-(\w+)-(\d{4})', url)
        if date_match:
            day, month, year = date_match.groups()
            filename = f"current_affairs_{year}_{month}_{day}.pdf"
        else:
            filename = f"current_affairs_{datetime.now().strftime('%Y_%m_%d')}.pdf"

        output_path = Path.home() / "saanvi" / "Legaledgedailygk" / filename

    try:
        create_pdf_from_url(url, output_path)
        print("\n✅ Done!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
