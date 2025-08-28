"""
Scheduler Agent for Interview Scheduler AI Engine
Main agent that orchestrates the interview scheduling workflow
"""

from typing import Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
import json
import os

from .slot_manager import SlotManager
from .email_parser import EmailParser
from .backend_client import BackendClient

class SchedulerAgent:
    def __init__(self, 
                 google_api_key: str,
                 backend_url: str = "http://localhost:3009",
                 llm_model: str = "gemini-1.5-flash"):
        
        # Initialize components
        self.slot_manager = SlotManager()
        self.email_parser = EmailParser(llm_model)
        self.backend_client = BackendClient(backend_url)
        
        # Initialize LLM (Gemini)
        os.environ["GOOGLE_API_KEY"] = google_api_key
        self.llm = ChatGoogleGenerativeAI(
            model=llm_model,
            temperature=0
        )
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Session state
        self.session_state = {
            "recruiter_email": None,
            "candidate_email": None,
            "current_stage": "initialized",
            "conversation_history": [],
            "proposed_slots": [],
            "confirmed_slot": None
        }
        
        # Initialize agent with tools
        self.agent = self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the LangChain agent with custom tools"""
        
        tools = [
            Tool(
                name="start_session",
                func=self._start_session_tool,
                description="Start a new interview scheduling session with recruiter and candidate emails"
            ),
            Tool(
                name="send_initial_email",
                func=self._send_initial_email_tool,
                description="Send initial email to candidate with available interview slots"
            ),
            Tool(
                name="parse_candidate_response",
                func=self._parse_candidate_response_tool,
                description="Parse candidate email response to extract proposed interview slots"
            ),
            Tool(
                name="find_slot_intersection",
                func=self._find_slot_intersection_tool,
                description="Find intersection between candidate proposed slots and recruiter availability"
            ),
            Tool(
                name="send_confirmation_email",
                func=self._send_confirmation_email_tool,
                description="Send confirmation email to candidate with confirmed interview slot"
            ),
            Tool(
                name="create_calendar_event",
                func=self._create_calendar_event_tool,
                description="Create calendar event for confirmed interview slot"
            ),
            Tool(
                name="send_follow_up_email",
                func=self._send_follow_up_email_tool,
                description="Send follow-up email asking for different times if no intersection found"
            ),
            Tool(
                name="get_session_status",
                func=self._get_session_status_tool,
                description="Get current session status and conversation history"
            )
        ]
        
        # Create agent
        agent = initialize_agent(
            tools,
            self.llm,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
        
        return agent

    def _refresh_recruiter_slots_from_backend(self, start: Optional[str] = None, end: Optional[str] = None, duration_minutes: int = 60) -> List[Dict]:
        """Fetch recruiter slots from backend and map to SlotManager availability format."""
        print(f"[SchedulerAgent] Refreshing recruiter slots from backend start={start} end={end} duration={duration_minutes}")
        data = self.backend_client.fetch_recruiter_slots(start=start, end=end, duration_minutes=duration_minutes)
        slots = data.get("slots", []) if isinstance(data, dict) else []
        mapped: List[Dict] = []
        for s in slots:
            start_iso = s.get("startTime")
            end_iso = s.get("endTime")
            if not start_iso or not end_iso:
                continue
            mapped.append({
                "start": start_iso,
                "end": end_iso,
                "available": True,
                "duration": duration_minutes
            })
        if mapped:
            self.slot_manager.recruiter_availability = mapped
            print(f"[SchedulerAgent] Updated recruiter_availability with {len(mapped)} slots")
        else:
            print("[SchedulerAgent] No slots fetched from backend; keeping existing availability")
        return mapped
    
    def _start_session_tool(self, recruiter_email: str, candidate_email: str) -> str:
        """Tool to start a new scheduling session"""
        try:
            self.session_state["recruiter_email"] = recruiter_email
            self.session_state["candidate_email"] = candidate_email
            self.session_state["current_stage"] = "session_started"
            
            # Start backend session
            result = self.backend_client.start_session(recruiter_email, candidate_email)
            
            return f"Session started successfully. Recruiter: {recruiter_email}, Candidate: {candidate_email}"
        except Exception as e:
            return f"Error starting session: {str(e)}"
    
    def _send_initial_email_tool(self, available_slots: str = "") -> str:
        """Tool to send initial email to candidate"""
        try:
            # Fetch latest recruiter availability from backend
            fetched = self._refresh_recruiter_slots_from_backend(duration_minutes=60)
            slots = fetched if fetched else self.slot_manager.get_available_slots()
            
            # Format slots for email
            slot_text = self._format_slots_for_email(slots[:5])  # Send first 5 slots
            
            email_body = f"""
