import requests
import os
from datetime import datetime
from typing import Optional


class ButtondownPublisher:
    """Publisher for the newsletter to Buttondown"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Buttondown publisher
        
        Args:
            api_key: Buttondown API key (optional, defaults to environment variable)
        """
        self.api_key = api_key or os.environ.get("BUTTONDOWN_API_KEY")
        if not self.api_key:
            raise ValueError("Buttondown API key is required. Set it as an environment variable or pass it to the constructor.")
        
        self.api_url = "https://api.buttondown.email/v1/emails"
    
    def publish(self, content: str, subject: Optional[str] = None, status: Optional[str] = None) -> dict:
        """
        Publish the newsletter to Buttondown
        
        Args:
            content: Newsletter content
            subject: Newsletter subject (optional, defaults to standard format with date)
            status: Newsletter status (optional, defaults to environment variable or "draft")
            
        Returns:
            dict: Response from the Buttondown API
        """
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Format the subject with today's date if not provided
        if not subject:
            today = datetime.now().strftime('%B %d, %Y')
            subject = f"LLM Daily: {today}"
        
        # Get newsletter status from environment variable or default to "draft"
        if not status:
            status = os.environ.get("NEWSLETTER_STATUS", "draft")
        
        data = {
            "subject": subject,
            "body": content,
            "status": status  # "draft" for human review or "scheduled" for automatic sending
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data)
            
            if response.status_code == 201:
                print(f"Newsletter successfully created in Buttondown with ID: {response.json().get('id')}")
                return response.json()
            else:
                print(f"Error creating newsletter: {response.status_code}")
                print(response.text)
                return {"error": response.text, "status_code": response.status_code}
                
        except Exception as e:
            print(f"Exception during API call: {e}")
            return {"error": str(e)}
