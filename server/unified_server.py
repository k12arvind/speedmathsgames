#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unified_server.py

Unified HTTP server that combines:
- Dashboard HTML serving (with optional Google OAuth)
- Assessment API endpoints
- Math API endpoints
- GK Dashboard API endpoints

Single server on port 8001 for everything.
"""

from http.server import SimpleHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs
import argparse
import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import traceback

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # .env is in parent directory (clat_preparation/)
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    print("Warning: python-dotenv not installed. Environment variables must be set manually.")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import authentication (optional)
try:
    from auth.google_auth import GoogleAuth
    from auth.user_db import UserDatabase
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False

# Import API handlers (from server directory)
from server.assessment_database import AssessmentDatabase
from server.anki_connector import AnkiConnector
from anthropic import Anthropic

# Import math database
from math_module.math_db import MathDatabase

# Import PDF scanner for GK dashboard
from server.pdf_scanner import PDFScanner

# Import processing jobs database for progress tracking
from server.processing_jobs_db import ProcessingJobsDB

# Import annotation manager for PDF annotation feature
from server.annotation_manager import AnnotationManager

# Import PDF chunker for PDF splitting
from server.pdf_chunker import PdfChunker

# Import assessment jobs database for assessment creation tracking
from server.assessment_jobs_db import AssessmentJobsDB


class UnifiedHandler(SimpleHTTPRequestHandler):
    """Unified HTTP handler with all APIs and authentication."""

    # Shared instances (set by server initialization)
    google_auth = None
    user_db = None
    assessment_db = None
    anki = None
    anthropic = None
    math_db = None
    pdf_scanner = None
    processing_db = None
    annotation_manager = None
    pdf_chunker = None
    assessment_jobs_db = None

    # Public pages that don't require authentication
    PUBLIC_PAGES = [
        '/login.html',
        '/privacy_policy.html',
        '/auth/login',
        '/auth/google/callback',
        '/auth/logout'
    ]

    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from (dashboard folder)
        dashboard_dir = Path(__file__).parent.parent / 'dashboard'
        super().__init__(*args, directory=str(dashboard_dir), **kwargs)

    def end_headers(self):
        """Add CORS headers and cache-busting headers to all responses."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Cache-busting headers to prevent browser caching issues
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        # Authentication endpoints
        if path == '/auth/login':
            self.handle_login()
            return
        elif path == '/auth/google/callback':
            self.handle_google_callback()
            return
        elif path == '/auth/logout':
            self.handle_logout()
            return
        elif path == '/auth/user':
            self.handle_get_user()
            return

        # Special handling for SSE endpoints (must be before handle_api_get)
        if path.startswith('/api/processing/') and '/logs' in path:
            from urllib.parse import unquote
            self.handle_processing_logs_sse(path)
            return

        # PDF serving endpoint (must be before general API handling)
        if path.startswith('/api/pdf/serve/'):
            from urllib.parse import unquote
            pdf_id = unquote(path.split('/')[-1])
            self.handle_pdf_serve(pdf_id)
            return

        # API endpoints
        if path.startswith('/api/'):
            self.handle_api_get(path, query_params)
            return

        # Check authentication for protected pages (if auth is enabled)
        if self.google_auth and not self.is_public_page(path):
            user = self.get_current_user()
            if not user:
                self.send_response(302)
                self.send_header('Location', '/login.html')
                self.end_headers()
                return

        # Serve static files
        super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body) if body else {}

        # API endpoints
        if path.startswith('/api/'):
            self.handle_api_post(path, data)
            return

        # Default response
        self.send_response(404)
        self.end_headers()

    # ============================================================
    # AUTHENTICATION METHODS
    # ============================================================

    def is_public_page(self, path: str) -> bool:
        """Check if page is public (doesn't require auth)."""
        if path == '/' or path == '':
            return False

        for public_path in self.PUBLIC_PAGES:
            if path == public_path or path.startswith(public_path):
                return True

        if path.endswith(('.css', '.js', '.png', '.jpg', '.ico', '.svg')):
            return True

        return False

    def get_current_user(self):
        """Get current user from session cookie."""
        if not self.user_db:
            return None

        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None

        cookies = SimpleCookie(cookie_header)
        if 'session_token' not in cookies:
            return None

        session_token = cookies['session_token'].value
        session = self.user_db.get_session(session_token)
        if not session:
            return None

        return {
            'user_id': session['user_id'],
            'email': session['email'],
            'name': session['name'],
            'picture': session['picture'],
            'role': session['role']
        }

    def handle_login(self):
        """Initiate Google OAuth login flow."""
        if not self.google_auth:
            self.send_error(500, "Authentication not configured")
            return

        try:
            auth_url, state = self.google_auth.get_authorization_url()
            self.send_response(302)
            self.send_header('Location', auth_url)
            self.send_header('Set-Cookie', f'oauth_state={state}; Path=/; HttpOnly; Max-Age=600')
            self.end_headers()
        except Exception as e:
            self.send_error(500, f"Login error: {str(e)}")

    def handle_google_callback(self):
        """Handle Google OAuth callback."""
        if not self.google_auth:
            self.send_error(500, "Authentication not configured")
            return

        try:
            parsed_path = urlparse(self.path)
            params = parse_qs(parsed_path.query)

            code = params.get('code', [None])[0]
            state = params.get('state', [None])[0]

            if not code or not state:
                self.send_error(400, "Missing code or state")
                return

            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                cookies = SimpleCookie(cookie_header)
                stored_state = cookies.get('oauth_state')
                if not stored_state or stored_state.value != state:
                    self.send_error(400, "Invalid state parameter")
                    return

            user_info, credentials = self.google_auth.exchange_code_for_token(code, state)

            user_id = self.user_db.create_or_update_user(
                google_id=user_info['google_id'],
                email=user_info['email'],
                name=user_info.get('name'),
                picture=user_info.get('picture')
            )

            session_token = GoogleAuth.generate_session_token()
            self.user_db.create_session(user_id, session_token, expires_in_days=30)

            self.send_response(302)
            self.send_header('Location', '/index.html')
            self.send_header('Set-Cookie', f'session_token={session_token}; Path=/; HttpOnly; Max-Age=2592000')
            self.send_header('Set-Cookie', 'oauth_state=; Path=/; Max-Age=0')
            self.end_headers()

            print(f"✅ User logged in: {user_info['email']}")

        except Exception as e:
            print(f"❌ OAuth callback error: {str(e)}")
            self.send_error(500, f"Authentication error: {str(e)}")

    def handle_logout(self):
        """Handle logout - clear session."""
        if not self.user_db:
            self.send_response(302)
            self.send_header('Location', '/login.html')
            self.end_headers()
            return

        try:
            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                cookies = SimpleCookie(cookie_header)
                if 'session_token' in cookies:
                    session_token = cookies['session_token'].value
                    self.user_db.delete_session(session_token)

            self.send_response(302)
            self.send_header('Location', '/login.html')
            self.send_header('Set-Cookie', 'session_token=; Path=/; Max-Age=0')
            self.end_headers()
        except Exception as e:
            self.send_error(500, f"Logout error: {str(e)}")

    def handle_get_user(self):
        """Get current user info (API endpoint)."""
        user = self.get_current_user()

        if not user:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not authenticated'}).encode())
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(user).encode())

    # ============================================================
    # API ROUTING
    # ============================================================

    def handle_api_get(self, path: str, query_params: dict):
        """Route GET API requests."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        try:
            # Assessment API endpoints
            if path.startswith('/api/assessment/'):
                self.handle_assessment_get(path, query_params)
            # Math API endpoints
            elif path.startswith('/api/math/'):
                self.handle_math_get(path, query_params)
            # GK Dashboard API endpoints (including assessment status)
            elif path.startswith('/api/dashboard') or path.startswith('/api/pdfs/') or \
                 path.startswith('/api/filter/') or path.startswith('/api/stats') or \
                 path.startswith('/api/pdf/') or path.startswith('/api/chunks/') or \
                 path.startswith('/api/large-files') or path.startswith('/api/assessment-status/') or \
                 path.startswith('/api/assessment-progress/'):
                self.handle_gk_dashboard_get(path, query_params)
            # Analytics API endpoints
            elif path.startswith('/api/analytics/'):
                self.handle_analytics_get(path, query_params)
            # Processing API endpoints
            elif path.startswith('/api/processing/'):
                self.handle_processing_get(path, query_params)
            # Annotation API endpoints
            elif path.startswith('/api/annotations/'):
                self.handle_annotation_get(path, query_params)
            else:
                self.send_json({'error': 'Not Found'})
        except Exception as e:
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    def handle_api_post(self, path: str, data: dict):
        """Route POST API requests."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        try:
            # Assessment API endpoints
            if path.startswith('/api/assessment/'):
                self.handle_assessment_post(path, data)
            # Math API endpoints
            elif path.startswith('/api/math/'):
                self.handle_math_post(path, data)
            # GK Dashboard API endpoints
            # GK PDF Processing API endpoints
            elif path.startswith('/api/gk/'):
                self.handle_gk_api_post(path, data)
            elif path.startswith('/api/revise/'):
                self.handle_gk_dashboard_post(path, data)
            # Processing API endpoints
            elif path.startswith('/api/processing/'):
                self.handle_processing_post(path, data)
            # Annotation API endpoints
            elif path.startswith('/api/annotations/'):
                self.handle_annotation_post(path, data)
            # PDF Chunking API endpoints
            elif path.startswith('/api/pdf/chunk'):
                self.handle_pdf_chunk_post(path, data)
            # Assessment Creation API endpoints
            elif path.startswith('/api/create-assessment'):
                self.handle_assessment_creation_post(path, data)
            else:
                self.send_json({'error': 'Not Found'})
        except Exception as e:
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    def do_DELETE(self):
        """Handle DELETE requests."""
        try:
            path = self.path.split('?')[0]

            # DELETE /api/annotations/{annotation_id}
            if path.startswith('/api/annotations/'):
                parts = path.split('/')
                if len(parts) == 4:
                    annotation_id = parts[3]

                    success = self.annotation_manager.delete_annotation(
                        annotation_id=int(annotation_id),
                        deleted_by='system',
                        hard_delete=False  # Soft delete by default
                    )

                    if success:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.send_json({
                            'success': True,
                            'message': 'Annotation deleted successfully'
                        })
                    else:
                        self.send_response(404)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.send_json({'error': 'Annotation not found'})
                else:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.send_json({'error': 'Invalid annotation ID'})
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.send_json({'error': 'Not Found'})

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    # ============================================================
    # ASSESSMENT API METHODS
    # ============================================================

    def handle_assessment_get(self, path: str, query_params: dict):
        """Handle assessment API GET requests."""
        # Import from assessment_api.py logic
        if path == '/api/assessment/check-anki':
            available = self.anki.test_connection()
            self.send_json({'available': available})

        elif path == '/api/assessment/categories':
            categories = self.anki.get_deck_names()
            self.send_json({'categories': categories})

        elif path == '/api/assessment/performance/summary':
            user_id = query_params.get('user_id', ['daughter'])[0]
            tests = self.assessment_db.get_all_tests(user_id)
            total_tests = len(tests)

            # Calculate stats from tests
            if total_tests > 0:
                avg_score = sum(t['score'] for t in tests) / total_tests
                total_correct = sum(t['correct_answers'] or 0 for t in tests)
                total_questions = sum(t['total_questions'] or 0 for t in tests)
                accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
            else:
                avg_score = 0
                accuracy = 0
                total_questions = 0

            questions_attempted = self.assessment_db.get_total_questions_attempted(user_id)
            mastery_breakdown = self.assessment_db.get_mastery_breakdown(user_id)

            # Return in format expected by frontend
            self.send_json({
                'overall_stats': {
                    'total_tests': total_tests,
                    'average_score': round(avg_score, 1),
                    'total_questions': questions_attempted,
                    'accuracy': round(accuracy, 1)
                },
                'category_performance': [],  # Can be populated later
                'mastery_breakdown': mastery_breakdown
            })

        elif path == '/api/assessment/performance/weak-questions':
            user_id = query_params.get('user_id', ['daughter'])[0]
            weak = self.assessment_db.get_weak_questions(user_id, limit=10)
            self.send_json({'weak_questions': weak})

        else:
            self.send_json({'error': 'Assessment endpoint not found'})

    def handle_assessment_post(self, path: str, data: dict):
        """Handle assessment API POST requests."""
        if path == '/api/assessment/session/create':
            # Create test session - full implementation from assessment_api.py
            user_id = data.get('user_id', 'daughter')
            # Support both single PDF (backward compat) and multiple PDFs
            pdf_ids = data.get('pdf_ids', [])
            if not pdf_ids:
                # Backward compatibility: single pdf_id
                single_pdf_id = data.get('pdf_id')
                if single_pdf_id:
                    pdf_ids = [single_pdf_id]

            if not pdf_ids:
                self.send_json({'error': 'No PDF selected'})
                return

            # Keep original variables for single PDF backward compatibility
            pdf_id = pdf_ids[0] if len(pdf_ids) == 1 else 'combined'
            pdf_id = data.get('pdf_id')
            pdf_filename = data.get('pdf_filename', '')
            source_date = data.get('source_date', pdf_id)
            session_type = data.get('session_type', 'full')

            # Handle weak topics test
            if session_type == 'weak':
                weak_note_ids = self.assessment_db.get_weak_questions(user_id, limit=20)

                if not weak_note_ids:
                    self.send_json({
                        'error': 'No weak topics found. Take some tests first to identify weak areas!'
                    })
                    return

                # Get questions from Anki for weak note IDs
                note_ids = [str(q['anki_note_id']) for q in weak_note_ids]
                questions = self.anki.get_questions_by_note_ids(note_ids)

                if not questions:
                    self.send_json({'error': 'Could not load weak topic questions from Anki.'})
                    return

                pdf_id = 'weak_topics'
                pdf_filename = 'Weak Topics Practice'
                source_date = 'weak_topics'
            else:
                # Get questions for this PDF
                # Get questions from all selected PDFs
                all_questions = []
                for pdf_source in pdf_ids:
                    pdf_questions = self.anki.get_questions_for_pdf(pdf_source)
                    if pdf_questions:
                        all_questions.extend(pdf_questions)
                
                questions = all_questions

                if not questions:
                    self.send_json({
                        'error': 'No questions found for this PDF. Make sure it has been processed and cards are in Anki.'
                    })
                    return

                # Set pdf_id and pdf_filename if not provided
                if not pdf_id:
                    pdf_id = source_date
                if not pdf_filename:
                    if len(pdf_ids) > 1:
                        pdf_filename = f'Combined Test ({len(pdf_ids)} PDFs)'
                    else:
                        pdf_filename = f'Daily GK - {source_date}'

            # Create session
            session_id = self.assessment_db.create_test_session(
                user_id=user_id,
                pdf_id=pdf_id,
                pdf_filename=pdf_filename,
                source_date=source_date,
                session_type=session_type,
                total_questions=len(questions)
            )

            # Load or generate choices for ALL questions
            questions_to_generate = []

            for i, question in enumerate(questions):
                # Try to load from database first
                stored_choices = self._get_stored_mcq_choices(question['note_id'])

                if stored_choices:
                    # Use stored choices (instant!)
                    question['choices'] = stored_choices['choices']
                    question['correct_index'] = stored_choices['correct_index']
                else:
                    # Mark for generation
                    questions_to_generate.append((i, question))

            # Generate choices for questions that don't have them yet
            if questions_to_generate:
                batch_size = 10

                for batch_start in range(0, len(questions_to_generate), batch_size):
                    batch_end = min(batch_start + batch_size, len(questions_to_generate))
                    batch_items = questions_to_generate[batch_start:batch_end]
                    batch_questions = [item[1] for item in batch_items]

                    batch_results = self._generate_mcq_choices_batch(batch_questions)

                    for local_idx, (global_idx, question) in enumerate(batch_items):
                        if local_idx in batch_results:
                            choices_data = batch_results[local_idx]
                            questions[global_idx]['choices'] = choices_data['choices']
                            questions[global_idx]['correct_index'] = choices_data['correct_index']

                            # Store in database for future use
                            self._store_mcq_choices(question['note_id'], choices_data)
                        else:
                            # Fallback
                            questions[global_idx]['choices'] = [questions[global_idx]['answer']]
                            questions[global_idx]['correct_index'] = 0

            # Return all questions
            self.send_json({
                'success': True,
                'session_id': session_id,
                'questions': questions,
                'total_questions': len(questions)
            })

        elif path == '/api/assessment/answer/submit':
            # Submit answer logic
            session_id = data.get('session_id')
            note_id = data.get('note_id')
            question_text = data.get('question', '')
            user_answer = data.get('user_answer', '')
            correct_answer = data.get('correct_answer')
            category = data.get('category', '')
            time_taken = data.get('time_taken', 0)

            # Calculate is_correct
            is_correct = (user_answer.strip() == correct_answer.strip())

            self.assessment_db.record_question_attempt(
                session_id=session_id,
                anki_note_id=note_id,
                question_text=question_text,
                correct_answer=correct_answer,
                user_answer=user_answer,
                category=category,
                is_correct=is_correct,
                time_taken=time_taken
            )

            self.send_json({'success': True})

        else:
            self.send_json({'error': 'Assessment endpoint not found'})

    # ============================================================
    # MATH API METHODS
    # ============================================================

    def handle_math_get(self, path: str, query_params: dict):
        """Handle math API GET requests."""
        if path == '/api/math/settings':
            user_id = query_params.get('user_id', ['daughter'])[0]
            settings = {}
            for topic in ['arithmetic', 'fractions', 'decimals', 'equations', 'profit_loss', 'bodmas']:
                setting = self.math_db.get_topic_setting(user_id, topic)
                if setting:
                    settings[topic] = setting
            self.send_json({'settings': settings})

        elif path == '/api/math/performance/overall':
            user_id = query_params.get('user_id', ['daughter'])[0]
            perf = self.math_db.get_overall_performance(user_id)
            self.send_json({'performance': perf})

        elif path == '/api/math/performance/topics':
            user_id = query_params.get('user_id', ['daughter'])[0]
            topics = self.math_db.get_topic_performance(user_id)
            self.send_json({'topics': topics})

        elif path == '/api/math/stats':
            stats = self.math_db.get_database_stats()
            self.send_json(stats)

        else:
            self.send_json({'error': 'Math endpoint not found'})

    def handle_math_post(self, path: str, data: dict):
        """Handle math API POST requests."""
        if path == '/api/math/session/create':
            user_id = data.get('user_id', 'daughter')
            topics = data.get('topics', [])
            total_questions = data.get('total_questions', 10)

            questions = []
            for topic in topics:
                setting = self.math_db.get_topic_setting(user_id, topic)
                difficulty = setting['difficulty'] if setting else 'medium'
                qs = self.math_db.get_questions([topic], difficulty, limit=total_questions // len(topics))
                questions.extend(qs)

            import random
            random.shuffle(questions)
            questions = questions[:total_questions]

            session_id = self.math_db.create_session(user_id, topics, total_questions)

            self.send_json({
                'session_id': session_id,
                'questions': questions,
                'total_questions': len(questions)
            })

        elif path == '/api/math/answer/submit':
            session_id = data.get('session_id')
            question_id = data.get('question_id')
            selected_choice = data.get('selected_choice')
            is_correct = data.get('is_correct', False)
            time_taken = data.get('time_taken_seconds', 0)
            topic = data.get('topic', '')

            self.math_db.record_answer(session_id, question_id, selected_choice, is_correct, time_taken)

            user_id = data.get('user_id', 'daughter')
            self.math_db.update_topic_performance(user_id, topic, is_correct, time_taken)

            self.send_json({'success': True})

        elif path == '/api/math/session/complete':
            session_id = data.get('session_id')
            score = data.get('score', 0)
            self.math_db.complete_session(session_id, score)
            self.send_json({'success': True})

        elif path == '/api/math/settings/update':
            user_id = data.get('user_id', 'daughter')
            topic = data.get('topic')
            enabled = data.get('enabled', True)
            difficulty = data.get('difficulty', 'medium')

            self.math_db.update_topic_setting(user_id, topic, enabled, difficulty)
            self.send_json({'success': True})

        elif path == '/api/math/generate':
            topic = data.get('topic')
            difficulty = data.get('difficulty')
            count = data.get('count', 10)

            try:
                import anthropic
                import os
                import json
                from datetime import datetime

                client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

                prompt = f"Generate {count} {difficulty} difficulty {topic} math questions for middle/high school students. For each question provide: question_text, correct_answer, choice_a, choice_b, choice_c, choice_d, correct_choice (A/B/C/D), explanation. Return ONLY a JSON array of question objects, no markdown or extra text."

                message = client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )

                response_text = message.content[0].text

                # Clean markdown if present
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                questions = json.loads(response_text)

                cursor = self.math_db.conn.cursor()
                now = datetime.utcnow().isoformat()
                inserted = 0

                for q in questions:
                    sql = "INSERT INTO math_questions (topic, difficulty, question_text, correct_answer, choice_a, choice_b, choice_c, choice_d, correct_choice, explanation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(sql, (topic, difficulty, q["question_text"], q["correct_answer"], q["choice_a"], q["choice_b"], q["choice_c"], q["choice_d"], q["correct_choice"], q["explanation"], now))
                    inserted += 1

                self.math_db.conn.commit()
                cursor.execute("SELECT COUNT(*) as total FROM math_questions")
                total_questions = cursor.fetchone()["total"]

                self.send_json({"success": True, "inserted": inserted, "topic": topic, "difficulty": difficulty, "total_questions": total_questions})
            except Exception as e:
                self.send_json({"error": str(e)})

        else:
            self.send_json({'error': 'Math endpoint not found'})

    # ============================================================
    # GK DASHBOARD API METHODS
    # ============================================================

    def get_all_chunks(self):
        """Get all chunked PDFs from database."""
        import sqlite3
        from pathlib import Path

        db_path = Path.home() / 'clat_preparation' / 'revision_tracker.db'
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    parent_pdf_id,
                    chunk_filename,
                    chunk_path,
                    chunk_number,
                    start_page,
                    end_page,
                    total_pages,
                    file_size_kb,
                    original_file_path,
                    original_file_deleted,
                    deletion_timestamp,
                    overlap_enabled,
                    max_pages_per_chunk,
                    created_at
                FROM pdf_chunks
                ORDER BY parent_pdf_id, chunk_number
            """)

            chunks = [dict(row) for row in cursor.fetchall()]

            # Group chunks by parent PDF
            grouped_chunks = {}
            for chunk in chunks:
                parent = chunk['parent_pdf_id']
                if parent not in grouped_chunks:
                    grouped_chunks[parent] = {
                        'parent_pdf': parent,
                        'original_deleted': chunk['original_file_deleted'],
                        'deletion_timestamp': chunk['deletion_timestamp'],
                        'overlap_enabled': chunk['overlap_enabled'],
                        'chunks': []
                    }
                grouped_chunks[parent]['chunks'].append(chunk)

            return list(grouped_chunks.values())

        finally:
            conn.close()

    def _filter_and_add_chunks(self, pdfs_list):
        """Filter out chunked originals and add chunked files from database."""
        import sqlite3
        from pathlib import Path

        db_path = Path.home() / 'clat_preparation' / 'revision_tracker.db'
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get list of PDFs marked as chunked (to filter out)
            cursor.execute("SELECT filename FROM pdfs WHERE is_chunked = 1")
            chunked_originals = {row['filename'] for row in cursor.fetchall()}

            # Filter out chunked originals
            filtered_pdfs = [pdf for pdf in pdfs_list if pdf.get('filename') not in chunked_originals]

            # Get all chunk files from pdfs table
            cursor.execute("""
                SELECT filename, filepath, source, date_published, source_type, parent_pdf
                FROM pdfs
                WHERE is_chunk = 1
            """)

            chunks = cursor.fetchall()

            # Add chunks to the filtered list
            for chunk in chunks:
                filtered_pdfs.append({
                    'filename': chunk['filename'],
                    'filepath': chunk['filepath'],
                    'source': chunk['source'],
                    'date_published': chunk['date_published'],
                    'source_type': chunk['source_type'],
                    'pdf_id': chunk['filename'],
                    'exists_in_db': True,
                    'is_chunk': True,
                    'parent_pdf': chunk['parent_pdf']
                })

            return filtered_pdfs
        finally:
            conn.close()

    def _add_page_counts(self, pdfs_list):
        """Add page count information to PDF list."""
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from pdf_chunker import PdfChunker

        for pdf in pdfs_list:
            filepath = pdf.get('filepath')
            if filepath and Path(filepath).exists():
                page_count = PdfChunker.get_pdf_page_count(filepath)
                pdf['page_count'] = page_count
                # Red marking and chunking should both be >13 pages
                pdf['needs_chunking'] = page_count > 13
                pdf['can_chunk'] = page_count > 13
            else:
                pdf['page_count'] = 0
                pdf['needs_chunking'] = False
                pdf['can_chunk'] = False

        return pdfs_list

    def _scan_large_files(self):
        """Scan large_files folder for archived PDFs."""
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from pdf_chunker import PdfChunker

        large_files_dir = Path.home() / 'Desktop' / 'saanvi' / 'large_files'
        if not large_files_dir.exists():
            return []

        large_files = []
        for pdf_path in large_files_dir.glob('*.pdf'):
            page_count = PdfChunker.get_pdf_page_count(str(pdf_path))
            large_files.append({
                'filename': pdf_path.name,
                'filepath': str(pdf_path),
                'pdf_id': pdf_path.name,
                'page_count': page_count,
                'size_mb': round(pdf_path.stat().st_size / (1024 * 1024), 2),
                'modified': pdf_path.stat().st_mtime
            })

        # Sort by modified time descending
        large_files.sort(key=lambda x: x['modified'], reverse=True)
        return large_files

    def handle_gk_dashboard_get(self, path: str, query_params: dict):
        """Handle GK dashboard API GET requests."""
        if path == '/api/dashboard':
            # Get comprehensive dashboard data
            scan_results = self.pdf_scanner.scan_all_folders()
            stats = self.pdf_scanner.get_statistics()

            # Add page counts to all PDFs
            scan_results['daily'] = self._add_page_counts(scan_results.get('daily', []))
            if 'weekly' in scan_results:
                scan_results['weekly']['legaledge'] = self._add_page_counts(scan_results['weekly'].get('legaledge', []))
                scan_results['weekly']['career_launcher'] = self._add_page_counts(scan_results['weekly'].get('career_launcher', []))

            # Organize into segregated structure
            data = {
                'pdfs': scan_results,
                'statistics': stats,
                'large_files': self._scan_large_files()
            }
            self.send_json(data)

        elif path == '/api/pdfs/all':
            # Get all PDFs from scan
            scan_results = self.pdf_scanner.scan_all_folders()
            all_pdfs = []
            all_pdfs.extend(scan_results.get('daily', []))
            if 'weekly' in scan_results:
                all_pdfs.extend(scan_results['weekly'].get('legaledge', []))
                all_pdfs.extend(scan_results['weekly'].get('career_launcher', []))
            self.send_json({'pdfs': all_pdfs})

        elif path == '/api/pdfs/daily':
            scan_results = self.pdf_scanner.scan_all_folders()
            self.send_json({'pdfs': scan_results.get('daily', [])})

        elif path == '/api/pdfs/weekly':
            scan_results = self.pdf_scanner.scan_all_folders()
            weekly_pdfs = []
            if 'weekly' in scan_results:
                weekly_pdfs.extend(scan_results['weekly'].get('legaledge', []))
                weekly_pdfs.extend(scan_results['weekly'].get('career_launcher', []))
            self.send_json({'pdfs': weekly_pdfs})

        elif path == '/api/stats':
            stats = self.pdf_scanner.get_statistics()
            self.send_json(stats)

        elif path.startswith('/api/pdf/'):
            pdf_id = path.split('/')[-1]
            # Find PDF in scan results
            scan_results = self.pdf_scanner.scan_all_folders()
            pdf = None
            all_pdfs = []
            all_pdfs.extend(scan_results.get('daily', []))
            if 'weekly' in scan_results:
                all_pdfs.extend(scan_results['weekly'].get('legaledge', []))
                all_pdfs.extend(scan_results['weekly'].get('career_launcher', []))

            for p in all_pdfs:
                if p.get('pdf_id') == pdf_id:
                    pdf = p
                    break

            self.send_json(pdf if pdf else {'error': 'PDF not found'})

        elif path == '/api/filter/untouched':
            weeks = int(query_params.get('weeks', [4])[0])
            pdfs = self.pdf_scanner.filter_by_untouched_weeks(weeks)
            self.send_json({'pdfs': pdfs})

        elif path == '/api/filter/revision-count':
            min_count = int(query_params.get('min', [0])[0])
            max_count = int(query_params.get('max', [999])[0])
            pdfs = self.pdf_scanner.filter_by_revision_count(min_count, max_count)
            self.send_json({'pdfs': pdfs})

        elif path == '/api/chunks/all':
            # Get all chunked PDFs from database
            chunks = self.get_all_chunks()
            self.send_json({'chunks': chunks})

        elif path == '/api/large-files':
            # Get all large archived files
            large_files = self._scan_large_files()
            self.send_json({'large_files': large_files})

        # Assessment creation status endpoints
        elif path.startswith('/api/assessment-progress/'):
            # GET /api/assessment-progress/{job_id}
            from urllib.parse import unquote
            job_id = unquote(path.split('/')[-1])
            self.handle_assessment_progress_get(job_id)

        elif path.startswith('/api/assessment-status/'):
            # GET /api/assessment-status/{pdf_id}
            from urllib.parse import unquote
            pdf_id = unquote(path.split('/')[-1])
            self.handle_assessment_status_get(pdf_id)

        else:
            self.send_json({'error': 'GK dashboard endpoint not found'})

    def handle_gk_dashboard_post(self, path: str, data: dict):
        """Handle GK dashboard API POST requests."""
        if path.startswith('/api/revise/'):
            pdf_id = path.split('/')[-1]
            # Mark as revised logic
            self.send_json({'success': True, 'pdf_id': pdf_id})
        else:
            self.send_json({'error': 'GK dashboard endpoint not found'})

    def handle_analytics_get(self, path: str, query_params: dict):
        """Handle analytics API GET requests."""
        import sqlite3
        from datetime import datetime, timedelta

        # Get current user (default to 'daughter' if no auth)
        user_id = query_params.get('user_id', ['daughter'])[0] if 'user_id' in query_params else 'daughter'

        if path == '/api/analytics/daily':
            # Get daily statistics for last 30 days from question_attempts
            # This includes ALL attempts, even from incomplete tests
            conn = sqlite3.connect(self.assessment_db.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Query to aggregate data by date from question_attempts
            cursor.execute("""
                SELECT
                    DATE(qa.answered_at) as practice_date,
                    COUNT(*) as total_questions,
                    SUM(qa.is_correct) as correct_answers,
                    SUM(CASE WHEN qa.is_correct = 0 AND qa.user_answer IS NOT NULL THEN 1 ELSE 0 END) as wrong_answers,
                    SUM(CASE WHEN qa.user_answer IS NULL THEN 1 ELSE 0 END) as skipped_answers,
                    SUM(qa.time_taken_seconds) as time_spent
                FROM question_attempts qa
                JOIN test_sessions ts ON qa.session_id = ts.session_id
                WHERE ts.user_id = ?
                  AND qa.answered_at >= date('now', '-30 days')
                GROUP BY DATE(qa.answered_at)
                ORDER BY practice_date DESC
            """, (user_id,))

            rows = cursor.fetchall()
            conn.close()

            daily_stats = []
            for row in rows:
                total_qs = row[1] or 0
                correct = row[2] or 0
                accuracy = round((correct / total_qs * 100) if total_qs > 0 else 0, 1)

                daily_stats.append({
                    'date': row[0],
                    'total_questions': total_qs,
                    'correct_answers': correct,
                    'wrong_answers': row[3] or 0,
                    'skipped_answers': row[4] or 0,
                    'time_spent': row[5] or 0,
                    'accuracy': accuracy
                })

            self.send_json({'daily_stats': daily_stats})

        elif path == '/api/analytics/categories':
            # Get category performance
            conn = sqlite3.connect(self.assessment_db.db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    category,
                    total_questions,
                    correct_answers,
                    wrong_answers,
                    accuracy_percentage,
                    last_practiced_at
                FROM category_performance
                WHERE user_id = ?
                ORDER BY total_questions DESC
            """, (user_id,))

            rows = cursor.fetchall()
            conn.close()

            categories = []
            for row in rows:
                categories.append({
                    'category': row[0],
                    'total_questions': row[1],
                    'correct_answers': row[2],
                    'wrong_answers': row[3],
                    'accuracy_percentage': row[4],
                    'last_practiced_at': row[5]
                })

            self.send_json({'categories': categories})

        else:
            self.send_json({'error': 'Analytics endpoint not found'})

    def handle_gk_api_post(self, path: str, data: dict):
        """Handle GK PDF processing API POST requests."""
        if path == '/api/gk/process-pdf':
            import threading
            import subprocess
            from pathlib import Path

            pdf_id = data.get('pdf_id')
            filepath = data.get('filepath')
            source_name = data.get('source_name')

            if not all([pdf_id, filepath, source_name]):
                self.send_json({
                    'success': False,
                    'error': 'Missing required parameters: pdf_id, filepath, source_name'
                })
                return

            # Check if file exists
            if not Path(filepath).exists():
                self.send_json({
                    'success': False,
                    'error': f'PDF file not found: {filepath}'
                })
                return

            # Process in background thread
            def process_in_background():
                try:
                    script_path = Path.home() / 'clat_preparation' / 'process_pdf_with_tracking.py'
                    venv_python = Path.home() / 'Desktop' / 'anki_automation' / 'venv' / 'bin' / 'python3'

                    # Use venv python if available, otherwise system python
                    python_exe = str(venv_python) if venv_python.exists() else 'python3'

                    result = subprocess.run(
                        [python_exe, str(script_path), filepath, source_name, pdf_id],
                        capture_output=True,
                        text=True,
                        timeout=1800  # 30 minute timeout
                    )

                    if result.returncode == 0:
                        print(f"✅ Successfully processed {pdf_id}")
                        print(result.stdout)
                    else:
                        print(f"❌ Error processing {pdf_id}")
                        print(result.stderr)

                except Exception as e:
                    print(f"❌ Exception processing {pdf_id}: {e}")

            # Start background thread
            thread = threading.Thread(target=process_in_background, daemon=True)
            thread.start()

            self.send_json({
                'success': True,
                'message': f'PDF processing started for {pdf_id}',
                'pdf_id': pdf_id
            })

        elif path == '/api/gk/processing-status':
            from pathlib import Path
            import json

            pdf_id = data.get('pdf_id')
            if not pdf_id:
                self.send_json({'error': 'pdf_id required'})
                return

            # Check for status file
            status_dir = Path.home() / "clat_preparation" / "processing_status"
            status_file = status_dir / f"{pdf_id}.json"

            if status_file.exists():
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                    self.send_json({'success': True, 'status': status_data})
                except Exception as e:
                    self.send_json({'error': str(e)})
            else:
                self.send_json({'success': False, 'message': 'No status available'})

        else:
            self.send_json({'error': 'GK API endpoint not found'})

    # ============================================================
    # MCQ GENERATION HELPER METHODS
    # ============================================================

    def _get_stored_mcq_choices(self, note_id: str) -> dict:
        """Get stored MCQ choices from database cache."""
        try:
            import sqlite3
            db_path = Path(__file__).parent.parent / 'revision_tracker.db'
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT choices, correct_index
                FROM mcq_cache
                WHERE note_id = ?
            """, (str(note_id),))

            row = cursor.fetchone()
            conn.close()

            if row:
                choices_json, correct_index = row
                return {
                    'choices': json.loads(choices_json),
                    'correct_index': correct_index
                }
            return None
        except Exception as e:
            print(f"Error loading cached choices: {e}")
            return None

    def _store_mcq_choices(self, note_id: str, choices_data: dict, pdf_source: str = None):
        """Store MCQ choices in database cache."""
        try:
            import sqlite3
            db_path = Path(__file__).parent.parent / 'revision_tracker.db'
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            choices_json = json.dumps(choices_data['choices'])
            correct_index = choices_data['correct_index']
            created_at = datetime.now().isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO mcq_cache (note_id, choices, correct_index, created_at, pdf_source)
                VALUES (?, ?, ?, ?, ?)
            """, (str(note_id), choices_json, correct_index, created_at, pdf_source))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error storing cached choices: {e}")

    def _generate_mcq_choices_batch(self, questions: list) -> dict:
        """Generate MCQ choices for a batch of questions using Claude API."""
        if not self.anthropic:
            print("⚠️  Anthropic API not configured - skipping choice generation")
            return {}

        # Prepare batch prompt
        questions_text = []
        for i, q in enumerate(questions):
            questions_text.append(f"""[Question {i+1}]
Question: {q['question']}
Correct Answer: {q['answer']}
Category: {q['category']}
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

{chr(10).join(questions_text)}

For each question, provide exactly 3 distractors, one per line. Use this format:

[Question 1]
<distractor 1>
<distractor 2>
<distractor 3>

[Question 2]
<distractor 1>
<distractor 2>
<distractor 3>

...and so on for all questions.

IMPORTANT: Provide ONLY the distractors, no explanations or additional text."""

        try:
            # Call Claude API
            message = self.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=4000,
                temperature=1.0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            # Parse response
            results = {}
            current_question_idx = None
            current_distractors = []

            for line in response_text.strip().split('\n'):
                line = line.strip()

                if line.startswith('[Question '):
                    # Save previous question
                    if current_question_idx is not None and len(current_distractors) == 3:
                        question = questions[current_question_idx]
                        all_choices = [question['answer']] + current_distractors

                        # Shuffle choices
                        import random
                        correct_answer = question['answer']
                        random.shuffle(all_choices)
                        correct_index = all_choices.index(correct_answer)

                        results[current_question_idx] = {
                            'choices': all_choices,
                            'correct_index': correct_index
                        }

                    # Start new question
                    try:
                        q_num = int(line.split('[Question ')[1].split(']')[0])
                        current_question_idx = q_num - 1
                        current_distractors = []
                    except:
                        pass

                elif line and not line.startswith('[') and current_question_idx is not None:
                    current_distractors.append(line)

            # Save last question
            if current_question_idx is not None and len(current_distractors) == 3:
                question = questions[current_question_idx]
                all_choices = [question['answer']] + current_distractors

                # Shuffle choices
                import random
                correct_answer = question['answer']
                random.shuffle(all_choices)
                correct_index = all_choices.index(correct_answer)

                results[current_question_idx] = {
                    'choices': all_choices,
                    'correct_index': correct_index
                }

            return results

        except Exception as e:
            print(f"❌ Error generating choices: {e}")
            return {}

    # ============================================================
    # PDF VIEWER & ANNOTATION METHODS
    # ============================================================

    def handle_pdf_serve(self, pdf_id: str):
        """Serve PDF file for viewing in browser."""
        import os
        from pathlib import Path

        filepath = None

        # First, try to find PDF in database
        db_path = Path.home() / 'clat_preparation' / 'revision_tracker.db'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT filepath FROM pdfs WHERE filename = ?", (pdf_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            filepath = Path(result[0])
            # Verify file actually exists before using database path
            if not filepath.exists():
                filepath = None  # Force fallback to chunked_pdfs check

        if not filepath:
            # If not in database, check if it's a chunked PDF in /tmp/chunked_pdfs
            chunked_path = Path('/tmp/chunked_pdfs') / pdf_id
            if chunked_path.exists():
                filepath = chunked_path
            else:
                # Also check common PDF directories
                for base_dir in [
                    Path.home() / 'saanvi' / 'Legaledgedailygk',
                    Path.home() / 'saanvi' / 'LegalEdgeweeklyGK',
                    Path.home() / 'saanvi' / 'weeklyGKCareerLauncher',
                    Path.home() / 'Desktop' / 'saanvi' / 'Legaledgedailygk',
                    Path.home() / 'Desktop' / 'saanvi' / 'legaledgegk'
                ]:
                    potential_path = base_dir / pdf_id
                    if potential_path.exists():
                        filepath = potential_path
                        break

        if not filepath or not filepath.exists():
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            error_msg = f'PDF not found: {pdf_id}\nSearched in database and common directories'
            self.wfile.write(error_msg.encode())
            return

        # Serve PDF file
        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Disposition', f'inline; filename="{filepath.name}"')
        self.send_header('Access-Control-Allow-Origin', '*')  # For CORS
        self.end_headers()

        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    # ============================================================
    # PDF PROCESSING API METHODS
    # ============================================================

    def handle_processing_logs_sse(self, path: str):
        """Handle SSE log streaming for processing jobs."""
        from urllib.parse import unquote
        import time

        # Extract job_id from path: /api/processing/{job_id}/logs
        job_id = unquote(path.split('/')[3])
        job = self.processing_db.get_job(job_id)

        if not job:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Job not found')
            return

        # Send SSE headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Stream log file
        log_file = Path(job['log_file'])
        if not log_file.exists():
            # Log file doesn't exist yet, send initial message
            event_data = json.dumps({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': 'INFO',
                'message': 'Waiting for processing to start...'
            })
            self.wfile.write(f"data: {event_data}\n\n".encode())
            self.wfile.flush()
            return

        # Read and stream log file
        last_position = 0

        # Read up to 30 seconds or until job completes
        for _ in range(30):
            try:
                with open(log_file, 'r') as f:
                    f.seek(last_position)
                    lines = f.readlines()
                    last_position = f.tell()

                    for line in lines:
                        # Parse log line: timestamp | level | message
                        parts = line.strip().split(' | ', 2)
                        if len(parts) == 3:
                            timestamp_str, level, message = parts
                            event_data = json.dumps({
                                'timestamp': timestamp_str,
                                'level': level,
                                'message': message
                            })
                            self.wfile.write(f"data: {event_data}\n\n".encode())
                            self.wfile.flush()

                # Check if job is complete
                updated_job = self.processing_db.get_job(job_id)
                if updated_job and updated_job['status'] in ['completed', 'failed']:
                    break

                time.sleep(1)

            except Exception as e:
                print(f"Error streaming logs: {e}")
                break

    def handle_processing_get(self, path: str, query_params: dict):
        """Handle processing API GET requests."""
        from urllib.parse import unquote

        # Get job status
        if path.startswith('/api/processing/') and '/status' in path:
            # Extract job_id from path: /api/processing/{job_id}/status
            job_id = unquote(path.split('/')[3])
            job = self.processing_db.get_job(job_id)

            if not job:
                self.send_json({'error': 'Job not found'})
                return

            self.send_json(job)

        # List all jobs
        elif path == '/api/processing/jobs':
            limit = int(query_params.get('limit', ['20'])[0])
            jobs = self.processing_db.get_recent_jobs(limit)
            self.send_json({'jobs': jobs})

        else:
            self.send_json({'error': 'Processing endpoint not found'})

    def handle_processing_post(self, path: str, data: dict):
        """Handle processing API POST requests."""
        import subprocess
        import threading

        # Start processing job
        if path == '/api/processing/start':
            pdf_id = data.get('pdf_id')
            pdf_path = data.get('pdf_path')
            pdf_filename = data.get('pdf_filename')
            source = data.get('source', 'career_launcher')
            week = data.get('week')
            pages_per_chunk = data.get('pages_per_chunk', 10)

            if not pdf_path or not pdf_filename:
                self.send_json({'error': 'Missing required parameters'})
                return

            # Determine number of chunks needed
            pdf_path_obj = Path(pdf_path)
            if not pdf_path_obj.exists():
                self.send_json({'error': f'PDF file not found: {pdf_path}'})
                return

            # Import the process_pdf_with_progress module to use its functions
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from process_pdf_with_progress import extract_text_length, split_pdf_by_pages

            text_length = extract_text_length(pdf_path_obj)
            total_chunks = 1

            if text_length > 40000:
                # Calculate number of chunks
                import fitz
                doc = fitz.open(str(pdf_path_obj))
                total_pages = len(doc)
                doc.close()
                total_chunks = (total_pages + pages_per_chunk - 1) // pages_per_chunk

            # Create job in database
            job_id = self.processing_db.create_job(
                pdf_id=pdf_id,
                pdf_filename=pdf_filename,
                pdf_path=pdf_path,
                source=source,
                week=week,
                total_chunks=total_chunks
            )

            # Start processing in background thread
            def run_processing():
                try:
                    # Run the processing script
                    script_path = Path(__file__).parent / 'process_pdf_with_progress.py'
                    subprocess.run(
                        ['python3', str(script_path), job_id],
                        check=True
                    )
                except Exception as e:
                    print(f"Processing error: {e}")
                    self.processing_db.mark_failed(job_id, str(e))

            thread = threading.Thread(target=run_processing, daemon=True)
            thread.start()

            self.send_json({
                'job_id': job_id,
                'status': 'queued',
                'message': 'Processing started'
            })

        else:
            self.send_json({'error': 'Processing endpoint not found'})

    # ============================================================
    # ANNOTATION API METHODS
    # ============================================================

    def handle_annotation_get(self, path: str, query_params: dict):
        """Handle annotation API GET requests."""
        from urllib.parse import unquote

        if not self.annotation_manager:
            self.send_json({'error': 'Annotation manager not initialized'})
            return

        try:
            # GET /api/annotations/{pdf_id}
            # Get all annotations for a PDF (optionally filtered by page)
            if path.startswith('/api/annotations/') and path.count('/') == 3:
                pdf_id = unquote(path.split('/')[-1])
                page_number = query_params.get('page', [None])[0]

                if page_number:
                    page_number = int(page_number)

                annotations = self.annotation_manager.get_annotations(
                    pdf_id=pdf_id,
                    page_number=page_number
                )

                self.send_json({
                    'pdf_id': pdf_id,
                    'annotations': annotations,
                    'count': len(annotations)
                })

            # GET /api/annotations/{pdf_id}/stats
            # Get statistics for a PDF
            elif path.endswith('/stats'):
                pdf_id = unquote(path.split('/')[-2])
                stats = self.annotation_manager.get_pdf_stats(pdf_id)

                if not stats:
                    self.send_json({'error': 'PDF not found'})
                else:
                    self.send_json(stats)

            # GET /api/annotations/{pdf_id}/history
            # Get revision history for a PDF
            elif path.endswith('/history'):
                pdf_id = unquote(path.split('/')[-2])
                limit = query_params.get('limit', [10])[0]

                history = self.annotation_manager.get_revision_history(
                    pdf_id=pdf_id,
                    limit=int(limit)
                )

                self.send_json({
                    'pdf_id': pdf_id,
                    'revisions': history,
                    'count': len(history)
                })

            # GET /api/annotations/{pdf_id}/details
            # Get comprehensive details for a PDF (stats + history + access log)
            elif path.endswith('/details'):
                pdf_id = unquote(path.split('/')[-2])

                # Get stats
                stats = self.annotation_manager.get_pdf_stats(pdf_id)

                # Get revision history (last 20 records)
                history = self.annotation_manager.get_revision_history(
                    pdf_id=pdf_id,
                    limit=20
                )

                # Get access log (last 50 accesses)
                conn = sqlite3.connect(str(Path.home() / 'clat_preparation' / 'revision_tracker.db'), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT log_id, user_id, access_type, timestamp, duration_seconds
                    FROM pdf_access_log
                    WHERE pdf_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (pdf_id,))

                access_log = [dict(row) for row in cursor.fetchall()]
                conn.close()

                self.send_json({
                    'pdf_id': pdf_id,
                    'stats': stats,
                    'revision_history': history,
                    'access_log': access_log,
                    'summary': {
                        'total_annotations': stats.get('annotation_count', 0) if stats else 0,
                        'total_edits': stats.get('edit_count', 0) if stats else 0,
                        'total_accesses': stats.get('access_count', 0) if stats else 0,
                        'last_accessed': stats.get('last_accessed') if stats else None,
                        'revision_count': len(history),
                        'access_count': len(access_log)
                    }
                })

            else:
                self.send_json({'error': 'Annotation endpoint not found'})

        except Exception as e:
            self.send_json({
                'error': str(e),
                'trace': traceback.format_exc()
            })

    def handle_annotation_post(self, path: str, data: dict):
        """Handle annotation API POST requests."""
        from urllib.parse import unquote

        if not self.annotation_manager:
            self.send_json({'error': 'Annotation manager not initialized'})
            return

        try:
            # POST /api/annotations/save
            # Save a new annotation
            if path == '/api/annotations/save':
                pdf_id = data.get('pdf_id')
                page_number = data.get('page_number')
                annotation_type = data.get('annotation_type')
                annotation_data = data.get('annotation_data')

                if not all([pdf_id, page_number, annotation_type, annotation_data]):
                    self.send_json({
                        'error': 'Missing required fields',
                        'required': ['pdf_id', 'page_number', 'annotation_type', 'annotation_data']
                    })
                    return

                annotation_id = self.annotation_manager.save_annotation(
                    pdf_id=pdf_id,
                    page_number=int(page_number),
                    annotation_type=annotation_type,
                    annotation_data=annotation_data,
                    created_by=data.get('created_by', 'system')
                )

                self.send_json({
                    'success': True,
                    'annotation_id': annotation_id,
                    'message': 'Annotation saved successfully'
                })

            # POST /api/annotations/update
            # Update an existing annotation
            elif path == '/api/annotations/update':
                annotation_id = data.get('annotation_id')
                annotation_data = data.get('annotation_data')

                if not annotation_id or not annotation_data:
                    self.send_json({
                        'error': 'Missing required fields',
                        'required': ['annotation_id', 'annotation_data']
                    })
                    return

                success = self.annotation_manager.update_annotation(
                    annotation_id=int(annotation_id),
                    annotation_data=annotation_data,
                    updated_by=data.get('updated_by', 'system')
                )

                if success:
                    self.send_json({
                        'success': True,
                        'message': 'Annotation updated successfully'
                    })
                else:
                    self.send_json({'error': 'Annotation not found'})

            # POST /api/annotations/delete
            # Delete an annotation
            elif path == '/api/annotations/delete':
                annotation_id = data.get('annotation_id')
                hard_delete = data.get('hard_delete', False)

                if not annotation_id:
                    self.send_json({
                        'error': 'Missing required field: annotation_id'
                    })
                    return

                success = self.annotation_manager.delete_annotation(
                    annotation_id=int(annotation_id),
                    deleted_by=data.get('deleted_by', 'system'),
                    hard_delete=hard_delete
                )

                if success:
                    self.send_json({
                        'success': True,
                        'message': 'Annotation deleted successfully'
                    })
                else:
                    self.send_json({'error': 'Annotation not found'})

            # POST /api/annotations/{pdf_id}/access
            # Log PDF access
            elif path.endswith('/access'):
                pdf_id = unquote(path.split('/')[-2])
                access_type = data.get('access_type', 'view')
                duration_seconds = data.get('duration_seconds')

                self.annotation_manager.log_access(
                    pdf_id=pdf_id,
                    access_type=access_type,
                    user_id=data.get('user_id', 'system'),
                    duration_seconds=duration_seconds
                )

                self.send_json({
                    'success': True,
                    'message': 'Access logged successfully'
                })

            else:
                self.send_json({'error': 'Annotation endpoint not found'})

        except Exception as e:
            self.send_json({
                'error': str(e),
                'trace': traceback.format_exc()
            })

    def handle_pdf_chunk_post(self, path: str, data: dict):
        """Handle PDF chunking API POST requests with streaming."""
        if not self.pdf_chunker:
            self.send_json({'error': 'PDF chunker not initialized'})
            return

        try:
            # POST /api/pdf/chunk
            # Chunk a PDF with streaming progress
            if path == '/api/pdf/chunk':
                pdf_path = data.get('pdf_path')
                output_dir = data.get('output_directory')
                max_pages = data.get('max_pages_per_chunk', 10)
                naming_pattern = data.get('naming_pattern', '{basename}_part{num}')

                if not pdf_path or not output_dir:
                    self.send_json({
                        'error': 'Missing required fields',
                        'required': ['pdf_path', 'output_directory']
                    })
                    return

                # Send headers for Server-Sent Events
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                # Stream progress updates
                try:
                    for update in self.pdf_chunker.chunk_pdf(
                        pdf_path,
                        output_dir,
                        max_pages,
                        naming_pattern
                    ):
                        # Send as Server-Sent Event
                        event_data = json.dumps(update)
                        self.wfile.write(f"data: {event_data}\n\n".encode())
                        self.wfile.flush()
                except Exception as e:
                    error_update = {
                        'type': 'error',
                        'message': str(e),
                        'trace': traceback.format_exc()
                    }
                    self.wfile.write(f"data: {json.dumps(error_update)}\n\n".encode())
                    self.wfile.flush()

            else:
                self.send_json({'error': 'PDF chunking endpoint not found'})

        except Exception as e:
            self.send_json({
                'error': str(e),
                'trace': traceback.format_exc()
            })

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    # ============================================================
    # ASSESSMENT CREATION API METHODS
    # ============================================================

    def handle_assessment_creation_post(self, path: str, data: dict):
        """Handle POST /api/create-assessment - Start assessment creation for a PDF."""
        import subprocess

        pdf_id = data.get('pdf_id')
        source = data.get('source')
        week = data.get('week')

        if not pdf_id or not source or not week:
            self.send_json({'error': 'Missing required parameters: pdf_id, source, week'})
            return

        try:
            # Get chunks for this PDF (or treat as single chunk if not chunked)
            conn = sqlite3.connect(str(Path.home() / 'clat_preparation' / 'revision_tracker.db'), check_same_thread=False)
            cursor = conn.cursor()

            # Check if PDF is chunked
            cursor.execute("""
                SELECT COUNT(*) FROM pdf_chunks WHERE parent_pdf_id = ?
            """, (pdf_id,))

            chunk_count = cursor.fetchone()[0]

            if chunk_count == 0:
                # Not chunked - treat as 1 chunk
                chunk_count = 1

            conn.close()

            # Create job in database
            job_id = self.assessment_jobs_db.create_job(pdf_id, chunk_count)

            # Launch background processor
            processor_path = Path(__file__).parent / 'assessment_processor.py'
            # Use venv python to ensure dependencies are available
            venv_python = Path(__file__).parent.parent / 'venv_clat' / 'bin' / 'python3'
            python_exe = str(venv_python) if venv_python.exists() else sys.executable

            # Start subprocess in background with output to log file
            log_file = open(f'/tmp/assessment_job_{job_id[:8]}.log', 'w')
            subprocess.Popen([
                python_exe,
                str(processor_path),
                job_id,
                pdf_id,
                source,
                week
            ], stdout=log_file, stderr=log_file)

            self.send_json({
                'job_id': job_id,
                'status': 'started',
                'message': 'Assessment creation started',
                'total_chunks': chunk_count
            })

        except Exception as e:
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    def handle_assessment_progress_get(self, job_id: str):
        """Handle GET /api/assessment-progress/{job_id} - Get current progress."""
        try:
            status = self.assessment_jobs_db.get_status(job_id)

            if not status:
                self.send_json({'error': 'Job not found'})
                return

            self.send_json(status)

        except Exception as e:
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    def handle_assessment_status_get(self, pdf_id: str):
        """Handle GET /api/assessment-status/{pdf_id} - Check if assessments exist."""
        try:
            conn = sqlite3.connect(str(Path.home() / 'clat_preparation' / 'revision_tracker.db'), check_same_thread=False)
            cursor = conn.cursor()

            # Check if PDF has chunks
            cursor.execute("""
                SELECT
                    COUNT(*) as total_chunks,
                    SUM(CASE WHEN assessment_created = 1 THEN 1 ELSE 0 END) as completed_chunks,
                    SUM(assessment_card_count) as total_cards
                FROM pdf_chunks
                WHERE parent_pdf_id = ?
            """, (pdf_id,))

            result = cursor.fetchone()

            if result and result[0] > 0:
                # PDF is chunked
                total_chunks, completed_chunks, total_cards = result
                has_assessments = completed_chunks > 0
                all_complete = completed_chunks == total_chunks
            else:
                # PDF is not chunked - check if any assessment jobs exist
                cursor.execute("""
                    SELECT COUNT(*), SUM(total_cards)
                    FROM assessment_jobs
                    WHERE parent_pdf_id = ? AND status = 'completed'
                """, (pdf_id,))

                job_result = cursor.fetchone()
                completed_jobs = job_result[0] if job_result else 0
                total_cards = job_result[1] if job_result and job_result[1] else 0

                has_assessments = completed_jobs > 0
                all_complete = completed_jobs > 0
                total_chunks = 1
                completed_chunks = 1 if all_complete else 0

            conn.close()

            self.send_json({
                'has_assessments': has_assessments,
                'all_complete': all_complete,
                'completed_chunks': completed_chunks or 0,
                'total_chunks': total_chunks or 0,
                'total_cards': total_cards or 0
            })

        except Exception as e:
            self.send_json({'error': str(e), 'trace': traceback.format_exc()})

    def send_json(self, data: dict):
        """Send JSON response."""
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Custom logging format."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    """Start the unified server."""
    parser = argparse.ArgumentParser(description='Unified CLAT Preparation Server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run on (default: 8001)')
    parser.add_argument('--no-auth', action='store_true', help='Disable authentication (dev mode)')
    args = parser.parse_args()

    # Initialize databases
    print("Initializing databases...")
    UnifiedHandler.assessment_db = AssessmentDatabase()
    UnifiedHandler.anki = AnkiConnector()

    math_db_path = Path(__file__).parent.parent / 'math_module' / 'math_tracker.db'
    UnifiedHandler.math_db = MathDatabase(str(math_db_path))

    UnifiedHandler.pdf_scanner = PDFScanner()

    # Initialize processing jobs database
    UnifiedHandler.processing_db = ProcessingJobsDB()
    print("✅ Processing jobs database initialized")

    # Initialize annotation manager
    UnifiedHandler.annotation_manager = AnnotationManager()
    print("✅ Annotation manager initialized")

    # Initialize PDF chunker
    UnifiedHandler.pdf_chunker = PdfChunker()
    print("✅ PDF chunker initialized")

    # Initialize assessment jobs database
    UnifiedHandler.assessment_jobs_db = AssessmentJobsDB()
    print("✅ Assessment jobs database initialized")

    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        UnifiedHandler.anthropic = Anthropic(api_key=api_key)
        print("✅ Anthropic API initialized")
    else:
        print("⚠️  Anthropic API key not set")

    # Initialize authentication (unless disabled)
    auth_enabled = False
    if not args.no_auth and AUTH_AVAILABLE:
        try:
            UnifiedHandler.google_auth = GoogleAuth()
            UnifiedHandler.user_db = UserDatabase()
            auth_enabled = True
            print("✅ Authentication enabled")
        except ValueError as e:
            print(f"⚠️  Authentication disabled: {e}")
            print("   Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable auth")
    elif args.no_auth:
        print("⚠️  Authentication disabled (dev mode)")
    elif not AUTH_AVAILABLE:
        print("⚠️  Authentication modules not available")

    # If auth is disabled, make all pages public
    if not auth_enabled:
        UnifiedHandler.PUBLIC_PAGES = ['*']

    # Start server (use ThreadingHTTPServer for concurrent requests)
    server_address = ('', args.port)
    httpd = ThreadingHTTPServer(server_address, UnifiedHandler)

    print("\n" + "="*70)
    print("          🎓 CLAT Preparation - Unified Server")
    print("="*70)
    print(f"\n🚀 Server running on: http://localhost:{args.port}")
    print(f"📁 Serving from: {Path(__file__).parent.parent / 'dashboard'}")
    print(f"🔐 Authentication: {'Enabled' if auth_enabled else 'Disabled'}")
    print(f"\n📡 All APIs unified on port {args.port}:")
    print(f"   • Dashboard HTML pages")
    print(f"   • Assessment API (/api/assessment/*)")
    print(f"   • Math API (/api/math/*)")
    print(f"   • GK Dashboard API (/api/dashboard, /api/pdfs/*)")
    if auth_enabled:
        print(f"   • Authentication (/auth/*)")

    print(f"\n🌐 Access Points:")
    if auth_enabled:
        print(f"   Login:             http://localhost:{args.port}/login.html")
    print(f"   Main Landing:      http://localhost:{args.port}/index.html")
    print(f"   GK Dashboard:      http://localhost:{args.port}/comprehensive_dashboard.html")
    print(f"   Assessment:        http://localhost:{args.port}/assessment.html")
    print(f"   Analytics:         http://localhost:{args.port}/analytics.html")
    print(f"   Math Settings:     http://localhost:{args.port}/math_settings.html")
    print(f"   Math Practice:     http://localhost:{args.port}/math_practice.html")
    print(f"   Math Admin:        http://localhost:{args.port}/math_admin.html")
    print(f"   Math Analytics:    http://localhost:{args.port}/math_analytics.html")

    print(f"\n⌨️  Press Ctrl+C to stop the server")
    print("="*70 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped.")


if __name__ == '__main__':
    main()
