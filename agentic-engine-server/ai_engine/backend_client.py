"""
Backend Client for Interview Scheduler AI Engine
Handles communication with Node.js backend API
"""

import requests
import json
from typing import Dict, Optional, List
import os
from datetime import datetime

class BackendClient:
    def __init__(self, base_url: str = "http://localhost:3009"):
        self.base_url = base_url
        self.session_id = None
    
    def start_session(self, recruiter_email: str, candidate_email: str) -> Dict:
        """Start a new scheduling session"""
        try:
            response = requests.post(f"{self.base_url}/start", json={
                "recruiterEmail": recruiter_email,
                "candidateEmail": candidate_email
            })
            response.raise_for_status()
            result = response.json()
            self.session_id = result.get("session", {}).get("id")
            return result
        except requests.exceptions.RequestException as e:
            print(f"Error starting session: {e}")
            return {"error": str(e)}
    
    def reset_session(self) -> Dict:
        """Reset the current session"""
        try:
            response = requests.post(f"{self.base_url}/reset")
            response.raise_for_status()
            self.session_id = None
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error resetting session: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict:
        """Get current session status"""
        try:
            response = requests.get(f"{self.base_url}/status")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting status: {e}")
            return {"error": str(e)}
    
    def send_email(self, to: str, subject: str, body: str) -> Dict:
        """Send email via backend"""
        try:
            response = requests.post(f"{self.base_url}/sendEmail", json={
                "to": to,
                "subject": subject,
                "body": body
            })
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending email: {e}")
            return {"error": str(e)}
    
    def receive_email(self, from_email: str, subject: str, body: str) -> Dict:
        """Simulate receiving email from candidate"""
        try:
            response = requests.post(f"{self.base_url}/receiveEmail", json={
                "from": from_email,
                "subject": subject,
                "body": body
            })
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error receiving email: {e}")
            return {"error": str(e)}
    
    def create_calendar_event(self, start_time: str, end_time: str, subject: str, location: str = "Virtual Interview") -> Dict:
        """Create calendar event via backend"""
        try:
            response = requests.post(f"{self.base_url}/createEvent", json={
                "startTime": start_time,
                "endTime": end_time,
                "subject": subject,
                "location": location
            })
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating calendar event: {e}")
            return {"error": str(e)}
    
    def is_backend_available(self) -> bool:
        """Check if backend is available"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False 

    def fetch_recruiter_slots(self, start: Optional[str] = None, end: Optional[str] = None, duration_minutes: int = 60, calendar_id: Optional[str] = None) -> Dict:
        """Fetch recruiter availability slots from backend /recruiterSlots"""
        try:
            params = {"durationMinutes": str(duration_minutes)}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            if calendar_id:
                params["calendarId"] = calendar_id
            print(f"[BackendClient] GET /recruiterSlots params={params}")
            response = requests.get(f"{self.base_url}/recruiterSlots", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            print(f"[BackendClient] /recruiterSlots -> {len(data.get('slots', []))} slots")
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching recruiter slots: {e}")
            return {"error": str(e)} 