#!/usr/bin/env python3
"""
Daily Summary Job

This script sends the daily summary email at 8 AM.
Run via LaunchAgent on Mac Mini.

Usage:
    python daily_summary_job.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Send daily summary email."""
    log_file = project_root / 'logs' / 'daily_summary.log'
    log_file.parent.mkdir(exist_ok=True)
    
    def log(message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        with open(log_file, 'a') as f:
            f.write(log_line + '\n')
    
    log("=" * 60)
    log("Starting daily summary job")
    
    try:
        from server.calendar_db import CalendarDatabase
        from server.email_service import DailySummaryService
        
        log("Initializing services...")
        calendar_db = CalendarDatabase()
        summary_service = DailySummaryService(calendar_db)
        
        log("Generating and sending summary...")
        recipient = 'arvind@orchids.edu.in'
        success = summary_service.generate_and_send_summary(recipient)
        
        if success:
            log(f"✅ Daily summary sent successfully to {recipient}")
        else:
            log(f"❌ Failed to send daily summary to {recipient}")
        
        return 0 if success else 1
        
    except Exception as e:
        log(f"❌ Error: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())

