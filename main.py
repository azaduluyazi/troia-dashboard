from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from collections import deque

app = FastAPI(title="Troia Media Dashboard", version="2.0.0")

# In-memory event log (last 100 events)
event_log: deque = deque(maxlen=100)

# Pipeline status tracking
pipeline_status: Dict = {
    "current_stage": "idle",
    "current_video": None,
    "progress": 0,
    "last_completed": None,
    "stats": {
        "videos_today": 0,
        "videos_this_week": 0,
        "total_videos": 0
    }
}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys from Environment Variables
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://troia.app.n8n.cloud")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COOLIFY_API_TOKEN = os.getenv("COOLIFY_API_TOKEN", "")
COOLIFY_BASE_URL = os.getenv("COOLIFY_BASE_URL", "https://coolify.troiamedia.cloud")
VIDEO_API_URL = os.getenv("VIDEO_API_URL", "")
WORKFLOW_ID = os.getenv("WORKFLOW_ID", "Y9b62VBTOzErXVnb")

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/workflow/status")
async def get_workflow_status():
    """Get n8n workflow status"""
    if not N8N_API_KEY:
        return {"error": "N8N_API_KEY not configured", "active": False}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{N8N_BASE_URL}/api/v1/workflows/{WORKFLOW_ID}",
                headers={"X-N8N-API-KEY": N8N_API_KEY}
            )
            data = response.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "active": data.get("active"),
                "updatedAt": data.get("updatedAt"),
                "triggerCount": data.get("triggerCount", 0)
            }
    except Exception as e:
        return {"error": str(e), "active": False}

@app.get("/api/workflow/executions")
async def get_workflow_executions():
    """Get recent workflow executions"""
    if not N8N_API_KEY:
        return {"error": "N8N_API_KEY not configured", "executions": []}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{N8N_BASE_URL}/api/v1/executions",
                headers={"X-N8N-API-KEY": N8N_API_KEY},
                params={"workflowId": WORKFLOW_ID, "limit": 10}
            )
            data = response.json()
            executions = []
            for exe in data.get("data", []):
                executions.append({
                    "id": exe.get("id"),
                    "status": exe.get("status"),
                    "startedAt": exe.get("startedAt"),
                    "stoppedAt": exe.get("stoppedAt"),
                    "mode": exe.get("mode")
                })
            return {"executions": executions}
    except Exception as e:
        return {"error": str(e), "executions": []}

@app.get("/api/credits/elevenlabs")
async def get_elevenlabs_credits():
    """Get ElevenLabs API credits"""
    if not ELEVENLABS_API_KEY:
        return {"error": "ELEVENLABS_API_KEY not configured"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.elevenlabs.io/v1/user/subscription",
                headers={"xi-api-key": ELEVENLABS_API_KEY}
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "character_count": data.get("character_count", 0),
                    "character_limit": data.get("character_limit", 10000),
                    "tier": data.get("tier", "free"),
                    "usage_percentage": round((data.get("character_count", 0) / max(data.get("character_limit", 1), 1)) * 100, 1)
                }
            else:
                return {"error": "API key may have limited permissions", "character_count": "N/A", "character_limit": "N/A", "usage_percentage": 0}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/credits/openai")
async def get_openai_credits():
    """Get OpenAI API usage"""
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not configured", "status": "not_configured"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
            )
            if response.status_code == 200:
                return {
                    "status": "active",
                    "note": "OpenAI does not provide real-time credit balance via API",
                    "check_at": "https://platform.openai.com/usage"
                }
            else:
                return {"status": "error", "message": "API key invalid"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/services/video-api")
async def get_video_api_status():
    """Check Video API status on Coolify"""
    video_url = VIDEO_API_URL or "https://u4w84gss8s0c40gso8c0o4g8.troiamedia.cloud"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{video_url}/health",
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "healthy", "data": response.json()}
            else:
                return {"status": "unhealthy", "code": response.status_code}
    except Exception as e:
        return {"status": "offline", "error": str(e)}

