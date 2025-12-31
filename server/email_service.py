"""
Email Service using Gmail API

Handles:
- Sending emails via Gmail API
- Daily summary emails
- Bill reminder emails
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calendar_db import CalendarDatabase

# Gmail API scopes
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class EmailService:
    """Service for sending emails via Gmail API."""
    
    def __init__(self, db: CalendarDatabase = None, sender_email: str = 'k12arvind@gmail.com'):
        self.db = db or CalendarDatabase()
        self.sender_email = sender_email
        self._gmail_service = None
    
    def _get_gmail_service(self):
        """Get Gmail API service using stored credentials."""
        if self._gmail_service:
            return self._gmail_service
        
        account = self.db.get_account(self.sender_email)
        if not account or not account.get('access_token'):
            raise ValueError(f"No credentials found for {self.sender_email}")
        
        credentials = Credentials(
            token=account['access_token'],
            refresh_token=account['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self._get_client_id(),
            client_secret=self._get_client_secret(),
        )
        
        # Refresh if expired
        if account.get('token_expiry'):
            expiry = datetime.fromisoformat(account['token_expiry'].replace('Z', '+00:00'))
            if expiry < datetime.now(expiry.tzinfo):
                credentials.refresh(Request())
                self.db.update_tokens(
                    email=self.sender_email,
                    access_token=credentials.token,
                    expiry=credentials.expiry.isoformat() if credentials.expiry else None
                )
        
        self._gmail_service = build('gmail', 'v1', credentials=credentials)
        return self._gmail_service
    
    def _get_client_id(self) -> str:
        """Get OAuth client ID from credentials file."""
        import json
        creds_file = Path(__file__).parent.parent / 'config' / 'google_oauth_credentials.json'
        with open(creds_file) as f:
            data = json.load(f)
            return data.get('web', data.get('installed', {})).get('client_id')
    
    def _get_client_secret(self) -> str:
        """Get OAuth client secret from credentials file."""
        import json
        creds_file = Path(__file__).parent.parent / 'config' / 'google_oauth_credentials.json'
        with open(creds_file) as f:
            data = json.load(f)
            return data.get('web', data.get('installed', {})).get('client_secret')
    
    def send_email(self, to: str, subject: str, body_html: str, 
                   body_text: str = None) -> bool:
        """
        Send an email via Gmail API.
        
        Args:
            to: Recipient email
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional fallback)
            
        Returns:
            True if sent successfully
        """
        try:
            service = self._get_gmail_service()
            
            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to
            message['from'] = self.sender_email
            message['subject'] = subject
            
            # Add plain text part
            if body_text:
                message.attach(MIMEText(body_text, 'plain'))
            
            # Add HTML part
            message.attach(MIMEText(body_html, 'html'))
            
            # Encode message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send
            service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"Gmail API error: {e}")
            return False
        except Exception as e:
            print(f"Email error: {e}")
            return False


class DailySummaryService:
    """Service for generating and sending daily summary emails."""
    
    def __init__(self, calendar_db: CalendarDatabase = None):
        from calendar_db import CalendarDatabase
        from google_calendar_client import GoogleCalendarClient
        
        self.db = calendar_db or CalendarDatabase()
        self.calendar_client = GoogleCalendarClient(self.db)
        self.email_service = EmailService(self.db)
    
    def generate_and_send_summary(self, recipient: str = 'arvind@orchids.edu.in') -> bool:
        """
        Generate and send daily summary email.
        
        Args:
            recipient: Email address to send summary to
            
        Returns:
            True if sent successfully
        """
        # Check if already sent today
        if self.db.was_summary_sent_today(recipient):
            print(f"Summary already sent to {recipient} today")
            return True
        
        try:
            # Get today's events
            events = self.calendar_client.get_todays_events()
            
            # Get bill reminders
            bills = self._get_bill_reminders()
            
            # Generate email content
            subject = f"📅 Daily Summary - {datetime.now().strftime('%A, %B %d, %Y')}"
            html_body = self._generate_html_summary(events, bills)
            text_body = self._generate_text_summary(events, bills)
            
            # Send email
            success = self.email_service.send_email(
                to=recipient,
                subject=subject,
                body_html=html_body,
                body_text=text_body
            )
            
            # Log result
            self.db.log_summary(
                recipient=recipient,
                events_count=len(events),
                bills_count=len(bills),
                status='sent' if success else 'failed',
                error=None if success else 'Send failed'
            )
            
            return success
            
        except Exception as e:
            self.db.log_summary(
                recipient=recipient,
                events_count=0,
                bills_count=0,
                status='error',
                error=str(e)
            )
            print(f"Error generating summary: {e}")
            return False
    
    def _get_bill_reminders(self) -> List[Dict[str, Any]]:
        """Get bills that need reminders (7, 3, 2, 1, 0 days before due)."""
        from finance_db import FinanceDatabase
        
        finance_db = FinanceDatabase()
        today = datetime.now().date()
        
        reminders = []
        reminder_days = [7, 3, 2, 1, 0]
        
        # Get all active bills
        bills = finance_db.get_bills()
        
        for bill in bills:
            if not bill.get('next_due_date'):
                continue
            
            due_date = datetime.strptime(bill['next_due_date'], '%Y-%m-%d').date()
            days_until = (due_date - today).days
            
            if days_until in reminder_days:
                reminders.append({
                    **bill,
                    'days_until': days_until,
                    'urgency': 'due_today' if days_until == 0 else 
                              'urgent' if days_until <= 2 else 'upcoming'
                })
        
        # Sort by urgency (due today first)
        reminders.sort(key=lambda x: x['days_until'])
        return reminders
    
    def _generate_html_summary(self, events: List[Dict], 
                                bills: List[Dict]) -> str:
        """Generate HTML email body."""
        today_str = datetime.now().strftime('%A, %B %d, %Y')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                       background: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; 
                             border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                .header p {{ margin: 8px 0 0; opacity: 0.9; }}
                .section {{ padding: 20px; border-bottom: 1px solid #eee; }}
                .section:last-child {{ border-bottom: none; }}
                .section-title {{ font-size: 16px; font-weight: 600; color: #333; 
                                 margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
                .event {{ padding: 12px; margin-bottom: 8px; border-radius: 8px; 
                         border-left: 4px solid #4285f4; background: #f8f9fa; }}
                .event-time {{ font-size: 13px; color: #666; margin-bottom: 4px; }}
                .event-title {{ font-size: 15px; font-weight: 500; color: #333; }}
                .event-account {{ font-size: 12px; color: #888; margin-top: 4px; }}
                .bill {{ padding: 12px; margin-bottom: 8px; border-radius: 8px; }}
                .bill.due_today {{ background: #ffebee; border-left: 4px solid #f44336; }}
                .bill.urgent {{ background: #fff3e0; border-left: 4px solid #ff9800; }}
                .bill.upcoming {{ background: #e3f2fd; border-left: 4px solid #2196f3; }}
                .bill-name {{ font-weight: 500; color: #333; }}
                .bill-details {{ font-size: 13px; color: #666; margin-top: 4px; }}
                .bill-amount {{ font-weight: 600; color: #333; }}
                .no-items {{ color: #888; font-style: italic; padding: 20px; text-align: center; }}
                .footer {{ background: #f8f9fa; padding: 16px; text-align: center; 
                          font-size: 12px; color: #888; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📅 Daily Summary</h1>
                    <p>{today_str}</p>
                </div>
        """
        
        # Events Section
        html += """
                <div class="section">
                    <div class="section-title">📆 Today's Events</div>
        """
        
        if events:
            for event in events:
                time_str = self._format_event_time(event)
                color = event.get('color', '#4285f4')
                account_name = event.get('account_email', '').split('@')[0]
                
                html += f"""
                    <div class="event" style="border-left-color: {color};">
                        <div class="event-time">{time_str}</div>
                        <div class="event-title">{event.get('summary', 'No Title')}</div>
                        <div class="event-account">📧 {account_name}</div>
                    </div>
                """
        else:
            html += '<div class="no-items">No events scheduled for today</div>'
        
        html += '</div>'
        
        # Bills Section
        if bills:
            html += """
                <div class="section">
                    <div class="section-title">💰 Bill Reminders</div>
            """
            
            for bill in bills:
                urgency = bill.get('urgency', 'upcoming')
                days = bill.get('days_until', 0)
                
                if days == 0:
                    due_text = "⚠️ DUE TODAY"
                elif days == 1:
                    due_text = "Due tomorrow"
                else:
                    due_text = f"Due in {days} days"
                
                amount = f"₹{bill.get('typical_amount', 0):,.0f}" if bill.get('typical_amount') else "Amount varies"
                
                html += f"""
                    <div class="bill {urgency}">
                        <div class="bill-name">{bill.get('name', 'Unknown Bill')}</div>
                        <div class="bill-details">
                            {due_text} • {bill.get('category', 'Other')} • 
                            <span class="bill-amount">{amount}</span>
                        </div>
                    </div>
                """
            
            html += '</div>'
        
        # Footer
        html += """
                <div class="footer">
                    Sent from CLAT Preparation Hub • <a href="https://speedmathsgames.com/calendar.html">View Calendar</a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_text_summary(self, events: List[Dict], 
                                bills: List[Dict]) -> str:
        """Generate plain text email body."""
        today_str = datetime.now().strftime('%A, %B %d, %Y')
        
        text = f"📅 DAILY SUMMARY - {today_str}\n"
        text += "=" * 50 + "\n\n"
        
        # Events
        text += "📆 TODAY'S EVENTS\n"
        text += "-" * 30 + "\n"
        
        if events:
            for event in events:
                time_str = self._format_event_time(event)
                text += f"• {time_str} - {event.get('summary', 'No Title')}\n"
                text += f"  ({event.get('account_email', '')})\n\n"
        else:
            text += "No events scheduled for today.\n\n"
        
        # Bills
        if bills:
            text += "💰 BILL REMINDERS\n"
            text += "-" * 30 + "\n"
            
            for bill in bills:
                days = bill.get('days_until', 0)
                if days == 0:
                    due_text = "DUE TODAY!"
                elif days == 1:
                    due_text = "Due tomorrow"
                else:
                    due_text = f"Due in {days} days"
                
                amount = f"₹{bill.get('typical_amount', 0):,.0f}" if bill.get('typical_amount') else "Amount varies"
                text += f"• {bill.get('name', 'Unknown')} - {due_text}\n"
                text += f"  Category: {bill.get('category', 'Other')}, Amount: {amount}\n\n"
        
        text += "\n" + "=" * 50 + "\n"
        text += "View online: https://speedmathsgames.com/calendar.html\n"
        
        return text
    
    def _format_event_time(self, event: Dict) -> str:
        """Format event time for display."""
        if event.get('is_all_day'):
            return "All Day"
        
        start = event.get('start', '')
        if 'T' in start:
            try:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                return dt.strftime('%I:%M %p')
            except:
                pass
        return start


# Entry point for daily summary job
def send_daily_summary():
    """Send daily summary email. Called by LaunchAgent at 8 AM."""
    print(f"[{datetime.now()}] Starting daily summary...")
    
    service = DailySummaryService()
    success = service.generate_and_send_summary(recipient='arvind@orchids.edu.in')
    
    if success:
        print(f"[{datetime.now()}] Daily summary sent successfully!")
    else:
        print(f"[{datetime.now()}] Failed to send daily summary")
    
    return success


if __name__ == '__main__':
    # Test run
    send_daily_summary()