Dear Candidate,

Thank you for your interest in the position. I would like to schedule an interview with you.

Here are some available time slots for the interview:

{slot_text}

Please let me know which time works best for you, or if you have other preferred times.

Best regards,
Recruiter
"""
            
            result = self.backend_client.send_email(
                to=self.session_state["candidate_email"],
                subject="Interview Scheduling - Available Slots",
                body=email_body
            )
            
            self.session_state["current_stage"] = "initial_email_sent"
            self.session_state["conversation_history"].append({
                "type": "email_sent",
                "content": email_body,
                "timestamp": "now"
            })
            
            return f"Initial email sent to {self.session_state['candidate_email']} with available slots"
        except Exception as e:
            return f"Error sending initial email: {str(e)}"
    
    def _parse_candidate_response_tool(self, email_content: str) -> str:
        """Tool to parse candidate email response"""
        try:
            # Parse candidate response
            proposed_slots = self.email_parser.parse_candidate_response(email_content)
            intent = self.email_parser.extract_scheduling_intent(email_content)
            
            self.session_state["proposed_slots"] = proposed_slots
            self.session_state["current_stage"] = "candidate_response_parsed"
            self.session_state["conversation_history"].append({
                "type": "email_received",
                "content": email_content,
                "parsed_slots": proposed_slots,
                "intent": intent,
                "timestamp": "now"
            })
            
            return f"Parsed candidate response. Intent: {intent['intent']}, Proposed slots: {proposed_slots}"
        except Exception as e:
            return f"Error parsing candidate response: {str(e)}"
    
    def _find_slot_intersection_tool(self, candidate_slots: str = "") -> str:
        """Tool to find intersection between candidate and recruiter slots"""
        try:
            # Ensure latest recruiter availability
            self._refresh_recruiter_slots_from_backend(duration_minutes=60)
            
            # Use parsed slots from session state
            slots = self.session_state["proposed_slots"]
            
            if not slots:
                return "No candidate slots to check for intersection"
            
            # Find intersections
            intersections = self.slot_manager.find_intersection(slots)
            best_match = self.slot_manager.get_best_match(intersections)
            
            if best_match:
                self.session_state["confirmed_slot"] = best_match
                self.session_state["current_stage"] = "slot_confirmed"
                return f"Found matching slot: {best_match['intersection_start']} - {best_match['intersection_end']}"
            else:
                self.session_state["current_stage"] = "no_intersection"
                return "No matching slots found between candidate and recruiter availability"
        except Exception as e:
            return f"Error finding slot intersection: {str(e)}"
    
    def _send_confirmation_email_tool(self, slot_details: str = "") -> str:
        """Tool to send confirmation email"""
        try:
            confirmed_slot = self.session_state["confirmed_slot"]
            if not confirmed_slot:
                return "No confirmed slot to send confirmation for"
            
            email_body = f"""
Dear Candidate,

Great! I'm confirming your interview for:

Date: {confirmed_slot['intersection_start']}
Duration: {confirmed_slot['duration']} minutes

The interview will be conducted virtually. You will receive a calendar invitation shortly.

Please let me know if you need to reschedule.

