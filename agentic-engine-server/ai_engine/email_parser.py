"""
Email Parser for Interview Scheduler AI Engine
Extracts candidate proposed slots from natural language email responses
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

class EmailParser:
    def __init__(self, llm_model: str = "gemini-1.5-flash"):
        self.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0)
        self.parsing_prompt = self._create_parsing_prompt()
    
    def _create_parsing_prompt(self) -> ChatPromptTemplate:
        """Create prompt template for parsing candidate email responses"""
        return ChatPromptTemplate.from_template("""
You are an expert at parsing interview scheduling emails. Extract proposed interview slots from the candidate's email response.

Email from candidate:
{email_content}

Instructions:
1. Extract all proposed interview times mentioned by the candidate
2. Convert them to ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SSZ)
3. Handle relative times like "tomorrow", "next week", "Monday"
4. Handle time ranges like "2-4 PM", "morning", "afternoon"
5. If candidate says they're "flexible" or "anytime", extract specific times they mention
6. If no specific times mentioned, return empty list

Current date and time: {current_datetime}

Return ONLY a JSON array of ISO datetime strings. Example:
["2024-01-15T14:00:00Z", "2024-01-16T10:00:00Z"]

If no specific times found, return: []
""")
    
    def parse_candidate_response(self, email_content: str) -> List[str]:
        """
        Parse candidate email response to extract proposed interview slots
        
        Args:
            email_content: The email body from candidate
            
        Returns:
            List of ISO datetime strings representing proposed slots
        """
        try:
            current_datetime = datetime.now().isoformat()
            
            # Use LLM to parse the email
            response = self.llm.invoke(
                self.parsing_prompt.format(
                    email_content=email_content,
                    current_datetime=current_datetime
                )
            )
            
            # Extract JSON from response
            parsed_slots = self._extract_json_from_response(response.content)
            
            # Validate and clean the slots
            validated_slots = self._validate_slots(parsed_slots)
            
            return validated_slots
            
        except Exception as e:
            print(f"Error parsing candidate response: {e}")
            # Fallback to regex parsing
            return self._fallback_regex_parsing(email_content)
    
    def _extract_json_from_response(self, response_content: str) -> List[str]:
        """Extract JSON array from LLM response"""
        try:
            # Look for JSON array in the response
            import json
            # Find JSON array pattern
            json_match = re.search(r'\[.*?\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Try to parse the entire response as JSON
                return json.loads(response_content)
        except json.JSONDecodeError:
            print("Failed to parse JSON from LLM response")
            return []
    
    def _validate_slots(self, slots: List[str]) -> List[str]:
        """Validate and clean parsed slots"""
        validated_slots = []
        
        for slot in slots:
            try:
                # Try different parsing approaches
                slot_clean = slot.strip()
                
                # Handle UTC format with Z suffix
                if slot_clean.endswith('Z'):
                    # Try parsing with Z suffix first
                    try:
                        datetime.strptime(slot_clean, '%Y-%m-%dT%H:%M:%SZ')
                        validated_slots.append(slot_clean)
                        continue
                    except ValueError:
                        pass
                    
                    # Try parsing with milliseconds
                    try:
                        datetime.strptime(slot_clean, '%Y-%m-%dT%H:%M:%S.%fZ')
                        validated_slots.append(slot_clean)
                        continue
                    except ValueError:
                        pass
                
                # Try standard ISO format
                try:
                    datetime.fromisoformat(slot_clean.replace('Z', '+00:00'))
                    validated_slots.append(slot_clean)
                    continue
                except ValueError:
                    pass
                
                # Try other common formats
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M']:
                    try:
                        datetime.strptime(slot_clean, fmt)
                        validated_slots.append(slot_clean)
                        break
                    except ValueError:
                        continue
                else:
                    print(f"Invalid datetime format: {slot}")
                    
            except Exception as e:
                print(f"Error validating slot {slot}: {e}")
                continue
        
        return validated_slots
    
    def _fallback_regex_parsing(self, email_content: str) -> List[str]:
        """
        Fallback regex parsing for common time patterns
        Used when LLM parsing fails
        """
        slots = []
        
        # Common patterns for time extraction
        patterns = [
            r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)',  # 2:30 PM
            r'(\d{1,2})\s*(AM|PM|am|pm)',          # 2 PM
            r'(\d{1,2}):(\d{2})',                  # 14:30
            r'(\d{1,2})\s*([ap]m)',                # 2 pm
        ]
        
        # This is a simplified fallback - in practice, you'd want more sophisticated parsing
        # For demo purposes, we'll return empty list and let the AI handle it
        return slots
    
    def extract_scheduling_intent(self, email_content: str) -> Dict:
        """
        Extract scheduling intent from candidate response
        
        Returns:
            Dict with intent classification and confidence
        """
        intent_prompt = ChatPromptTemplate.from_template("""
Analyze this candidate email response for scheduling intent:

Email: {email_content}

Classify the intent as one of:
- "proposed_slots": Candidate proposed specific time slots
- "flexible": Candidate is flexible but no specific times
- "unavailable": Candidate is unavailable for proposed times
- "unclear": Intent is unclear or ambiguous

Return JSON: {{"intent": "intent_type", "confidence": 0.9, "reasoning": "explanation"}}
""")
        
        try:
            response = self.llm.invoke(
                intent_prompt.format(email_content=email_content)
            )
            
            # Extract JSON from response
            import json
            json_match = re.search(r'\{.*?\}', response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"intent": "unclear", "confidence": 0.5, "reasoning": "Failed to parse"}
                
        except Exception as e:
            return {"intent": "unclear", "confidence": 0.3, "reasoning": f"Error: {e}"} 