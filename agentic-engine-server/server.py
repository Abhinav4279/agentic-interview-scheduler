import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from ai_engine.scheduler_agent import SchedulerAgent

load_dotenv()

app = FastAPI()

# Initialize agent once
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3009")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

agent = SchedulerAgent(google_api_key=GOOGLE_API_KEY, backend_url=BACKEND_URL)

class KickoffPayload(BaseModel):
    recruiterEmail: EmailStr
    candidateEmail: EmailStr

class IngestEmailPayload(BaseModel):
    from_: EmailStr | None = None
    subject: str
    body: str
    sessionId: str | None = None

@app.post("/kickoff")
def kickoff(payload: KickoffPayload):
    try:
        print(f"[ENGINE /kickoff] recruiter={payload.recruiterEmail} candidate={payload.candidateEmail}")
        agent.session_state["recruiter_email"] = payload.recruiterEmail
        agent.session_state["candidate_email"] = payload.candidateEmail
        agent.session_state["current_stage"] = "session_started"
        print("[ENGINE /kickoff] session initialized locally")
        result2 = agent._send_initial_email_tool()
        print(f"[ENGINE /kickoff] send_initial_email_tool -> {result2}")
        return {"status": "kickoff_started"}
    except Exception as e:
        print(f"[ENGINE /kickoff] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingestEmail")
def ingest_email(payload: IngestEmailPayload):
    try:
        print(f"[ENGINE /ingestEmail] subject={payload.subject} from={payload.from_} body_len={len(payload.body) if payload.body else 0}")
        result_parse = agent._parse_candidate_response_tool(payload.body)
        print(f"[ENGINE /ingestEmail] parse_candidate_response_tool -> {result_parse}")
        result_intersect = agent._find_slot_intersection_tool()
        print(f"[ENGINE /ingestEmail] find_slot_intersection_tool -> {result_intersect}")
        if agent.session_state.get("confirmed_slot"):
            conf_res = agent._send_confirmation_email_tool()
            cal_res = agent._create_calendar_event_tool()
            print(f"[ENGINE /ingestEmail] confirmation -> {conf_res}")
            print(f"[ENGINE /ingestEmail] calendar -> {cal_res}")
            return {"status": "confirmed", "details": result_intersect}
        else:
            follow_res = agent._send_follow_up_email_tool()
            print(f"[ENGINE /ingestEmail] follow_up -> {follow_res}")
            return {"status": "no_intersection", "details": result_intersect}
    except Exception as e:
        print(f"[ENGINE /ingestEmail] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def status():
    print(f"[ENGINE /status] stage={agent.session_state.get('current_stage')} candidate={agent.session_state.get('candidate_email')}")
    return agent.get_session_state() 