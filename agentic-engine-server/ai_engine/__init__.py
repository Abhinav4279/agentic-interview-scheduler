"""
AI Engine for Interview Scheduler
Main package for the AI-driven interview scheduling system
"""

from .slot_manager import SlotManager
from .email_parser import EmailParser
from .backend_client import BackendClient

__version__ = "1.0.0"
__all__ = ["SlotManager", "EmailParser", "BackendClient"] 