"""
Canvas Authentication for Panther Instructor Engagement Reports
Handles API token-based authentication with Canvas LMS
"""

import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, 
    QLineEdit, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SimpleBrowserAuthDialog(QDialog):
    """
    Browser auth dialog for Canvas API token setup
    Instructs user to manually create API token in Canvas
    """
    
    def __init__(self, canvas_url: str, parent=None):
        super().__init__(parent)
        self.canvas_url = canvas_url.rstrip('/')
        self.api_token = None
        
        self.setWindowTitle("Canvas API Token Setup")
        self.setMinimumSize(600, 450)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("First Time Setup - Panther Instructor Engagement")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "<b>First-time setup: Create a Canvas API token for automatic login</b><br><br>"
            "<b>Step 1:</b> Click 'Open Canvas Settings' below<br>"
            "<b>Step 2:</b> In Canvas, scroll down to <b>Approved Integrations</b><br>"
            "<b>Step 3:</b> Click <b>+ New Access Token</b><br>"
            "<b>Step 4:</b> Purpose: <b>Panther Instructor Engagement</b><br>"
            "<b>Step 5:</b> Leave expiration blank (never expires)<br>"
            "<b>Step 6:</b> Click <b>Generate Token</b><br>"
            "<b>Step 7:</b> Copy the token and paste below<br><br>"
            "<i>Note: You only need to do this once. Your token will be saved securely.</i>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Open button
        open_btn = QPushButton("Open Canvas Settings")
        open_btn.setStyleSheet(f"background-color: #770000; color: white; padding: 10px; font-weight: bold;")
        open_btn.clicked.connect(self.open_canvas_settings)
        layout.addWidget(open_btn)
        
        # Token input
        token_label = QLabel("Paste your API token:")
        token_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(token_label)
        
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Paste token here...")
        self.token_input.setMinimumHeight(40)
        self.token_input.returnPressed.connect(self.save_token)
        layout.addWidget(self.token_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Save Token")
        ok_btn.setStyleSheet(f"background-color: #770000; color: white; padding: 8px; font-weight: bold;")
        ok_btn.clicked.connect(self.save_token)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    def open_canvas_settings(self):
        """Open Canvas settings page in browser"""
        settings_url = f"{self.canvas_url}/profile/settings"
        webbrowser.open(settings_url)
    
    def save_token(self):
        """Save API token"""
        token = self.token_input.text().strip()
        if token:
            self.api_token = token
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "No Token",
                "Please paste your Canvas API token."
            )
    
    def get_token(self) -> str:
        """Get the API token"""
        return self.api_token


class TokenBasedCanvasClient:
    """
    Simple Canvas API client using bearer token authentication
    """
    
    def __init__(self, base_url: str, api_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = None
        
        if api_token:
            self.set_token(api_token)
    
    def set_token(self, api_token: str):
        """Set API token and create session"""
        import requests
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def test_connection(self) -> bool:
        """Test Canvas API connection"""
        if not self.session:
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/users/self",
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def get_user_info(self) -> dict:
        """Get current user information"""
        if not self.session:
            return {}
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/users/self",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {}