@app.get("/api/services/coolify")
async def get_coolify_status():
    """Get Coolify applications status"""
    if not COOLIFY_API_TOKEN:
        return {"error": "COOLIFY_API_TOKEN not configured"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COOLIFY_BASE_URL}/api/v1/applications",
                headers={"Authorization": f"Bearer {COOLIFY_API_TOKEN}"}
            )
            if response.status_code == 200:
                apps = response.json()
                return {
                    "total_apps": len(apps),
                    "applications": [
                        {
                            "name": app.get("name"),
                            "status": app.get("status"),
                            "fqdn": app.get("fqdn")
                        } for app in apps
                    ]
                }
            else:
                return {"error": "Failed to fetch", "code": response.status_code}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/youtube/channel")
async def get_youtube_channel_info():
    """Placeholder for YouTube channel info - requires OAuth"""
    return {
        "note": "YouTube Analytics requires OAuth authentication",
        "channels": [
            {"name": "Global Atlas HQ", "status": "pending_auth"},
            {"name": "Capital Research HQ", "status": "pending_auth"}
        ],
        "setup_url": "https://troia.app.n8n.cloud"
    }

# ==================== AUTONOMOUS AGENT ENDPOINTS ====================

@app.post("/api/events/log")
async def log_event(request: Request):
    """Log an event from n8n workflow or Claude Agent"""
    try:
        data = await request.json()
        event = {
            "id": len(event_log) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "type": data.get("type", "info"),  # info, success, warning, error, decision
            "source": data.get("source", "system"),  # n8n, claude, video-api, youtube
            "message": data.get("message", ""),
            "details": data.get("details", {})
        }
        event_log.appendleft(event)
        return {"status": "logged", "event_id": event["id"]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/events")
async def get_events(limit: int = 50):
    """Get recent events"""
    events = list(event_log)[:limit]
    return {"events": events, "total": len(event_log)}

@app.post("/api/pipeline/update")
async def update_pipeline(request: Request):
    """Update pipeline status from n8n workflow"""
    global pipeline_status
    try:
        data = await request.json()
        pipeline_status.update({
            "current_stage": data.get("stage", pipeline_status["current_stage"]),
            "current_video": data.get("video", pipeline_status["current_video"]),
            "progress": data.get("progress", pipeline_status["progress"]),
            "last_updated": datetime.utcnow().isoformat()
        })

        if data.get("completed"):
            pipeline_status["last_completed"] = {
                "title": data.get("video", {}).get("title"),
                "timestamp": datetime.utcnow().isoformat()
            }
            pipeline_status["stats"]["videos_today"] += 1
            pipeline_status["stats"]["total_videos"] += 1

        return {"status": "updated"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline status"""
    return pipeline_status

@app.get("/api/content/calendar")
async def get_content_calendar():
    """Get content calendar from Google Sheets"""
    # This will be called by the frontend to show upcoming content
    try:
        # For now, return placeholder - will integrate with Google Sheets API
        async with httpx.AsyncClient() as client:
            # Try to get from n8n or direct sheets API
            return {
                "upcoming": [
                    {"date": "Today", "title": "Pending...", "status": "scheduled"},
                ],
                "note": "Connect Google Sheets for full calendar"
            }
    except Exception as e:
        return {"error": str(e), "upcoming": []}

@app.post("/api/agent/decision")
async def log_agent_decision(request: Request):
    """Log autonomous agent decisions"""
    try:
        data = await request.json()
        decision = {
            "id": len(event_log) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "decision",
            "source": "claude",
            "message": f"AUTONOMOUS: {data.get('action', 'Unknown action')}",
            "details": {
                "reason": data.get("reason", ""),
                "confidence": data.get("confidence", "high"),
                "result": data.get("result", "pending")
            }
        }
        event_log.appendleft(decision)
        return {"status": "logged", "decision_id": decision["id"]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/agent/status")
async def get_agent_status():
    """Get Claude Agent status"""
    return {
        "mode": "autonomous",
        "status": "active",
        "last_action": event_log[0] if event_log else None,
        "decisions_today": sum(1 for e in event_log if e.get("type") == "decision"),
        "capabilities": [
            "content_scheduling",
            "video_generation",
            "youtube_upload",
            "error_handling",
            "performance_optimization"
        ]
    }

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
