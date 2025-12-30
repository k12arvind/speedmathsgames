#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
health_db.py

Database operations for Personal Workout/Health Module.
Tracks weight, workouts, diet, blood reports, and health goals.

Access restricted to: Arvind & Deepa only
Both users can view each other's data.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class HealthDatabase:
    """Database manager for personal health tracking."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'health_tracker.db'
        self.db_path = Path(db_path)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Health Profiles
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_profiles (
                    user_id TEXT PRIMARY KEY,
                    current_weight REAL,
                    target_weight REAL,
                    height_cm REAL,
                    date_of_birth TEXT,
                    blood_group TEXT,
                    gender TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Weight Log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weight_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    weight REAL NOT NULL,
                    body_fat_percent REAL,
                    muscle_mass REAL,
                    notes TEXT,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Workouts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    workout_date TEXT NOT NULL,
                    workout_type TEXT NOT NULL,
                    duration_minutes INTEGER,
                    intensity TEXT,
                    exercises TEXT,
                    calories_burned INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Exercise Library
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercise_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    equipment TEXT,
                    description TEXT,
                    is_custom INTEGER DEFAULT 0
                )
            ''')
            
            # Workout Templates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workout_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    workout_type TEXT,
                    exercises TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Diet Log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS diet_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    log_date TEXT NOT NULL,
                    meal_type TEXT,
                    meal_notes TEXT,
                    water_glasses INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Blood Reports
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blood_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    lab_name TEXT DEFAULT 'Healthians',
                    report_type TEXT,
                    pdf_path TEXT,
                    pdf_filename TEXT,
                    extracted_data TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Blood Parameters (extracted values)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blood_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    parameter_name TEXT NOT NULL,
                    parameter_category TEXT,
                    value REAL,
                    unit TEXT,
                    reference_min REAL,
                    reference_max REAL,
                    is_abnormal INTEGER DEFAULT 0,
                    recorded_date TEXT NOT NULL,
                    FOREIGN KEY (report_id) REFERENCES blood_reports(id) ON DELETE CASCADE
                )
            ''')
            
            # Parameter Reference (standard reference ranges)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parameter_reference (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter_name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    unit TEXT,
                    reference_min_male REAL,
                    reference_max_male REAL,
                    reference_min_female REAL,
                    reference_max_female REAL,
                    description TEXT
                )
            ''')
            
            # Health Goals
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    goal_type TEXT,
                    goal_description TEXT,
                    target_value REAL,
                    target_date TEXT,
                    current_value REAL,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_weight_log_user ON weight_log(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_weight_log_date ON weight_log(recorded_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workouts_user ON workouts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(workout_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diet_log_user ON diet_log(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diet_log_date ON diet_log(log_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blood_reports_user ON blood_reports(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blood_parameters_report ON blood_parameters(report_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blood_parameters_name ON blood_parameters(parameter_name)')
            
            # Initialize default parameter references
            self._init_parameter_references(cursor)
    
    def _init_parameter_references(self, cursor):
        """Initialize standard blood parameter references."""
        references = [
            # Hematology
            ('Hemoglobin', 'hematology', 'g/dL', 13.0, 17.0, 12.0, 15.0, 'Oxygen-carrying protein in blood'),
            ('WBC Count', 'hematology', 'cells/mcL', 4500, 11000, 4500, 11000, 'White blood cells'),
            ('RBC Count', 'hematology', 'million/mcL', 4.5, 5.5, 4.0, 5.0, 'Red blood cells'),
            ('Platelet Count', 'hematology', 'lakh/mcL', 1.5, 4.0, 1.5, 4.0, 'Blood clotting cells'),
            ('Hematocrit', 'hematology', '%', 38.8, 50.0, 34.9, 44.5, 'Percentage of blood volume occupied by RBCs'),
            ('MCV', 'hematology', 'fL', 80, 100, 80, 100, 'Mean Corpuscular Volume'),
            ('MCH', 'hematology', 'pg', 27, 33, 27, 33, 'Mean Corpuscular Hemoglobin'),
            ('MCHC', 'hematology', 'g/dL', 32, 36, 32, 36, 'Mean Corpuscular Hemoglobin Concentration'),
            
            # Diabetes
            ('Fasting Blood Sugar', 'diabetes', 'mg/dL', 70, 100, 70, 100, 'Blood glucose after fasting'),
            ('HbA1c', 'diabetes', '%', 4.0, 5.6, 4.0, 5.6, 'Average blood sugar over 3 months'),
            ('Post Prandial Blood Sugar', 'diabetes', 'mg/dL', 70, 140, 70, 140, 'Blood glucose after meal'),
            ('Random Blood Sugar', 'diabetes', 'mg/dL', 70, 140, 70, 140, 'Blood glucose at any time'),
            
            # Lipid Profile
            ('Total Cholesterol', 'lipid', 'mg/dL', 0, 200, 0, 200, 'Total blood cholesterol'),
            ('HDL Cholesterol', 'lipid', 'mg/dL', 40, 60, 50, 60, 'Good cholesterol'),
            ('LDL Cholesterol', 'lipid', 'mg/dL', 0, 100, 0, 100, 'Bad cholesterol'),
            ('Triglycerides', 'lipid', 'mg/dL', 0, 150, 0, 150, 'Blood fats'),
            ('VLDL Cholesterol', 'lipid', 'mg/dL', 5, 40, 5, 40, 'Very low density lipoprotein'),
            ('Total/HDL Ratio', 'lipid', 'ratio', 0, 5, 0, 5, 'Cardiovascular risk indicator'),
            
            # Liver Function
            ('SGOT (AST)', 'liver', 'U/L', 0, 40, 0, 32, 'Aspartate aminotransferase'),
            ('SGPT (ALT)', 'liver', 'U/L', 0, 41, 0, 33, 'Alanine aminotransferase'),
            ('Bilirubin Total', 'liver', 'mg/dL', 0.1, 1.2, 0.1, 1.2, 'Liver waste product'),
            ('Bilirubin Direct', 'liver', 'mg/dL', 0, 0.3, 0, 0.3, 'Conjugated bilirubin'),
            ('Alkaline Phosphatase', 'liver', 'U/L', 44, 147, 44, 147, 'Enzyme in liver and bones'),
            ('GGT', 'liver', 'U/L', 0, 60, 0, 40, 'Gamma-glutamyl transferase'),
            ('Total Protein', 'liver', 'g/dL', 6.0, 8.3, 6.0, 8.3, 'Total blood protein'),
            ('Albumin', 'liver', 'g/dL', 3.5, 5.0, 3.5, 5.0, 'Main blood protein'),
            ('Globulin', 'liver', 'g/dL', 2.0, 3.5, 2.0, 3.5, 'Immune proteins'),
            ('A/G Ratio', 'liver', 'ratio', 1.0, 2.0, 1.0, 2.0, 'Albumin/Globulin ratio'),
            
            # Kidney Function
            ('Creatinine', 'kidney', 'mg/dL', 0.7, 1.3, 0.6, 1.1, 'Kidney waste product'),
            ('BUN', 'kidney', 'mg/dL', 7, 20, 7, 20, 'Blood Urea Nitrogen'),
            ('Urea', 'kidney', 'mg/dL', 15, 45, 15, 45, 'Kidney waste product'),
            ('Uric Acid', 'kidney', 'mg/dL', 3.5, 7.2, 2.5, 6.2, 'Purine breakdown product'),
            ('eGFR', 'kidney', 'mL/min', 90, 120, 90, 120, 'Estimated Glomerular Filtration Rate'),
            ('BUN/Creatinine Ratio', 'kidney', 'ratio', 10, 20, 10, 20, 'Kidney function indicator'),
            
            # Thyroid
            ('TSH', 'thyroid', 'mIU/L', 0.4, 4.0, 0.4, 4.0, 'Thyroid Stimulating Hormone'),
            ('T3 Total', 'thyroid', 'ng/dL', 80, 200, 80, 200, 'Triiodothyronine'),
            ('T4 Total', 'thyroid', 'mcg/dL', 5.0, 12.0, 5.0, 12.0, 'Thyroxine'),
            ('Free T3', 'thyroid', 'pg/mL', 2.0, 4.4, 2.0, 4.4, 'Free Triiodothyronine'),
            ('Free T4', 'thyroid', 'ng/dL', 0.8, 1.8, 0.8, 1.8, 'Free Thyroxine'),
            
            # Vitamins & Minerals
            ('Vitamin D', 'vitamins', 'ng/mL', 30, 100, 30, 100, '25-Hydroxy Vitamin D'),
            ('Vitamin B12', 'vitamins', 'pg/mL', 200, 900, 200, 900, 'Cobalamin'),
            ('Iron', 'vitamins', 'mcg/dL', 60, 170, 50, 150, 'Serum Iron'),
            ('Ferritin', 'vitamins', 'ng/mL', 30, 400, 15, 150, 'Iron storage protein'),
            ('Calcium', 'vitamins', 'mg/dL', 8.5, 10.5, 8.5, 10.5, 'Serum Calcium'),
            ('Phosphorus', 'vitamins', 'mg/dL', 2.5, 4.5, 2.5, 4.5, 'Serum Phosphorus'),
            ('Magnesium', 'vitamins', 'mg/dL', 1.7, 2.2, 1.7, 2.2, 'Serum Magnesium'),
            ('Sodium', 'vitamins', 'mEq/L', 136, 145, 136, 145, 'Serum Sodium'),
            ('Potassium', 'vitamins', 'mEq/L', 3.5, 5.0, 3.5, 5.0, 'Serum Potassium'),
            ('Chloride', 'vitamins', 'mEq/L', 98, 106, 98, 106, 'Serum Chloride'),
            ('Folic Acid', 'vitamins', 'ng/mL', 3.0, 17.0, 3.0, 17.0, 'Vitamin B9'),
        ]
        
        for ref in references:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO parameter_reference 
                    (parameter_name, category, unit, reference_min_male, reference_max_male,
                     reference_min_female, reference_max_female, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ref)
            except sqlite3.IntegrityError:
                pass  # Already exists
    
    # =========================================================================
    # HEALTH PROFILES
    # =========================================================================
    
    def get_profile(self, user_id: str) -> Optional[Dict]:
        """Get user health profile."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM health_profiles WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def save_profile(self, user_id: str, data: Dict) -> bool:
        """Save or update health profile."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO health_profiles 
                (user_id, current_weight, target_weight, height_cm, date_of_birth,
                 blood_group, gender, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user_id,
                data.get('current_weight'),
                data.get('target_weight'),
                data.get('height_cm'),
                data.get('date_of_birth'),
                data.get('blood_group'),
                data.get('gender')
            ))
            return True
    
    # =========================================================================
    # WEIGHT TRACKING
    # =========================================================================
    
    def get_weight_log(self, user_id: str, days: int = 90) -> List[Dict]:
        """Get weight log for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM weight_log 
                WHERE user_id = ? AND recorded_at >= date('now', ?)
                ORDER BY recorded_at DESC
            ''', (user_id, f'-{days} days'))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_weight_logs(self, days: int = 90) -> Dict[str, List[Dict]]:
        """Get weight logs for all users (Arvind & Deepa can see each other)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM weight_log 
                WHERE recorded_at >= date('now', ?)
                ORDER BY user_id, recorded_at DESC
            ''', (f'-{days} days',))
            
            result = {'arvind': [], 'deepa': []}
            for row in cursor.fetchall():
                data = dict(row)
                if data['user_id'] in result:
                    result[data['user_id']].append(data)
            return result
    
    def log_weight(self, user_id: str, weight: float, data: Optional[Dict] = None) -> int:
        """Log a weight entry."""
        data = data or {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO weight_log (user_id, weight, body_fat_percent, muscle_mass, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                weight,
                data.get('body_fat_percent'),
                data.get('muscle_mass'),
                data.get('notes')
            ))
            
            # Update current weight in profile
            cursor.execute('''
                UPDATE health_profiles SET current_weight = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (weight, user_id))
            
            return cursor.lastrowid
    
    def delete_weight_entry(self, entry_id: int, user_id: str) -> bool:
        """Delete a weight entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM weight_log WHERE id = ? AND user_id = ?', (entry_id, user_id))
            return cursor.rowcount > 0
    
    # =========================================================================
    # WORKOUTS
    # =========================================================================
    
    def get_workouts(self, user_id: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Get workouts with optional user filter."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('''
                    SELECT * FROM workouts 
                    WHERE user_id = ? AND workout_date >= date('now', ?)
                    ORDER BY workout_date DESC
                ''', (user_id, f'-{days} days'))
            else:
                cursor.execute('''
                    SELECT * FROM workouts 
                    WHERE workout_date >= date('now', ?)
                    ORDER BY workout_date DESC, user_id
                ''', (f'-{days} days',))
            
            workouts = []
            for row in cursor.fetchall():
                workout = dict(row)
                if workout.get('exercises'):
                    try:
                        workout['exercises'] = json.loads(workout['exercises'])
                    except:
                        pass
                workouts.append(workout)
            return workouts
    
    def get_workout(self, workout_id: int) -> Optional[Dict]:
        """Get a specific workout."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM workouts WHERE id = ?', (workout_id,))
            row = cursor.fetchone()
            if row:
                workout = dict(row)
                if workout.get('exercises'):
                    try:
                        workout['exercises'] = json.loads(workout['exercises'])
                    except:
                        pass
                return workout
            return None
    
    def log_workout(self, user_id: str, data: Dict) -> int:
        """Log a workout."""
        exercises = json.dumps(data.get('exercises', [])) if data.get('exercises') else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workouts 
                (user_id, workout_date, workout_type, duration_minutes, intensity,
                 exercises, calories_burned, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('workout_date', date.today().strftime('%Y-%m-%d')),
                data['workout_type'],
                data.get('duration_minutes'),
                data.get('intensity'),
                exercises,
                data.get('calories_burned'),
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def update_workout(self, workout_id: int, data: Dict) -> bool:
        """Update a workout."""
        exercises = json.dumps(data.get('exercises', [])) if data.get('exercises') else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE workouts 
                SET workout_date = ?, workout_type = ?, duration_minutes = ?,
                    intensity = ?, exercises = ?, calories_burned = ?, notes = ?
                WHERE id = ?
            ''', (
                data.get('workout_date'),
                data.get('workout_type'),
                data.get('duration_minutes'),
                data.get('intensity'),
                exercises,
                data.get('calories_burned'),
                data.get('notes'),
                workout_id
            ))
            return cursor.rowcount > 0
    
    def delete_workout(self, workout_id: int) -> bool:
        """Delete a workout."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM workouts WHERE id = ?', (workout_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # WORKOUT TEMPLATES
    # =========================================================================
    
    def get_workout_templates(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get workout templates."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    'SELECT * FROM workout_templates WHERE user_id = ? ORDER BY name',
                    (user_id,)
                )
            else:
                cursor.execute('SELECT * FROM workout_templates ORDER BY user_id, name')
            
            templates = []
            for row in cursor.fetchall():
                template = dict(row)
                if template.get('exercises'):
                    try:
                        template['exercises'] = json.loads(template['exercises'])
                    except:
                        pass
                templates.append(template)
            return templates
    
    def save_workout_template(self, user_id: str, data: Dict) -> int:
        """Save a workout template."""
        exercises = json.dumps(data.get('exercises', [])) if data.get('exercises') else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workout_templates (user_id, name, workout_type, exercises, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                data['name'],
                data.get('workout_type'),
                exercises,
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def delete_workout_template(self, template_id: int) -> bool:
        """Delete a workout template."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM workout_templates WHERE id = ?', (template_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # DIET LOG
    # =========================================================================
    
    def get_diet_log(self, user_id: Optional[str] = None, days: int = 7) -> List[Dict]:
        """Get diet log entries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('''
                    SELECT * FROM diet_log 
                    WHERE user_id = ? AND log_date >= date('now', ?)
                    ORDER BY log_date DESC, meal_type
                ''', (user_id, f'-{days} days'))
            else:
                cursor.execute('''
                    SELECT * FROM diet_log 
                    WHERE log_date >= date('now', ?)
                    ORDER BY log_date DESC, user_id, meal_type
                ''', (f'-{days} days',))
            return [dict(row) for row in cursor.fetchall()]
    
    def log_meal(self, user_id: str, data: Dict) -> int:
        """Log a meal."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO diet_log (user_id, log_date, meal_type, meal_notes, water_glasses)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('log_date', date.today().strftime('%Y-%m-%d')),
                data.get('meal_type'),
                data.get('meal_notes'),
                data.get('water_glasses', 0)
            ))
            return cursor.lastrowid
    
    def update_meal(self, meal_id: int, data: Dict) -> bool:
        """Update a meal entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE diet_log 
                SET log_date = ?, meal_type = ?, meal_notes = ?, water_glasses = ?
                WHERE id = ?
            ''', (
                data.get('log_date'),
                data.get('meal_type'),
                data.get('meal_notes'),
                data.get('water_glasses'),
                meal_id
            ))
            return cursor.rowcount > 0
    
    def delete_meal(self, meal_id: int) -> bool:
        """Delete a meal entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM diet_log WHERE id = ?', (meal_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # BLOOD REPORTS
    # =========================================================================
    
    def get_blood_reports(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get blood reports."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    'SELECT * FROM blood_reports WHERE user_id = ? ORDER BY report_date DESC',
                    (user_id,)
                )
            else:
                cursor.execute('SELECT * FROM blood_reports ORDER BY report_date DESC')
            
            reports = []
            for row in cursor.fetchall():
                report = dict(row)
                if report.get('extracted_data'):
                    try:
                        report['extracted_data'] = json.loads(report['extracted_data'])
                    except:
                        pass
                reports.append(report)
            return reports
    
    def get_blood_report(self, report_id: int) -> Optional[Dict]:
        """Get a specific blood report with parameters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blood_reports WHERE id = ?', (report_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            report = dict(row)
            if report.get('extracted_data'):
                try:
                    report['extracted_data'] = json.loads(report['extracted_data'])
                except:
                    pass
            
            # Get parameters
            cursor.execute(
                'SELECT * FROM blood_parameters WHERE report_id = ? ORDER BY parameter_category, parameter_name',
                (report_id,)
            )
            report['parameters'] = [dict(r) for r in cursor.fetchall()]
            
            return report
    
    def add_blood_report(self, user_id: str, data: Dict) -> int:
        """Add a blood report."""
        extracted_data = json.dumps(data.get('extracted_data', {})) if data.get('extracted_data') else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO blood_reports 
                (user_id, report_date, lab_name, report_type, pdf_path, pdf_filename, extracted_data, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data['report_date'],
                data.get('lab_name', 'Healthians'),
                data.get('report_type'),
                data.get('pdf_path'),
                data.get('pdf_filename'),
                extracted_data,
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def add_blood_parameters(self, report_id: int, user_id: str, report_date: str, 
                            parameters: List[Dict]) -> int:
        """Add extracted blood parameters for a report."""
        count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for param in parameters:
                # Get reference ranges
                cursor.execute(
                    'SELECT * FROM parameter_reference WHERE parameter_name = ?',
                    (param['parameter_name'],)
                )
                ref = cursor.fetchone()
                
                # Determine if abnormal
                is_abnormal = 0
                ref_min = param.get('reference_min')
                ref_max = param.get('reference_max')
                
                if ref:
                    ref = dict(ref)
                    # Use reference ranges from our table if not provided
                    if ref_min is None:
                        ref_min = ref.get('reference_min_male')  # Default to male, can be updated per user
                    if ref_max is None:
                        ref_max = ref.get('reference_max_male')
                
                if param.get('value') is not None:
                    if ref_min is not None and param['value'] < ref_min:
                        is_abnormal = 1
                    elif ref_max is not None and param['value'] > ref_max:
                        is_abnormal = 1
                
                cursor.execute('''
                    INSERT INTO blood_parameters 
                    (report_id, user_id, parameter_name, parameter_category, value,
                     unit, reference_min, reference_max, is_abnormal, recorded_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    report_id,
                    user_id,
                    param['parameter_name'],
                    param.get('parameter_category'),
                    param.get('value'),
                    param.get('unit'),
                    ref_min,
                    ref_max,
                    is_abnormal,
                    report_date
                ))
                count += 1
        return count
    
    def delete_blood_report(self, report_id: int) -> bool:
        """Delete a blood report and its parameters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM blood_reports WHERE id = ?', (report_id,))
            return cursor.rowcount > 0
    
    def get_parameter_history(self, user_id: str, parameter_name: str, months: int = 24) -> List[Dict]:
        """Get historical values for a specific parameter."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM blood_parameters 
                WHERE user_id = ? AND parameter_name = ? 
                AND recorded_date >= date('now', ?)
                ORDER BY recorded_date
            ''', (user_id, parameter_name, f'-{months} months'))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_parameters_latest(self, user_id: str) -> List[Dict]:
        """Get latest values for all parameters for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT bp.*, pr.description 
                FROM blood_parameters bp
                LEFT JOIN parameter_reference pr ON bp.parameter_name = pr.parameter_name
                WHERE bp.user_id = ?
                AND bp.id IN (
                    SELECT MAX(id) FROM blood_parameters 
                    WHERE user_id = ? 
                    GROUP BY parameter_name
                )
                ORDER BY bp.parameter_category, bp.parameter_name
            ''', (user_id, user_id))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_parameter_reference(self) -> List[Dict]:
        """Get all parameter references."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parameter_reference ORDER BY category, parameter_name')
            return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # HEALTH GOALS
    # =========================================================================
    
    def get_goals(self, user_id: Optional[str] = None, status: str = 'active') -> List[Dict]:
        """Get health goals."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    'SELECT * FROM health_goals WHERE user_id = ? AND status = ? ORDER BY created_at DESC',
                    (user_id, status)
                )
            else:
                cursor.execute(
                    'SELECT * FROM health_goals WHERE status = ? ORDER BY user_id, created_at DESC',
                    (status,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def add_goal(self, user_id: str, data: Dict) -> int:
        """Add a health goal."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO health_goals 
                (user_id, goal_type, goal_description, target_value, target_date, current_value, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('goal_type'),
                data.get('goal_description'),
                data.get('target_value'),
                data.get('target_date'),
                data.get('current_value'),
                data.get('notes')
            ))
            return cursor.lastrowid
    
    def update_goal(self, goal_id: int, data: Dict) -> bool:
        """Update a health goal."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE health_goals 
                SET goal_type = ?, goal_description = ?, target_value = ?,
                    target_date = ?, current_value = ?, status = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('goal_type'),
                data.get('goal_description'),
                data.get('target_value'),
                data.get('target_date'),
                data.get('current_value'),
                data.get('status'),
                data.get('notes'),
                goal_id
            ))
            return cursor.rowcount > 0
    
    def delete_goal(self, goal_id: int) -> bool:
        """Delete a health goal."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM health_goals WHERE id = ?', (goal_id,))
            return cursor.rowcount > 0
    
    # =========================================================================
    # DASHBOARD
    # =========================================================================
    
    def get_dashboard_summary(self, user_id: str) -> Dict:
        """Get health dashboard summary for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Profile
            cursor.execute('SELECT * FROM health_profiles WHERE user_id = ?', (user_id,))
            profile = cursor.fetchone()
            profile = dict(profile) if profile else {}
            
            # Latest weight
            cursor.execute('''
                SELECT * FROM weight_log WHERE user_id = ? ORDER BY recorded_at DESC LIMIT 1
            ''', (user_id,))
            latest_weight = cursor.fetchone()
            
            # Weight trend (last 7 entries)
            cursor.execute('''
                SELECT weight, recorded_at FROM weight_log 
                WHERE user_id = ? ORDER BY recorded_at DESC LIMIT 7
            ''', (user_id,))
            weight_trend = [dict(r) for r in cursor.fetchall()]
            
            # Workouts this week
            cursor.execute('''
                SELECT COUNT(*) as count, SUM(duration_minutes) as total_minutes
                FROM workouts WHERE user_id = ? AND workout_date >= date('now', '-7 days')
            ''', (user_id,))
            week_workouts = cursor.fetchone()
            
            # Workouts this month
            cursor.execute('''
                SELECT COUNT(*) as count FROM workouts 
                WHERE user_id = ? AND workout_date >= date('now', '-30 days')
            ''', (user_id,))
            month_workouts = cursor.fetchone()
            
            # Latest blood report
            cursor.execute('''
                SELECT * FROM blood_reports WHERE user_id = ? ORDER BY report_date DESC LIMIT 1
            ''', (user_id,))
            latest_report = cursor.fetchone()
            
            # Abnormal parameters count
            cursor.execute('''
                SELECT COUNT(*) as count FROM blood_parameters bp
                WHERE bp.user_id = ? AND bp.is_abnormal = 1
                AND bp.id IN (
                    SELECT MAX(id) FROM blood_parameters 
                    WHERE user_id = ? GROUP BY parameter_name
                )
            ''', (user_id, user_id))
            abnormal_params = cursor.fetchone()
            
            # Active goals
            cursor.execute('''
                SELECT COUNT(*) as count FROM health_goals 
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            active_goals = cursor.fetchone()
            
            return {
                'profile': profile,
                'latest_weight': dict(latest_weight) if latest_weight else None,
                'weight_trend': weight_trend,
                'workouts_this_week': week_workouts['count'] if week_workouts else 0,
                'workout_minutes_this_week': week_workouts['total_minutes'] if week_workouts else 0,
                'workouts_this_month': month_workouts['count'] if month_workouts else 0,
                'latest_blood_report': dict(latest_report) if latest_report else None,
                'abnormal_parameters': abnormal_params['count'] if abnormal_params else 0,
                'active_goals': active_goals['count'] if active_goals else 0
            }

