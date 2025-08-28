# AI-Driven Interview Scheduler

An intelligent interview scheduling system that uses AI to automatically coordinate between recruiters and candidates, handling email communication, slot availability, and calendar integration.

## 🎯 Project Overview

This project demonstrates **agentic AI capabilities** by building an autonomous interview scheduling system that:

- **Parses candidate email responses** using LLM to extract proposed interview slots
- **Manages recruiter availability** and finds slot intersections
- **Automatically sends emails** and creates calendar events
- **Orchestrates the entire scheduling workflow** without manual intervention

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   AI Engine     │    │   Backend       │
│   (React)       │◄──►│   (LangGraph)   │◄──►│   (Node.js)     │
│                 │    │                 │    │                 │
│ - Start/Reset   │    │ - Email Parsing │    │ - Email Sending │
│ - Status Check  │    │ - Slot Logic    │    │ - Calendar API  │
│                 │    │ - Workflow      │    │ - Session Mgmt  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd scheduling-ai-agent/engine
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your Google Gemini API key and other settings
   ```

4. **Install Node.js dependencies** (for backend)
   ```bash
   cd ../backend  # Create this directory for your Node.js backend
   npm install express nodemailer axios body-parser
   ```

### Configuration

Create a `.env` file with the following variables:

```env
# Google Gemini API Configuration
GOOGLE_API_KEY=your_google_api_key_here

# Backend API Configuration
BACKEND_URL=http://localhost:3009

# Recruiter Configuration
RECRUITER_EMAIL=recruiter@company.com
RECRUITER_NAME=John Doe

# Timezone Configuration
TIMEZONE=UTC
```

## 🧠 AI Engine Components

### 1. **Slot Manager** (`ai_engine/slot_manager.py`)
- Manages recruiter availability (Mon-Fri, 9 AM - 5 PM)
- Generates available interview slots
- Finds intersections between candidate and recruiter availability

### 2. **Email Parser** (`ai_engine/email_parser.py`)
- Uses Gemini to parse candidate email responses
- Extracts proposed interview slots from natural language
- Handles multiple slot suggestions and relative times

### 3. **Backend Client** (`ai_engine/backend_client.py`)
- Communicates with Node.js backend API
- Handles email sending, calendar events, and session management

### 4. **Scheduler Agent** (`ai_engine/scheduler_agent.py`)
- Main orchestrator using LangChain
- Manages the complete scheduling workflow
- Integrates all components with custom tools

## 📋 Usage

### Running the AI Engine

```bash
# From the engine directory
python main.py

# Run step-by-step demo
python main.py --demo
```

### Manual Workflow Demo

The `--demo` flag runs a step-by-step demonstration:

1. **Start Session** - Initialize with recruiter and candidate emails
2. **Send Initial Email** - Send available slots to candidate
3. **Parse Response** - Extract candidate's proposed times
4. **Find Intersection** - Match candidate slots with recruiter availability
5. **Confirm & Book** - Send confirmation and create calendar event

### Example Output

```
=== Manual Workflow Demo ===

1. Starting session...
Session started successfully. Recruiter: recruiter@company.com, Candidate: candidate@example.com

2. Sending initial email...
Initial email sent to candidate@example.com with available slots

3. Parsing candidate response...
Parsed candidate response. Intent: proposed_slots, Proposed slots: ['2024-01-15T14:00:00Z', '2024-01-16T15:00:00Z', '2024-01-17T10:00:00Z']

4. Finding slot intersection...
Found matching slot: 2024-01-15T14:00:00Z - 2024-01-15T15:00:00Z

5. Sending confirmation...
Confirmation email sent for slot: 2024-01-15T14:00:00Z

6. Creating calendar event...
Calendar event created successfully. Event ID: abc123

=== Final Session State ===
Stage: calendar_event_created
Confirmed Slot: {'intersection_start': '2024-01-15T14:00:00Z', ...}
```

## 🔧 Backend Integration

The AI engine expects a Node.js backend with these endpoints:

- `POST /start` - Start scheduling session
- `POST /reset` - Reset session
- `GET /status` - Get session status
- `POST /sendEmail` - Send email
- `POST /receiveEmail` - Simulate receiving email
- `POST /createEvent` - Create calendar event

## 🎯 Key Features

### **Intelligent Email Parsing**
- Extracts interview slots from natural language
- Handles multiple time suggestions
- Processes relative times ("tomorrow", "next week")

### **Smart Slot Management**
- Generates recruiter availability automatically
- Finds optimal intersections between schedules
- Handles timezone considerations

### **Autonomous Workflow**
- Complete end-to-end scheduling without manual intervention
- Automatic email responses and calendar booking
- Intelligent decision-making for follow-ups

### **Demo-Ready**
- Simulated email responses for testing
- Step-by-step workflow demonstration
- Comprehensive logging and status tracking

## 🛠️ Development

### Project Structure

```
scheduling-ai-agent/engine/
├── ai_engine/
│   ├── __init__.py
│   ├── slot_manager.py      # Slot availability and intersection logic
│   ├── email_parser.py      # LLM-based email parsing
│   ├── backend_client.py    # Backend API communication
│   └── scheduler_agent.py   # Main LangChain agent
├── main.py                  # Entry point and demo
├── requirements.txt         # Python dependencies
├── env.example             # Environment variables template
└── README.md               # This file
```

### Adding New Features

1. **New Tools**: Add to `scheduler_agent.py` tools list
2. **Email Templates**: Modify email generation in agent methods
3. **Slot Logic**: Extend `slot_manager.py` for complex availability
4. **Parsing**: Enhance `email_parser.py` for new response types

## 🚨 Important Notes

- **Demo Mode**: Uses simulated email responses for testing
- **Availability**: Hardcoded recruiter availability (Mon-Fri, 9-5)
- **Timezone**: Uses UTC for demo (configurable)
- **Backend**: Requires separate Node.js backend implementation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is for demonstration purposes. Please ensure compliance with Google AI Studio terms and other service agreements.

---

**Built for Hackathon MVP** - Focuses on demonstrating agentic AI capabilities with real-world integrations. 