"""
Slot Manager for Interview Scheduler AI Engine
Handles recruiter availability and slot intersection logic
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz

class SlotManager:
    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)
        self.recruiter_availability = self._generate_default_availability()
    
    def _generate_default_availability(self) -> List[Dict]:
        """
        Generate default recruiter availability for demo
        Available: Mon-Fri, 9 AM - 5 PM, 1-hour slots
        """
        availability = []
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Generate slots for next 2 weeks
        for day_offset in range(14):
            current_date = base_date + timedelta(days=day_offset)
            
            # Skip weekends (5=Saturday, 6=Sunday)
            if current_date.weekday() >= 5:
                continue
            
            # Generate 1-hour slots from 9 AM to 5 PM
            for hour in range(9, 17):
                slot_start = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(hours=1)
                
                # Ensure consistent UTC formatting
                availability.append({
                    "start": slot_start.isoformat() + "Z",  # Add Z for UTC
                    "end": slot_end.isoformat() + "Z",      # Add Z for UTC
                    "available": True,
                    "duration": 60  # minutes
                })
        
        print(f"[SlotManager] Generated default availability: {len(availability)} slots")
        return availability
    
    def get_available_slots(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Get available recruiter slots within date range"""
        print(f"[SlotManager.get_available_slots] called with start_date={start_date}, end_date={end_date}")
        if not start_date:
            start_date = datetime.now().isoformat() + "Z"  # Add Z for UTC consistency
        if not end_date:
            end_date = (datetime.now() + timedelta(days=14)).isoformat() + "Z"  # Add Z for UTC consistency
        
        available_slots = []
        for slot in self.recruiter_availability:
            if start_date <= slot["start"] <= end_date and slot["available"]:
                available_slots.append(slot)
        print(f"[SlotManager.get_available_slots] returning {len(available_slots)} slots in range")
        return available_slots
    
    def find_intersection(self, candidate_slots: List[str]) -> List[Dict]:
        """
        Find intersection between candidate proposed slots and recruiter availability
        
        Args:
            candidate_slots: List of ISO datetime strings from candidate
            
        Returns:
            List of matching slots with intersection details
        """
        print(f"[SlotManager.find_intersection] candidate_slots={candidate_slots}")
        intersections = []
        
        for candidate_slot in candidate_slots:
            try:
                # Handle different ISO formats more robustly
                candidate_slot_clean = candidate_slot.strip()
                candidate_dt = None
                
                # Try parsing with fromisoformat first (most reliable)
                try:
                    if candidate_slot_clean.endswith('Z'):
                        # Handle UTC format by replacing Z with +00:00
                        candidate_slot_clean = candidate_slot_clean[:-1] + '+00:00'
                    
                    candidate_dt = datetime.fromisoformat(candidate_slot_clean)
                    print(f"[SlotManager.find_intersection] parsed candidate slot: {candidate_slot} -> {candidate_dt}")
                    
                except ValueError:
                    # Fallback to strptime for different formats
                    print(f"[SlotManager.find_intersection] fromisoformat failed, trying strptime for {candidate_slot}")
                    
                    if candidate_slot_clean.endswith('Z'):
                        # Parse UTC format: 2025-08-25T14:00:00Z
                        candidate_dt = datetime.strptime(candidate_slot_clean, '%Y-%m-%dT%H:%M:%SZ')
                        candidate_dt = candidate_dt.replace(tzinfo=pytz.UTC)
                    elif '.000Z' in candidate_slot_clean:
                        # Parse format with milliseconds: 2025-08-25T14:00:00.000Z
                        candidate_dt = datetime.strptime(candidate_slot_clean, '%Y-%m-%dT%H:%M:%S.%fZ')
                        candidate_dt = candidate_dt.replace(tzinfo=pytz.UTC)
                    else:
                        # Try other common formats
                        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M']:
                            try:
                                candidate_dt = datetime.strptime(candidate_slot_clean, fmt)
                                break
                            except ValueError:
                                continue
                    
                    if candidate_dt:
                        print(f"[SlotManager.find_intersection] parsed with strptime: {candidate_dt}")
                    else:
                        print(f"[SlotManager.find_intersection] Failed to parse {candidate_slot} with any known format")
                        continue
                
                # Ensure candidate_dt is timezone-aware
                if candidate_dt.tzinfo is None:
                    candidate_dt = pytz.UTC.localize(candidate_dt)
                
                # Find matching recruiter slots
                for recruiter_slot in self.recruiter_availability:
                    if not recruiter_slot["available"]:
                        continue
                    
                    try:
                        # Parse recruiter slots (they should be in UTC)
                        recruiter_start = datetime.fromisoformat(recruiter_slot["start"].replace('Z', '+00:00'))
                        recruiter_end = datetime.fromisoformat(recruiter_slot["end"].replace('Z', '+00:00'))
                        
                        # Ensure recruiter times are timezone-aware
                        if recruiter_start.tzinfo is None:
                            recruiter_start = pytz.UTC.localize(recruiter_start)
                        if recruiter_end.tzinfo is None:
                            recruiter_end = pytz.UTC.localize(recruiter_end)
                        
                        print(f"[SlotManager.find_intersection] checking recruiter slot: {recruiter_start} - {recruiter_end}")
                        
                        # Check if candidate slot overlaps with recruiter slot
                        if (recruiter_start <= candidate_dt < recruiter_end):
                            intersections.append({
                                "candidate_slot": candidate_slot,
                                "recruiter_slot": recruiter_slot,
                                "intersection_start": candidate_dt.isoformat(),
                                "intersection_end": recruiter_end.isoformat(),
                                "duration": recruiter_slot["duration"]
                            })
                            print(f"[SlotManager.find_intersection] match found: {candidate_slot} within {recruiter_slot['start']} - {recruiter_slot['end']}")
                            break
                            
                    except ValueError as recruiter_parse_error:
                        print(f"[SlotManager.find_intersection] Error parsing recruiter slot: {recruiter_parse_error}")
                        continue
                        
            except Exception as e:
                print(f"[SlotManager.find_intersection] Error processing candidate slot {candidate_slot}: {e}")
                continue
        
        print(f"[SlotManager.find_intersection] total intersections={len(intersections)}")
        return intersections
    
    def get_best_match(self, intersections: List[Dict]) -> Optional[Dict]:
        """Get the best matching slot from intersections"""
        if not intersections:
            print("[SlotManager.get_best_match] no intersections available")
            return None
        print(f"[SlotManager.get_best_match] returning first of {len(intersections)} intersections")
        return intersections[0]
    
    def mark_slot_booked(self, slot_start: str, slot_end: str):
        """Mark a slot as booked (unavailable)"""
        for slot in self.recruiter_availability:
            if slot["start"] == slot_start and slot["end"] == slot_end:
                slot["available"] = False
                print(f"[SlotManager.mark_slot_booked] marked as booked: {slot_start} - {slot_end}")
                break 