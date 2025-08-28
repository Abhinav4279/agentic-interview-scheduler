#!/usr/bin/env python3
"""
Main entry point for the Interview Scheduler AI Engine
Demonstrates the complete scheduling workflow
"""

import os
import sys
from dotenv import load_dotenv
from ai_engine.scheduler_agent import SchedulerAgent

def main():
    """Main function to run the AI engine"""
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    google_api_key = os.getenv("GOOGLE_API_KEY")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:3009")
    
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found in environment variables")
        print("Please set your Google Gemini API key in the .env file")
        sys.exit(1)
    
    # Initialize the scheduler agent
    print("Initializing AI Scheduler Agent (Gemini)...")
    agent = SchedulerAgent(
        google_api_key=google_api_key,
        backend_url=backend_url
    )
    
    # If kickoff arguments are provided
    if len(sys.argv) > 1 and sys.argv[1] == "--kickoff":
        if len(sys.argv) < 4:
            print("Usage: python main.py --kickoff <recruiter_email> <candidate_email>")
            sys.exit(2)
        recruiter_email = sys.argv[2]
        candidate_email = sys.argv[3]
        # Kickoff: start session and send initial email
        print(f"Kickoff: starting session for {recruiter_email} -> {candidate_email}")
        agent.session_state["recruiter_email"] = recruiter_email
        agent.session_state["candidate_email"] = candidate_email
        agent.session_state["current_stage"] = "session_started"
        print("[ENGINE /kickoff] session initialized locally")
        print(agent._send_initial_email_tool())
        sys.exit(0)
    
    # Demo configuration
    recruiter_email = "recruiter@company.com"
    candidate_email = "candidate@example.com"
    
    print(f"\nStarting interview scheduling session...")
    print(f"Recruiter: {recruiter_email}")
    print(f"Candidate: {candidate_email}")
    print("-" * 50)
    
    try:
        # Run the complete scheduling workflow
        result = agent.run_scheduling_workflow(recruiter_email, candidate_email)
        
        print("\nWorkflow completed!")
        print("Result:", result)
        
        # Show final session state
        print("\nFinal Session State:")
        session_state = agent.get_session_state()
        print(f"Current Stage: {session_state['current_stage']}")
        print(f"Confirmed Slot: {session_state['confirmed_slot']}")
        
    except Exception as e:
        print(f"Error running workflow: {e}")
        sys.exit(1)

def demo_manual_workflow():
    """Demo the workflow step by step for testing"""
    
    # Load environment variables
    load_dotenv()
    
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found")
        return
    
    # Initialize agent
    agent = SchedulerAgent(google_api_key=google_api_key)
    
    print("=== Manual Workflow Demo ===")
    
    # Step 1: Start session
    print("\n1. Starting session...")
    result = agent._start_session_tool("recruiter@company.com", "candidate@example.com")
    print(result)
    
    # Step 2: Send initial email
    print("\n2. Sending initial email...")
    result = agent._send_initial_email_tool()
    print(result)
    
    # Step 3: Simulate candidate response
    print("\n3. Parsing candidate response...")
    candidate_response = """
    Hi, thank you for the interview opportunity!
    
    I'm available on Monday at 2 PM, Tuesday at 3 PM, or Wednesday at 10 AM.
    Any of these times would work well for me.
    
    Best regards,
    Candidate
    """
    result = agent._parse_candidate_response_tool(candidate_response)
    print(result)
    
    # Step 4: Find intersection
    print("\n4. Finding slot intersection...")
    result = agent._find_slot_intersection_tool()
    print(result)
    
    # Step 5: Send confirmation (if slot found)
    if agent.session_state["confirmed_slot"]:
        print("\n5. Sending confirmation...")
        result = agent._send_confirmation_email_tool()
        print(result)
        
        print("\n6. Creating calendar event...")
        result = agent._create_calendar_event_tool()
        print(result)
    else:
        print("\n5. No intersection found, sending follow-up...")
        result = agent._send_follow_up_email_tool()
        print(result)
    
    # Show final state
    print("\n=== Final Session State ===")
    session_state = agent.get_session_state()
    print(f"Stage: {session_state['current_stage']}")
    print(f"Confirmed Slot: {session_state['confirmed_slot']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_manual_workflow()
    else:
        main() 