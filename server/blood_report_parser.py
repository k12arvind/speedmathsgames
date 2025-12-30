#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
blood_report_parser.py

Extract blood test parameters from PDF reports using:
1. PyMuPDF (fitz) for text extraction
2. Claude AI for intelligent parameter parsing

Optimized for Healthians lab reports.
"""

import os
import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Try to import Anthropic for AI parsing
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class BloodReportParser:
    """Parse blood test reports from PDF files."""
    
    # Common parameter name variations (for normalization)
    PARAMETER_ALIASES = {
        # Hemoglobin variations
        'haemoglobin': 'Hemoglobin',
        'hb': 'Hemoglobin',
        'hgb': 'Hemoglobin',
        
        # Blood sugar
        'fasting glucose': 'Fasting Blood Sugar',
        'fbs': 'Fasting Blood Sugar',
        'fasting blood glucose': 'Fasting Blood Sugar',
        'glucose fasting': 'Fasting Blood Sugar',
        'pp blood sugar': 'Post Prandial Blood Sugar',
        'ppbs': 'Post Prandial Blood Sugar',
        'post prandial glucose': 'Post Prandial Blood Sugar',
        'random glucose': 'Random Blood Sugar',
        'rbs': 'Random Blood Sugar',
        'glycosylated hemoglobin': 'HbA1c',
        'hba1c': 'HbA1c',
        'glycated hemoglobin': 'HbA1c',
        
        # Lipid profile
        'cholesterol total': 'Total Cholesterol',
        'serum cholesterol': 'Total Cholesterol',
        'hdl': 'HDL Cholesterol',
        'hdl-c': 'HDL Cholesterol',
        'hdl cholesterol': 'HDL Cholesterol',
        'ldl': 'LDL Cholesterol',
        'ldl-c': 'LDL Cholesterol',
        'ldl cholesterol': 'LDL Cholesterol',
        'tg': 'Triglycerides',
        'triglyceride': 'Triglycerides',
        'vldl': 'VLDL Cholesterol',
        'vldl-c': 'VLDL Cholesterol',
        
        # Liver function
        'ast': 'SGOT (AST)',
        'sgot': 'SGOT (AST)',
        'aspartate aminotransferase': 'SGOT (AST)',
        'alt': 'SGPT (ALT)',
        'sgpt': 'SGPT (ALT)',
        'alanine aminotransferase': 'SGPT (ALT)',
        'total bilirubin': 'Bilirubin Total',
        'bilirubin - total': 'Bilirubin Total',
        'direct bilirubin': 'Bilirubin Direct',
        'bilirubin - direct': 'Bilirubin Direct',
        'alp': 'Alkaline Phosphatase',
        'alk phos': 'Alkaline Phosphatase',
        'ggt': 'GGT',
        'gamma gt': 'GGT',
        'gamma-glutamyl transferase': 'GGT',
        
        # Kidney function
        'serum creatinine': 'Creatinine',
        'blood urea nitrogen': 'BUN',
        'serum urea': 'Urea',
        'uric acid': 'Uric Acid',
        'serum uric acid': 'Uric Acid',
        'egfr': 'eGFR',
        'gfr': 'eGFR',
        
        # Thyroid
        'tsh': 'TSH',
        'thyroid stimulating hormone': 'TSH',
        't3': 'T3 Total',
        't3 total': 'T3 Total',
        'triiodothyronine': 'T3 Total',
        't4': 'T4 Total',
        't4 total': 'T4 Total',
        'thyroxine': 'T4 Total',
        'free t3': 'Free T3',
        'ft3': 'Free T3',
        'free t4': 'Free T4',
        'ft4': 'Free T4',
        
        # Vitamins
        'vitamin d': 'Vitamin D',
        '25-oh vitamin d': 'Vitamin D',
        '25-hydroxy vitamin d': 'Vitamin D',
        'vit d': 'Vitamin D',
        'vitamin b12': 'Vitamin B12',
        'vit b12': 'Vitamin B12',
        'cyanocobalamin': 'Vitamin B12',
        'serum iron': 'Iron',
        'serum ferritin': 'Ferritin',
        'folate': 'Folic Acid',
        'folic acid': 'Folic Acid',
        
        # CBC
        'wbc': 'WBC Count',
        'white blood cells': 'WBC Count',
        'total leucocyte count': 'WBC Count',
        'tlc': 'WBC Count',
        'rbc': 'RBC Count',
        'red blood cells': 'RBC Count',
        'total rbc': 'RBC Count',
        'platelet': 'Platelet Count',
        'platelets': 'Platelet Count',
        'platelet count': 'Platelet Count',
        'hct': 'Hematocrit',
        'haematocrit': 'Hematocrit',
        'pcv': 'Hematocrit',
    }
    
    # Parameter categories
    CATEGORY_KEYWORDS = {
        'hematology': ['hemoglobin', 'wbc', 'rbc', 'platelet', 'hematocrit', 'mcv', 'mch', 'mchc'],
        'diabetes': ['glucose', 'sugar', 'hba1c', 'diabetes'],
        'lipid': ['cholesterol', 'hdl', 'ldl', 'triglyceride', 'vldl', 'lipid'],
        'liver': ['sgot', 'sgpt', 'ast', 'alt', 'bilirubin', 'alkaline', 'ggt', 'albumin', 'globulin', 'protein'],
        'kidney': ['creatinine', 'urea', 'bun', 'uric', 'egfr', 'gfr'],
        'thyroid': ['tsh', 't3', 't4', 'thyroid'],
        'vitamins': ['vitamin', 'iron', 'ferritin', 'calcium', 'phosphorus', 'magnesium', 'sodium', 'potassium', 'folic']
    }
    
    def __init__(self):
        """Initialize parser."""
        self.anthropic = None
        if ANTHROPIC_AVAILABLE:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if api_key:
                self.anthropic = Anthropic(api_key=api_key)
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract all text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        text_parts = []
        
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(text)
            doc.close()
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""
        
        return "\n\n".join(text_parts)
    
    def normalize_parameter_name(self, name: str) -> str:
        """
        Normalize parameter name to standard format.
        
        Args:
            name: Raw parameter name from report
            
        Returns:
            Normalized standard name
        """
        name_lower = name.lower().strip()
        
        # Check aliases
        if name_lower in self.PARAMETER_ALIASES:
            return self.PARAMETER_ALIASES[name_lower]
        
        # Check partial matches
        for alias, standard in self.PARAMETER_ALIASES.items():
            if alias in name_lower or name_lower in alias:
                return standard
        
        # Title case the original if no match
        return name.strip().title()
    
    def detect_category(self, parameter_name: str) -> str:
        """
        Detect category for a parameter.
        
        Args:
            parameter_name: Parameter name
            
        Returns:
            Category string
        """
        name_lower = parameter_name.lower()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return category
        
        return 'other'
    
    def parse_with_regex(self, text: str) -> List[Dict]:
        """
        Parse blood parameters using regex patterns.
        Fallback method when AI is not available.
        
        Args:
            text: Extracted PDF text
            
        Returns:
            List of parameter dicts
        """
        parameters = []
        
        # Pattern: Parameter name followed by value and optionally unit and reference range
        # Examples:
        # "Hemoglobin 14.5 g/dL 13.0-17.0"
        # "SGPT (ALT) : 25 U/L (0-40)"
        # "Total Cholesterol 185 mg/dL"
        
        patterns = [
            # Pattern 1: Name : Value Unit (Min-Max)
            r'([A-Za-z][A-Za-z0-9\s\(\)\-\/]+?)\s*[:\-]?\s*(\d+\.?\d*)\s*([A-Za-z/%]+)?\s*[\(\[]?\s*(\d+\.?\d*)?\s*[\-to]+\s*(\d+\.?\d*)?\s*[\)\]]?',
            
            # Pattern 2: Name Value Unit Reference
            r'([A-Za-z][A-Za-z\s\(\)\-]+)\s+(\d+\.?\d*)\s+([A-Za-z/]+)\s+(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',
        ]
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            for pattern in patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    try:
                        name = match[0].strip()
                        value = float(match[1]) if match[1] else None
                        unit = match[2].strip() if len(match) > 2 and match[2] else None
                        ref_min = float(match[3]) if len(match) > 3 and match[3] else None
                        ref_max = float(match[4]) if len(match) > 4 and match[4] else None
                        
                        # Skip if name is too short or looks like noise
                        if len(name) < 2 or name.isdigit():
                            continue
                        
                        normalized_name = self.normalize_parameter_name(name)
                        category = self.detect_category(normalized_name)
                        
                        param = {
                            'parameter_name': normalized_name,
                            'parameter_category': category,
                            'value': value,
                            'unit': unit,
                            'reference_min': ref_min,
                            'reference_max': ref_max
                        }
                        
                        # Avoid duplicates
                        if not any(p['parameter_name'] == normalized_name for p in parameters):
                            parameters.append(param)
                            
                    except (ValueError, IndexError):
                        continue
        
        return parameters
    
    def parse_with_ai(self, text: str) -> List[Dict]:
        """
        Parse blood parameters using Claude AI.
        More accurate than regex for complex reports.
        
        Args:
            text: Extracted PDF text
            
        Returns:
            List of parameter dicts
        """
        if not self.anthropic:
            print("Anthropic API not available, falling back to regex")
            return self.parse_with_regex(text)
        
        prompt = f"""You are a medical data extraction assistant. Extract all blood test parameters from the following lab report text.

