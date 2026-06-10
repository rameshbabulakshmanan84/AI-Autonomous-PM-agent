import uuid
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from db.database import init_db
from agent.agent import run_agent

load_dotenv()

init_db()

app = FastAPI()

#In memory session stoare
sessions={}

app.mount("/static",StaticFiles(directory="ui"),name="static")

class ChatRequest(BaseModel):
    session_id:str
    message:str

class NewSession(BaseModel):
    session_id:str
    project_id:str

@app.get("/")

def index():
    return FileResponse("ui/chat.html")

@app.post("/session/new")

def new_session():
    session_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    sessions[session_id] = {
        "project_id": project_id,
        "history":[]
    }
    return {"session_id":session_id, "project_id":project_id[:8]}

@app.post("/chat")

def chat(req: ChatRequest):
    if req.session_id not in sessions:
        return {"error":"Session not found. Please refresh"}
    print(f"[chat] received: {req.message[:50]}")  # add this

    session = sessions[req.session_id]
    project_id= session["project_id"]
    history = session["history"]

    message = f"[project_id: {project_id}] {req.message}"
    reply,updated_history = run_agent(history,message)

    sessions[req.session_id]["history"] = updated_history
    reply, updated_history = run_agent(history, message)
    print(f"[reply type]: {type(reply)}")
    print(f"[reply value]: {reply}")
    return {"reply": reply}

    return {"reply":reply}