import msal
import requests
from flask import current_app, url_for

class MSGraphService:
    @property
    def config(self):
        return current_app.config

    def _build_msal_app(self, cache=None):
        tenant_id = self.config.get('MS_TENANT_ID', 'common')
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        
        return msal.ConfidentialClientApplication(
            self.config['MS_CLIENT_ID'],
            authority=authority,
            client_credential=self.config['MS_CLIENT_SECRET'],
            token_cache=cache
        )

    def get_auth_url(self):
        app = self._build_msal_app()
        scopes = ["User.Read", "Mail.Send", "Mail.Read"]
        
        # Determine redirect URI dynamically or from config
        redirect_uri = self.config.get('MS_REDIRECT_URI') or url_for('auth.microsoft_callback', _external=True)
        print(f"DEBUG: Using Redirect URI: {redirect_uri}")

        return app.get_authorization_request_url(
            scopes,
            redirect_uri=redirect_uri
        )

    def get_token_from_code(self, code):
        app = self._build_msal_app()
        scopes = ["User.Read", "Mail.Send", "Mail.Read"]
        
        redirect_uri = self.config.get('MS_REDIRECT_URI') or url_for('auth.microsoft_callback', _external=True)
                
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
        return result

    def acquire_token_by_refresh_token(self, refresh_token):
        app = self._build_msal_app()
        scopes = ["User.Read", "Mail.Send", "Mail.Read"]
        # acquire_token_by_refresh_token handles the exchange
        result = app.acquire_token_by_refresh_token(refresh_token, scopes=scopes)
        return result

    def get_messages(self, access_token, filter_email=None, limit=10):
        """
        Fetch messages from the user's mailbox.
        If filter_email is provided, it filters for messages to/from that email.
        """
        endpoint = "https://graph.microsoft.com/v1.0/me/messages"
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json'
        }

        params = {
            '$top': limit,
            '$select': 'subject,receivedDateTime,bodyPreview,from,toRecipients,ccRecipients,id',
            '$orderby': 'receivedDateTime desc'
        }

        if filter_email:
            # Using $search is often more robust for finding interactions with a specific contact 
            # as it covers from, to, cc, etc. without complex OData syntax.
            params['$search'] = f'"{filter_email}"'
            # $orderby is NOT supported when using $search in MS Graph
            if '$orderby' in params:
                del params['$orderby']

        response = requests.get(endpoint, headers=headers, params=params)
        return response

    def send_email(self, access_token, to_email, subject, body, is_html=True, attachments=None, cc_email=None):
        """
        Send email via Microsoft Graph API.
        attachments: List of dicts -> {'name': 'file.pdf', 'content_bytes': 'base64str', 'content_type': 'application/pdf'}
        """
        endpoint = "https://graph.microsoft.com/v1.0/me/sendMail"
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json'
        }

        # Build Recipients
        to_recipients = [
            {"emailAddress": {"address": addr.strip()}} 
            for addr in to_email.split(';') if addr.strip()
        ]

        # Build CC Recipients
        cc_recipients = []
        if cc_email:
            cc_recipients = [
                {"emailAddress": {"address": addr.strip()}} 
                for addr in cc_email.split(';') if addr.strip() # Support multiple CCs
            ]

        # Wrap body in a styled container to enforce font consistency
        wrapped_body = f"""
        <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.3; color: #333;">
            {body}
        </div>
        """

        # Build Message
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if is_html else "Text",
                "content": wrapped_body if is_html else body
            },
            "toRecipients": to_recipients,
            "ccRecipients": cc_recipients
        }

        # Handle Attachments
        if attachments:
            msg_attachments = []
            for att in attachments:
                msg_attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att['name'],
                    "contentBytes": att['content_bytes']
                })
            message["attachments"] = msg_attachments

        payload = {
            "message": message,
            "saveToSentItems": "true"
        }

        response = requests.post(endpoint, headers=headers, json=payload)
        return response
