"""
Book Practice Module for RS Aggarwal Question Bank

This module provides:
- Database operations for book questions, topics, and practice sessions
- Image extraction using Claude Vision API
- Spaced repetition and mastery tracking
"""

from .book_db import BookPracticeDB
from .image_extractor import BookImageExtractor, save_uploaded_image, compress_image

__all__ = ['BookPracticeDB', 'BookImageExtractor', 'save_uploaded_image', 'compress_image']
