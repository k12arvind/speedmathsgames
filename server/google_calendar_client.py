"""
Google Calendar API Client

Handles:
- OAuth 2.0 flow for multiple accounts
- Calendar events CRUD operations
- Event syncing from multiple accounts
- Bill reminders sync to Google Calendar
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from server.calendar_db import CalendarDatabase

# OAuth 2.0 Scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',  # Full calendar access
    'https://www.googleapis.com/auth/gmail.send',  # Send emails
    'https://www.googleapis.com/auth/userinfo.email',  # Get user email
    'https://www.googleapis.com/auth/userinfo.profile',  # Get user profile
]

# Path to OAuth credentials file (downloaded from GCP Console)
CREDENTIALS_FILE = Path(__file__).parent.parent / 'config' / 'google_oauth_credentials.json'


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""
    
    def __init__(self, db: CalendarDatabase = None):
        self.db = db or CalendarDatabase()
        self._services = {}  # Cache for API service objects
    
    # =========================================================================
    # OAuth Flow
    # =========================================================================
    
    def get_auth_url(self, redirect_uri: str, state: str = None) -> str:
        """
        Generate OAuth authorization URL.
        
        Args:
            redirect_uri: URL to redirect after authorization
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL for user to visit
        """
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                f"OAuth credentials file not found at {CREDENTIALS_FILE}. "
                "Please download from Google Cloud Console."
            )
        
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )
        
        return auth_url
    
    def handle_oauth_callback(self, authorization_response: str, 
                               redirect_uri: str) -> Dict[str, Any]:
        """
        Handle OAuth callback and store tokens.
        
        Args:
            authorization_response: Full callback URL with code
            redirect_uri: Same redirect_uri used in get_auth_url
            
        Returns:
            Dict with user info and status
        """
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Get user info
        user_info = self._get_user_info(credentials)
        email = user_info.get('email')
        
        if not email:
            raise ValueError("Could not get email from Google account")
        
        # Determine color based on email domain
        color = self._get_account_color(email)
        
        # Store tokens
        tokens = {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
            'scopes': list(credentials.scopes) if credentials.scopes else SCOPES
        }
        
        # Check if this is the primary account
        is_primary = email == 'k12arvind@gmail.com'
        
        self.db.add_or_update_account(
            email=email,
            tokens=tokens,
            display_name=user_info.get('name'),
            is_primary=is_primary,
            color=color
        )
        
        return {
            'email': email,
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'is_primary': is_primary,
            'color': color
        }
    
    def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Get user profile info from Google."""
        service = build('oauth2', 'v2', credentials=credentials)
        return service.userinfo().get().execute()
    
    def _get_account_color(self, email: str) -> str:
        """Get display color based on email domain."""
        colors = {
            'gmail.com': '#4285f4',      # Google Blue
            'orchids.edu.in': '#34a853',  # Green
            'k12technoservices.com': '#ea4335'  # Red
        }
        domain = email.split('@')[1] if '@' in email else ''
        return colors.get(domain, '#fbbc05')  # Default Yellow
    
    # =========================================================================
    # Credentials Management
    # =========================================================================
    
    def _get_credentials(self, email: str) -> Optional[Credentials]:
        """Get valid credentials for an account, refreshing if needed."""
        account = self.db.get_account(email)
        if not account or not account.get('access_token'):
            return None
        
        credentials = Credentials(
            token=account['access_token'],
            refresh_token=account['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self._get_client_id(),
            client_secret=self._get_client_secret(),
            scopes=json.loads(account['scopes']) if account['scopes'] else SCOPES
        )
        
        # Check if expired and refresh
        if account.get('token_expiry'):
            expiry = datetime.fromisoformat(account['token_expiry'].replace('Z', '+00:00'))
            if expiry < datetime.now(expiry.tzinfo):
                try:
                    credentials.refresh(Request())
                    self.db.update_tokens(
                        email=email,
                        access_token=credentials.token,
                        expiry=credentials.expiry.isoformat() if credentials.expiry else None
                    )
                except Exception as e:
                    print(f"Failed to refresh token for {email}: {e}")
                    return None
        
        return credentials
    
    def _get_client_id(self) -> str:
        """Get OAuth client ID from credentials file."""
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
            return data.get('web', data.get('installed', {})).get('client_id')
    
    def _get_client_secret(self) -> str:
        """Get OAuth client secret from credentials file."""
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
            return data.get('web', data.get('installed', {})).get('client_secret')
    
    def _get_calendar_service(self, email: str):
        """Get or create Calendar API service for an account."""
        if email in self._services:
            return self._services[email]
        
        credentials = self._get_credentials(email)
        if not credentials:
            return None
        
        service = build('calendar', 'v3', credentials=credentials)
        self._services[email] = service
        return service
    
    # =========================================================================
    # Calendar Events - Read
    # =========================================================================
    
    def get_events(self, email: str, start_date: datetime, end_date: datetime,
                   max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get calendar events for a date range.
        
        Args:
            email: Google account email
            start_date: Start of date range
            end_date: End of date range
            max_results: Maximum events to return
            
        Returns:
            List of event dictionaries
        """
        service = self._get_calendar_service(email)
        if not service:
            return []
        
        try:
            self.db.update_sync_status(email, 'syncing')
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Transform to consistent format
            transformed = []
            for event in events:
                transformed.append(self._transform_event(event, email))
            
            # Cache events
            self.db.cache_events(transformed, email)
            self.db.update_sync_status(email, 'completed')
            
            return transformed
            
        except HttpError as e:
            error_msg = str(e)
            self.db.update_sync_status(email, 'error', error=error_msg)
            print(f"Error fetching events for {email}: {error_msg}")
            return []
    
    def get_events_all_accounts(self, start_date: datetime, 
                                 end_date: datetime) -> List[Dict[str, Any]]:
        """Get events from all configured accounts."""
        all_events = []
        accounts = self.db.get_all_accounts(active_only=True)
        
        for account in accounts:
            events = self.get_events(account['email'], start_date, end_date)
            all_events.extend(events)
        
        # Sort by start time
        all_events.sort(key=lambda x: x.get('start', ''))
        return all_events
    
    def get_todays_events(self) -> List[Dict[str, Any]]:
        """Get all events for today from all accounts."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return self.get_events_all_accounts(today, tomorrow)
    
    def _transform_event(self, event: Dict, email: str) -> Dict[str, Any]:
        """Transform Google Calendar event to consistent format."""
        start = event.get('start', {})
        end = event.get('end', {})
        
        # Handle all-day vs timed events
        is_all_day = 'date' in start
        start_time = start.get('date') or start.get('dateTime', '')
        end_time = end.get('date') or end.get('dateTime', '')
        
        account = self.db.get_account(email)
        
        return {
            'id': event.get('id'),
            'summary': event.get('summary', 'No Title'),
            'description': event.get('description'),
            'location': event.get('location'),
            'start': start_time,
            'end': end_time,
            'is_all_day': is_all_day,
            'status': event.get('status', 'confirmed'),
            'htmlLink': event.get('htmlLink'),
            'recurrence': event.get('recurrence'),
            'attendees': event.get('attendees'),
            'account_email': email,
            'color': account.get('color', '#4285f4') if account else '#4285f4',
            'source': 'google'
        }
    
    # =========================================================================
    # Calendar Events - Create/Update/Delete
    # =========================================================================
    
    def create_event(self, email: str, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new calendar event.
        
        Args:
            email: Google account to create event in
            event_data: Event details (title, start, end, description, location)
            
        Returns:
            Created event or None on failure
        """
        service = self._get_calendar_service(email)
        if not service:
            return None
        
        # Build event body
        event_body = {
            'summary': event_data.get('title'),
            'description': event_data.get('description'),
            'location': event_data.get('location'),
        }
        
        # Handle all-day vs timed
        if event_data.get('is_all_day'):
            event_body['start'] = {'date': event_data.get('start')[:10]}
            event_body['end'] = {'date': event_data.get('end')[:10]}
        else:
            event_body['start'] = {
                'dateTime': event_data.get('start'),
                'timeZone': 'Asia/Kolkata'
            }
            event_body['end'] = {
                'dateTime': event_data.get('end'),
                'timeZone': 'Asia/Kolkata'
            }
        
        # Add reminders
        if event_data.get('reminders'):
            event_body['reminders'] = {
                'useDefault': False,
                'overrides': event_data['reminders']
            }
        
        try:
            created = service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            
            return self._transform_event(created, email)
            
        except HttpError as e:
            print(f"Error creating event: {e}")
            return None
    
    def update_event(self, email: str, event_id: str, 
                     event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing calendar event."""
        service = self._get_calendar_service(email)
        if not service:
            return None
        
        try:
            # Get existing event
            existing = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Update fields
            if 'title' in event_data:
                existing['summary'] = event_data['title']
            if 'description' in event_data:
                existing['description'] = event_data['description']
            if 'location' in event_data:
                existing['location'] = event_data['location']
            
            # Update times
            if 'start' in event_data:
                if event_data.get('is_all_day'):
                    existing['start'] = {'date': event_data['start'][:10]}
                else:
                    existing['start'] = {
                        'dateTime': event_data['start'],
                        'timeZone': 'Asia/Kolkata'
                    }
            
            if 'end' in event_data:
                if event_data.get('is_all_day'):
                    existing['end'] = {'date': event_data['end'][:10]}
                else:
                    existing['end'] = {
                        'dateTime': event_data['end'],
                        'timeZone': 'Asia/Kolkata'
                    }
            
            updated = service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=existing
            ).execute()
            
            return self._transform_event(updated, email)
            
        except HttpError as e:
            print(f"Error updating event: {e}")
            return None
    
    def delete_event(self, email: str, event_id: str) -> bool:
        """Delete a calendar event."""
        service = self._get_calendar_service(email)
        if not service:
            return False
        
        try:
            service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            return True
            
        except HttpError as e:
            print(f"Error deleting event: {e}")
            return False
    
    # =========================================================================
    # Bill Sync to Google Calendar
    # =========================================================================
    
    def sync_bill_to_calendar(self, bill: Dict[str, Any], 
                               target_email: str = 'k12arvind@gmail.com') -> Optional[str]:
        """
        Create/update a calendar event for a bill due date.
        
        Args:
            bill: Bill data from finance module
            target_email: Google account to sync to
            
        Returns:
            Google event ID or None
        """
        due_date = bill.get('next_due_date') or bill.get('due_date')
        if not due_date:
            return None
        
        # Check if already synced
        existing_event_id = self.db.get_synced_bill(bill['id'], due_date)
        
        # Build event data
        event_data = {
            'title': f"💰 Bill Due: {bill.get('name')}",
            'description': (
                f"Category: {bill.get('category', 'Other')}\n"
                f"Amount: ₹{bill.get('typical_amount', 'N/A')}\n"
                f"Provider: {bill.get('provider', 'N/A')}\n"
                f"Account: {bill.get('account_number', 'N/A')}"
            ),
            'start': due_date,
            'end': due_date,
            'is_all_day': True,
            'reminders': [
                {'method': 'popup', 'minutes': 60 * 24 * 7},   # 7 days before
                {'method': 'popup', 'minutes': 60 * 24 * 3},   # 3 days before
                {'method': 'popup', 'minutes': 60 * 24 * 2},   # 2 days before
                {'method': 'popup', 'minutes': 60 * 24},       # 1 day before
                {'method': 'popup', 'minutes': 60 * 9},        # 9 AM on due date
            ]
        }
        
        if existing_event_id:
            # Update existing
            result = self.update_event(target_email, existing_event_id, event_data)
            return existing_event_id if result else None
        else:
            # Create new
            result = self.create_event(target_email, event_data)
            if result:
                self.db.record_bill_sync(bill['id'], result['id'], due_date)
                return result['id']
            return None
    
    # =========================================================================
    # Connection Test
    # =========================================================================
    
    def test_connection(self, email: str) -> Tuple[bool, str]:
        """Test if we can connect to Google Calendar for an account."""
        service = self._get_calendar_service(email)
        if not service:
            return False, "No valid credentials found"
        
        try:
            # Try to list calendars
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            return True, f"Connected! Found {len(calendars)} calendars."
        except HttpError as e:
            return False, f"API Error: {e}"
        except Exception as e:
            return False, f"Error: {e}"


# Singleton instance
_calendar_client = None

def get_calendar_client() -> GoogleCalendarClient:
    """Get singleton calendar client instance."""
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = GoogleCalendarClient()
    return _calendar_client

