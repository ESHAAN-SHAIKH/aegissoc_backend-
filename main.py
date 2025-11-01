from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

app = FastAPI(title="AegisSOC Backend")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
MISTRAL_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    alert_context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    model: str

# Mock alert data for context
MOCK_ALERTS = [
    {
        "id": 1,
        "severity": "critical",
        "type": "Malware",
        "source": "192.168.1.50",
        "target": "DB-Server-01",
        "description": "Trojan.GenericKD detected on database server",
        "time": "2 min ago"
    },
    {
        "id": 2,
        "severity": "high",
        "type": "DDoS",
        "source": "203.45.67.89",
        "target": "Web-Server-03",
        "description": "Unusual traffic spike from external IP",
        "time": "5 min ago"
    },
    {
        "id": 4,
        "severity": "critical",
        "type": "Ransomware",
        "source": "10.0.5.23",
        "target": "File-Server-05",
        "description": "File encryption activity detected",
        "time": "18 min ago"
    }
]

def build_system_prompt():
    """Build SOC analyst system prompt with context"""
    alert_summary = "\n".join([
        f"- {a['severity'].upper()}: {a['type']} on {a['target']} - {a['description']}"
        for a in MOCK_ALERTS
    ])
    
    return f"""You are a SOC analyst AI. Be concise and actionable.

Active Alerts:
{alert_summary}

Format responses:
- Risk: [High/Medium/Low]
- Action: [1-2 specific steps]
- Impact: [Brief consequence]

Keep under 200 words unless asked for details."""
async def call_mistral_api(messages: List[dict]) -> str:
    """Call Together AI with Mistral model"""
    if not TOGETHER_API_KEY:
        raise HTTPException(status_code=500, detail="TOGETHER_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    api_messages = [
        {"role": "system", "content": build_system_prompt()}
    ] + messages
    
    payload = {
        "model": MISTRAL_MODEL,
        "messages": api_messages,
        "max_tokens": 512,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TOGETHER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # FIX: Extract content correctly
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                raise Exception("No response from API")
                
    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail=f"API call failed: {str(e)}")

@app.get("/")
async def root():
    return {
        "service": "AegisSOC Backend",
        "status": "online",
        "model": MISTRAL_MODEL
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "api_configured": bool(TOGETHER_API_KEY)
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint with Mistral AI"""
    try:
        print("Received request:", request.dict())  # DEBUG
        
        # Convert Pydantic models to dicts
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        print("Converted messages:", messages)  # DEBUG
        
        # Call Mistral
        response_text = await call_mistral_api(messages)
        
        return ChatResponse(
            response=response_text,
            model=MISTRAL_MODEL
        )
    except Exception as e:
        print("Chat endpoint error:", str(e))  # DEBUG
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts():
    """Get current alerts"""
    return {"alerts": MOCK_ALERTS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)