Best regards,
Recruiter
"""
            
            result = self.backend_client.send_email(
                to=self.session_state["candidate_email"],
                subject="Interview Confirmed",
                body=email_body
            )
            
            self.session_state["conversation_history"].append({
                "type": "email_sent",
                "content": email_body,
                "timestamp": "now"
            })
            
            return "Confirmation email sent to candidate"
        except Exception as e:
            return f"Error sending confirmation email: {str(e)}"
    
    def _create_calendar_event_tool(self, event_details: str = "") -> str:
        """Tool to create calendar event for confirmed slot"""
        try:
            confirmed_slot = self.session_state["confirmed_slot"]
            if not confirmed_slot:
                return "No confirmed slot to create calendar event"
            
            start_time = confirmed_slot["intersection_start"]
            end_time = confirmed_slot["intersection_end"]
            subject = "Interview with Candidate"
            
            result = self.backend_client.create_calendar_event(start_time, end_time, subject)
            
            self.session_state["conversation_history"].append({
                "type": "calendar_event_created",
                "details": result,
                "timestamp": "now"
            })
            
            return "Calendar event created successfully"
        except Exception as e:
            return f"Error creating calendar event: {str(e)}"
    
    def _send_follow_up_email_tool(self, context: str = "") -> str:
        """Tool to send follow-up email for alternative times"""
        try:
            # Fetch fresh slots again for follow-up suggestion
            fetched = self._refresh_recruiter_slots_from_backend(duration_minutes=60)
            slots = fetched if fetched else self.slot_manager.get_available_slots()
            slot_text = self._format_slots_for_email(slots[:5])
            
            email_body = f"""
Dear Candidate,

Thank you for your response. Unfortunately, the proposed times don't match our current availability.

Here are some additional available time slots:

{slot_text}

Please let me know if any of these work, or feel free to suggest other times.

Best regards,
Recruiter
"""
            
            result = self.backend_client.send_email(
                to=self.session_state["candidate_email"],
                subject="Interview Scheduling - Alternative Slots",
                body=email_body
            )
            
            self.session_state["conversation_history"].append({
                "type": "email_sent",
                "content": email_body,
                "timestamp": "now"
            })
            
            return "Follow-up email sent with alternative slots"
        except Exception as e:
            return f"Error sending follow-up email: {str(e)}"
    
    def _get_session_status_tool(self) -> str:
        """Tool to get current session status"""
        try:
            status = {
                "stage": self.session_state["current_stage"],
                "recruiter": self.session_state["recruiter_email"],
                "candidate": self.session_state["candidate_email"],
                "proposed_slots": self.session_state["proposed_slots"],
                "confirmed_slot": self.session_state["confirmed_slot"],
            }
            return json.dumps(status)
        except Exception as e:
            return f"Error getting status: {str(e)}"
    
    def _format_slots_for_email(self, slots: List[Dict]) -> str:
        """Format slots for email display"""
        if not slots:
            return "No available slots"
        
        formatted_slots = []
        for slot in slots:
            start_dt = slot["start"]
            formatted_slots.append(f"- {start_dt}")
        
        return "\n".join(formatted_slots)
    
    def run_scheduling_workflow(self, recruiter_email: str, candidate_email: str) -> str:
        """Run the complete scheduling workflow"""
        try:
            # Start the workflow
            result = self.agent.run(
                f"Start interview scheduling session with recruiter {recruiter_email} and candidate {candidate_email}. "
                "Follow this workflow: 1) Start session, 2) Send initial email with available slots, "
                "3) Wait for candidate response, 4) Parse response and find slot intersection, "
                "5) If intersection found, send confirmation and create calendar event, "
                "6) If no intersection, send follow-up email asking for alternative times."
            )
            
            return result
        except Exception as e:
            return f"Error running scheduling workflow: {str(e)}"
    
    def get_session_state(self) -> Dict:
        """Get current session state"""
        return self.session_state.copy() 