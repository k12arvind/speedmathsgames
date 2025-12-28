#!/usr/bin/env python3
"""
Fix Database Paths Script

Converts all absolute paths in the database to relative paths for cross-machine compatibility.
This ensures the same database works on both MacBook Pro (/Users/arvind) and Mac Mini (/Users/arvindkumar).

Run this once to migrate existing data, then the pdf_scanner will store relative paths going forward.
"""

import sqlite3
import re
from pathlib import Path


def fix_paths():
    """Convert all absolute paths to relative paths in the database."""
    db_path = Path.home() / 'clat_preparation' / 'revision_tracker.db'
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Pattern to match /Users/username/ prefix
    # Matches: /Users/arvind/, /Users/arvindkumar/, etc.
    user_path_pattern = r'^/Users/[^/]+/'
    
    tables_and_columns = [
        ('pdfs', 'filepath'),
        ('pdf_chunks', 'chunk_path'),
        ('pdf_chunks', 'original_file_path'),
    ]
    
    total_fixed = 0
    
    for table, column in tables_and_columns:
        try:
            # Get all rows with absolute paths
            cursor.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} LIKE '/Users/%'")
            rows = cursor.fetchall()
            
            if not rows:
                print(f"✓ {table}.{column}: No absolute paths found")
                continue
            
            fixed_count = 0
            for rowid, old_path in rows:
                if old_path and old_path.startswith('/Users/'):
                    # Convert to relative path
                    new_path = re.sub(user_path_pattern, '', old_path)
                    cursor.execute(f"UPDATE {table} SET {column} = ? WHERE rowid = ?", (new_path, rowid))
                    fixed_count += 1
            
            conn.commit()
            print(f"✅ {table}.{column}: Fixed {fixed_count} paths")
            total_fixed += fixed_count
            
        except sqlite3.OperationalError as e:
            print(f"⚠️  {table}.{column}: Skipped - {e}")
    
    conn.close()
    
    print(f"\n🎉 Total paths fixed: {total_fixed}")
    print("Database is now cross-machine compatible!")


if __name__ == '__main__':
    print("=" * 60)
    print("Database Path Migration Tool")
    print("Converting absolute paths to relative paths...")
    print("=" * 60)
    print()
    fix_paths()

