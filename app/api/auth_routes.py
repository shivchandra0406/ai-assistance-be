from flask import Blueprint, jsonify, request, url_for, session, redirect
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.utils.response_handler import ResponseHandler
import os
import json
import pathlib

# Allow OAuth over HTTP for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

auth_bp = Blueprint('auth', __name__)

# Google OAuth configuration
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:5001/api/auth/callback"],
        "javascript_origins": ["http://localhost:5001", "http://localhost:3000"]
    }
}

# OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

@auth_bp.route('/login')
def login():
    """Initiate Google OAuth login flow"""
    try:
        # Create OAuth flow instance
        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=GOOGLE_CLIENT_CONFIG['web']['redirect_uris'][0]
        )
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to ensure refresh token
        )
        
        # Store the state in session
        session['state'] = state
        
        # Redirect user to Google's auth page
        return redirect(authorization_url)
    
    except Exception as e:
        print(f"Login error: {str(e)}")
        return ResponseHandler.error(
            error=str(e),
            message="Failed to initiate Google login"
        )

@auth_bp.route('/callback')
def oauth2callback():
    """Handle Google OAuth callback"""
    try:
        # Get state from session
        state = session.get('state')
        
        # Verify state
        if not state or state != request.args.get('state', ''):
            raise ValueError("Invalid state parameter")
        
        # Create flow instance
        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=SCOPES,
            state=state
        )
        flow.redirect_uri = GOOGLE_CLIENT_CONFIG['web']['redirect_uris'][0]
        
        # Get authorization code from request
        authorization_response = request.url
        if not request.args.get('code'):
            raise ValueError("No authorization code received")
            
        # Exchange authorization code for credentials
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Get user info
        user_info = get_user_info(credentials)
        if not user_info:
            raise ValueError("Failed to get user info")
        
        # Store user info and credentials in session
        session['user'] = user_info
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Redirect to frontend with success
        return redirect(f"http://localhost:3000/auth-success?user={json.dumps(user_info)}")
    
    except Exception as e:
        print(f"Callback error: {str(e)}")
        # Redirect to frontend with error
        return redirect(f"http://localhost:3000/auth-error?error={str(e)}")

@auth_bp.route('/user')
def get_current_user():
    """Get current authenticated user info"""
    try:
        user = session.get('user')
        if not user:
            return ResponseHandler.error(
                error="No authenticated user",
                message="Please login first",
                status_code=401
            )
        return ResponseHandler.success(
            data=user,
            message="Current user info retrieved"
        )
    except Exception as e:
        print(f"Get user error: {str(e)}")
        return ResponseHandler.error(
            error=str(e),
            message="Failed to get user info"
        )

@auth_bp.route('/logout')
def logout():
    """Logout user and clear session"""
    try:
        session.clear()
        return ResponseHandler.success(
            message="Successfully logged out"
        )
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return ResponseHandler.error(
            error=str(e),
            message="Failed to logout"
        )

def get_user_info(credentials):
    """Get user info from Google using OAuth credentials"""
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return {
            'id': user_info.get('id'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'verified_email': user_info.get('verified_email', False)
        }
    except Exception as e:
        print(f"Error getting user info: {str(e)}")
        return None
