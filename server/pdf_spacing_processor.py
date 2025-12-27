#!/usr/bin/env python3
"""
PDF Spacing Processor
Adds spacing between lines and paragraphs to make PDFs easier to annotate.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Optional
import os


class PdfSpacingProcessor:
    """Process PDFs to add spacing for easier annotation."""

    def __init__(self):
        self.line_spacing_factor = 2.0  # 2x line spacing
        self.paragraph_spacing_lines = 6  # 6 blank lines between paragraphs
        self.top_margin_lines = 5  # 5 lines margin at top
        self.bottom_margin_lines = 5  # 5 lines margin at bottom

    def needs_processing(self, pdf_path: str) -> bool:
        """
        Check if PDF needs spacing processing.

        Returns True if filename doesn't end with '_s.pdf'
        """
        path = Path(pdf_path)
        return not path.stem.endswith('_s')

    def get_output_path(self, pdf_path: str) -> str:
        """
        Get output path with _s suffix.

        Example: 'file.pdf' -> 'file_s.pdf'
        """
        path = Path(pdf_path)
        new_name = f"{path.stem}_s{path.suffix}"
        return str(path.parent / new_name)

    def process_pdf(self, input_path: str, output_path: Optional[str] = None) -> Dict:
        """
        Process PDF to add spacing for annotations.

        Args:
            input_path: Input PDF path
            output_path: Output PDF path (auto-generated if None)

        Returns:
            Dict with processing stats
        """
        if output_path is None:
            output_path = self.get_output_path(input_path)

        # Check if already processed
        if Path(output_path).exists():
            return {
                'status': 'already_exists',
                'input_path': input_path,
                'output_path': output_path,
                'message': 'Spaced PDF already exists'
            }

        try:
            # Open input PDF
            doc = fitz.open(input_path)

            # Create new PDF with spacing
            output_doc = fitz.open()

            # Standard page size (A4)
            page_width = 595  # A4 width in points
            page_height = 842  # A4 height in points

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract text with layout preserved
                text_dict = page.get_text("dict")

                # Create new page(s) with spacing
                self._process_page_with_spacing(
                    output_doc,
                    text_dict,
                    page_width,
                    page_height
                )

            # Save output
            output_doc.save(output_path)
            output_doc.close()
            doc.close()

            return {
                'status': 'success',
                'input_path': input_path,
                'output_path': output_path,
                'pages': len(doc),
                'message': f'Successfully processed {len(doc)} pages'
            }

        except Exception as e:
            return {
                'status': 'error',
                'input_path': input_path,
                'output_path': output_path,
                'error': str(e),
                'message': f'Failed to process PDF: {e}'
            }

    def _process_page_with_spacing(self, output_doc, text_dict, page_width, page_height):
        """
        Process a single page and add it to output with spacing.
        """
        # Create new page
        new_page = output_doc.new_page(width=page_width, height=page_height)

        # Calculate margins
        base_font_size = 12
        line_height = base_font_size * 1.2

        top_margin = self.top_margin_lines * line_height
        bottom_margin = page_height - (self.bottom_margin_lines * line_height)
        left_margin = 50
        right_margin = page_width - 50

        y_position = top_margin
        last_y = None

        # Extract blocks (paragraphs)
        blocks = text_dict.get("blocks", [])

        for block in blocks:
            if block.get("type") == 0:  # Text block
                # Get lines in block
                lines = []
                for line_data in block.get("lines", []):
                    line_text = ""
                    for span in line_data.get("spans", []):
                        line_text += span.get("text", "")
                    if line_text.strip():
                        lines.append({
                            'text': line_text,
                            'font_size': span.get("size", base_font_size)
                        })

                # Add paragraph spacing if this is a new paragraph
                if last_y is not None:
                    paragraph_gap = self.paragraph_spacing_lines * line_height
                    y_position += paragraph_gap

                # Add lines with line spacing
                for line_info in lines:
                    # Check if we need a new page
                    if y_position + line_height > bottom_margin:
                        # Create new page
                        new_page = output_doc.new_page(width=page_width, height=page_height)
                        y_position = top_margin

                    # Insert text
                    new_page.insert_text(
                        (left_margin, y_position),
                        line_info['text'],
                        fontsize=line_info['font_size']
                    )

                    # Add line spacing
                    y_position += line_height * self.line_spacing_factor
                    last_y = y_position

    def process_folder(self, folder_path: str, recursive: bool = False) -> Dict:
        """
        Process all PDFs in a folder that need spacing.

        Args:
            folder_path: Folder to process
            recursive: Process subfolders

        Returns:
            Dict with processing stats
        """
        folder = Path(folder_path)

        if not folder.exists():
            return {
                'status': 'error',
                'message': f'Folder not found: {folder_path}'
            }

        # Find PDFs that need processing
        pattern = "**/*.pdf" if recursive else "*.pdf"
        all_pdfs = list(folder.glob(pattern))

        # Filter out already processed (_s.pdf files)
        pdfs_to_process = [
            str(pdf) for pdf in all_pdfs
            if self.needs_processing(str(pdf))
        ]

        if not pdfs_to_process:
            return {
                'status': 'success',
                'message': 'No PDFs need processing',
                'processed': 0,
                'skipped': len(all_pdfs)
            }

        # Process each PDF
        results = []
        for pdf_path in pdfs_to_process:
            result = self.process_pdf(pdf_path)
            results.append(result)

        # Compile stats
        successful = len([r for r in results if r['status'] == 'success'])
        failed = len([r for r in results if r['status'] == 'error'])

        return {
            'status': 'success',
            'folder': folder_path,
            'total': len(pdfs_to_process),
            'processed': successful,
            'failed': failed,
            'results': results
        }


def process_daily_pdfs():
    """Process all daily PDFs."""
    processor = PdfSpacingProcessor()

    # Daily PDF folder (adjust path as needed)
    daily_folder = Path.home() / "Desktop" / "saanvi" / "Legaledgedailygk"

    if not daily_folder.exists():
        print(f"Daily folder not found: {daily_folder}")
        return

    print(f"Processing daily PDFs in: {daily_folder}")
    result = processor.process_folder(str(daily_folder))

    print(f"\nResults:")
    print(f"  Total PDFs to process: {result.get('total', 0)}")
    print(f"  Successfully processed: {result.get('processed', 0)}")
    print(f"  Failed: {result.get('failed', 0)}")

    if result.get('results'):
        print("\nDetails:")
        for r in result['results']:
            if r['status'] == 'success':
                print(f"  ✅ {Path(r['input_path']).name} -> {Path(r['output_path']).name}")
            else:
                print(f"  ❌ {Path(r['input_path']).name}: {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    process_daily_pdfs()