For each parameter found, provide:
1. parameter_name: Standard medical name (e.g., "Hemoglobin", "Total Cholesterol", "TSH")
2. parameter_category: One of: hematology, diabetes, lipid, liver, kidney, thyroid, vitamins, other
3. value: The numeric value (as a number, not string)
4. unit: The unit of measurement (e.g., "g/dL", "mg/dL", "U/L")
5. reference_min: Lower reference range (if available)
6. reference_max: Upper reference range (if available)

Return ONLY a valid JSON array. No explanation or markdown, just the JSON.
If no valid parameters found, return an empty array: []

Lab Report Text:
{text[:8000]}

JSON Array:"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Extract JSON from response
            if response_text.startswith('['):
                json_str = response_text
            else:
                # Find JSON array in response
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                else:
                    print("Could not find JSON array in AI response")
                    return self.parse_with_regex(text)
            
            parameters = json.loads(json_str)
            
            # Normalize and validate
            validated = []
            for param in parameters:
                if not param.get('parameter_name') or param.get('value') is None:
                    continue
                
                normalized = {
                    'parameter_name': self.normalize_parameter_name(param['parameter_name']),
                    'parameter_category': param.get('parameter_category', self.detect_category(param['parameter_name'])),
                    'value': float(param['value']) if param.get('value') is not None else None,
                    'unit': param.get('unit'),
                    'reference_min': float(param['reference_min']) if param.get('reference_min') is not None else None,
                    'reference_max': float(param['reference_max']) if param.get('reference_max') is not None else None
                }
                validated.append(normalized)
            
            return validated
            
        except Exception as e:
            print(f"AI parsing error: {e}, falling back to regex")
            return self.parse_with_regex(text)
    
    def parse_report(self, pdf_path: str, use_ai: bool = True) -> Dict:
        """
        Parse a blood report PDF and extract parameters.
        
        Args:
            pdf_path: Path to PDF file
            use_ai: Whether to use AI parsing (recommended)
            
        Returns:
            Dict with extracted data
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            return {'success': False, 'error': 'PDF file not found'}
        
        # Extract text
        text = self.extract_text_from_pdf(str(pdf_path))
        
        if not text.strip():
            return {'success': False, 'error': 'Could not extract text from PDF'}
        
        # Parse parameters
        if use_ai and self.anthropic:
            parameters = self.parse_with_ai(text)
        else:
            parameters = self.parse_with_regex(text)
        
        # Try to extract report date from text
        report_date = self.extract_date(text)
        
        # Try to extract lab name
        lab_name = self.extract_lab_name(text)
        
        return {
            'success': True,
            'pdf_path': str(pdf_path),
            'pdf_filename': pdf_path.name,
            'report_date': report_date,
            'lab_name': lab_name,
            'parameters': parameters,
            'parameters_count': len(parameters),
            'raw_text_preview': text[:500] + '...' if len(text) > 500 else text
        }
    
    def extract_date(self, text: str) -> Optional[str]:
        """
        Extract report date from text.
        
        Args:
            text: PDF text
            
        Returns:
            Date string in YYYY-MM-DD format or None
        """
        # Common date patterns
        patterns = [
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',  # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',  # YYYY/MM/DD
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})',  # DD Month YYYY
        ]
        
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    
                    if len(groups[1]) > 2:  # Month name
                        day = int(groups[0])
                        month = months.get(groups[1][:3].lower(), 1)
                        year = int(groups[2])
                    elif len(groups[0]) == 4:  # YYYY first
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                    else:  # DD/MM/YYYY
                        day = int(groups[0])
                        month = int(groups[1])
                        year = int(groups[2])
                    
                    return f"{year:04d}-{month:02d}-{day:02d}"
                except:
                    continue
        
        return None
    
    def extract_lab_name(self, text: str) -> str:
        """
        Extract lab name from text.
        
        Args:
            text: PDF text
            
        Returns:
            Lab name or default
        """
        # Known labs
        labs = ['Healthians', 'Dr Lal PathLabs', 'SRL Diagnostics', 'Thyrocare', 
                'Metropolis', 'Apollo Diagnostics', 'Fortis', 'Max Lab']
        
        text_lower = text.lower()
        for lab in labs:
            if lab.lower() in text_lower:
                return lab
        
        return 'Healthians'  # Default as specified


# Convenience function for direct use
def parse_blood_report(pdf_path: str, use_ai: bool = True) -> Dict:
    """
    Parse a blood report PDF.
    
    Args:
        pdf_path: Path to PDF file
        use_ai: Whether to use AI parsing
        
    Returns:
        Parsed report data
    """
    parser = BloodReportParser()
    return parser.parse_report(pdf_path, use_ai)

