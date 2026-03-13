import os
import requests
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MSGraphService:
    """
    Handles all interactions with the Microsoft Graph API.
    Specifically designed for the "Hybrid Smart" Phase 1 architecture to fetch
    Teams recordings without relying on massive internal cloud storage.
    """
    def __init__(self):
        # We allow lazy loading from environment variables directly, 
        # though production apps might pull from current_app.config
        self.tenant_id = os.getenv('MS_TENANT_ID')
        self.client_id = os.getenv('MS_CLIENT_ID')
        self.client_secret = os.getenv('MS_CLIENT_SECRET')
        self.base_url = "https://graph.microsoft.com/v1.0"
        
        if not self.client_id or not self.client_secret:
            logger.warning("MS_CLIENT_ID or MS_CLIENT_SECRET is missing. Graph API calls will fail.")

    def _acquire_token(self):
        """
        Acquire an App-Only access token from Azure AD using Client Credentials.
        This provides daemon-level access without user interaction.
        """
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            return response.json().get('access_token')
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to acquire MS Graph token: {str(e)}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    def _get_headers(self):
        """Generate Authorization headers with a fresh token."""
        token = self._acquire_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def ping(self):
        """Test authentication and connection to Graph API. Useful for diagnostic scripts."""
        try:
            headers = self._get_headers()
            # Fetch basic tenant details as a sanity check
            response = requests.get(f"{self.base_url}/organization", headers=headers)
            response.raise_for_status()
            return True, response.json()
        except Exception as e:
            return False, str(e)

    # ---------------------------------------------------------
    # Webhook Subscription Methods (Step 3.3)
    # ---------------------------------------------------------
    
    def create_meeting_subscription(self, notification_url, client_state):
        """
        Creates a Graph subscription to listen for when online meetings end.
        Requires active App-Only token.
        notification_url: Our Flask Webhook Endpoint (/api/v1/webhooks/teams)
        client_state: A secret token we use to verify the payload is from Microsoft.
        """
        headers = self._get_headers()
        # Subscriptions usually last up to roughly 4000 minutes (2.7 days)
        expiration = datetime.utcnow() + timedelta(days=2)
        
        payload = {
            "changeType": "updated",
            "notificationUrl": notification_url,
            "resource": "communications/onlineMeetings/?$filter=joinWebUrl eq 'all'",
            "expirationDateTime": expiration.isoformat() + "Z",
            "clientState": client_state
        }
        
        response = requests.post(f"{self.base_url}/subscriptions", headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()
        
    def renew_subscription(self, subscription_id):
        """
        Renews an existing subscription before it expires.
        """
        headers = self._get_headers()
        expiration = datetime.utcnow() + timedelta(days=2)
        
        payload = {
            "expirationDateTime": expiration.isoformat() + "Z"
        }
        
        response = requests.patch(f"{self.base_url}/subscriptions/{subscription_id}", headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()

    # ---------------------------------------------------------
    # Online Meetings
    # ---------------------------------------------------------

    def create_online_meeting(self, subject: str, start_dt: datetime, end_dt: datetime) -> dict:
        """
        Creates a Microsoft Teams online meeting using the Calendar Event workaround.
        This often works better with App-Only permissions than the direct onlineMeetings API.
        Returns a dict containing 'joinWebUrl'.
        """
        sender = os.getenv('MS_SENDER_EMAIL')
        if not sender:
            logger.error('[MSGraph] MS_SENDER_EMAIL not configured. Cannot create meeting.')
            return {}

        try:
            headers = self._get_headers()
            payload = {
                "subject": subject,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": "UTC"
                },
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness"
            }
            logger.debug(f'[MSGraph] Calendar Event Payload: {payload}')
            url = f"{self.base_url}/users/{sender}/calendar/events"
            response = requests.post(url, headers=headers, json=payload)
            
            if response.ok:
                data = response.json()
                # The join link is nested in onlineMeeting object for calendar events
                join_url = data.get('onlineMeeting', {}).get('joinUrl')
                if join_url:
                    return {'joinWebUrl': join_url}
                else:
                    logger.warning(f'[MSGraph] Calendar event created but no joinUrl found: {data}')
                    return {}
            else:
                logger.error(f'[MSGraph] create_online_meeting (Calendar API) failed ({response.status_code}): {response.text}')
                return {}
        except Exception as e:
            logger.error(f'[MSGraph] create_online_meeting exception: {e}')
            return {}

    # ---------------------------------------------------------
    # Email Sending (App-Only, via sender mailbox)
    # ---------------------------------------------------------

    def send_email(self, to_email: str, subject: str, html_body: str,
                   cc_email: str = None, sender_email: str = None,
                   attachments: list = None) -> bool:
        """
        Send an HTML email using app-only credentials.
        Requires MS_SENDER_EMAIL env var (or pass sender_email explicitly).
        attachments: List of dicts -> {'name': 'file.ics', 'content_bytes': 'base64str', 'content_type': 'text/calendar'}
        Returns True on success, False on failure.
        """
        sender = sender_email or os.getenv('MS_SENDER_EMAIL')
        if not sender:
            logger.error('[MSGraph] MS_SENDER_EMAIL not configured. Cannot send email.')
            return False

        if not self.client_id or not self.client_secret or not self.tenant_id:
            logger.error('[MSGraph] MS credentials not configured. Cannot send email.')
            return False

        try:
            headers = self._get_headers()
            to_recipients = [
                {'emailAddress': {'address': addr.strip()}}
                for addr in to_email.split(';') if addr.strip()
            ]
            cc_recipients = []
            if cc_email:
                cc_recipients = [
                    {'emailAddress': {'address': addr.strip()}}
                    for addr in cc_email.split(';') if addr.strip()
                ]

            message_payload = {
                'subject': subject,
                'body': {'contentType': 'HTML', 'content': html_body},
                'toRecipients': to_recipients,
                'ccRecipients': cc_recipients,
            }

            if attachments:
                api_attachments = []
                for att in attachments:
                    api_attachments.append({
                        '@odata.type': '#microsoft.graph.fileAttachment',
                        'name': att['name'],
                        'contentBytes': att['content_bytes'],
                        'contentType': att.get('content_type', 'application/octet-stream')
                    })
                message_payload['attachments'] = api_attachments

            payload = {
                'message': message_payload,
                'saveToSentItems': 'true'
            }

            url = f"{self.base_url}/users/{sender}/sendMail"
            response = requests.post(url, headers=headers, json=payload)
            if response.ok:
                return True
            else:
                logger.error(f'[MSGraph] sendMail failed ({response.status_code}): {response.text}')
                return False
        except Exception as e:
            logger.error(f'[MSGraph] send_email exception: {e}')
            return False

    # ---------------------------------------------------------
    # SharePoint / OneDrive Video Retrieval (Step 3.4)
    # ---------------------------------------------------------
    
    def get_drive_item(self, drive_id, item_id):
        """
        Retrieves the exact file metadata, including the highly-coveted 
        @microsoft.graph.downloadUrl (which bypasses auth for direct download/stream)
        based on the pointers we get from the Teams webhook.
        """
        headers = self._get_headers()
        url = f"{self.base_url}/drives/{drive_id}/items/{item_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'id': data.get('id'),
            'name': data.get('name'),
            'webUrl': data.get('webUrl'), # SharePoint browser view
            'downloadUrl': data.get('@microsoft.graph.downloadUrl'), # Direct raw MP4 bytes
            'size': data.get('size')
        }
