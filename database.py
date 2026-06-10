import sqlite3
import json
import os

DB_PATH = "pm_agent.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

#creates tables for charters and stories if they dont exist

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY ,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

        CREATE TABLE IF NOT EXISTS charter_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            version INTEGER,
            date TEXT,
            content TEXT,
            brd_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );   

        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );                                          
    """)

    conn.commit()
    conn.close()

"""Return the latest version number for a project (0 if none)."""

def get_latest_version(project_id:str) -> int:
    conn = get_connection()
    row = conn.execute("SELECT MAX(version) as v FROM charter_versions WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()
    return row["v"] if row["v"] else 0

"""Save a new version of the project charter to the database."""
def save_charter(project_id:str, version:int, content:str,brd_content:str):
    conn = get_connection()
    conn.execute("INSERT INTO projects (id)  VALUES (?) ON CONFLICT (id) DO NOTHING",(project_id,))
    conn.execute("INSERT INTO charter_versions (project_id, version, content,brd_content) VALUES (?, ?, ?, ?)"
    ,(project_id, version, content,brd_content))
    conn.commit()
    conn.close()

"""Return the latest charter text for a project."""
def get_latest_charter(project_id:str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT content FROM charter_versions WHERE project_id = ? ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()
    conn.close()
    return row["content"] if row else None

"""Save generated stories as JSON."""
def save_stories(project_id:str, data:dict):
    conn = get_connection()
    conn.execute("INSERT INTO stories (project_id, data_json) VALUES (?, ?)", (project_id, json.dumps(data)))
    conn.commit()
    conn.close()

"""Return the latest stories for a project."""
def get_stories(project_id:str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT data_json FROM stories WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
    conn.close()
    return json.loads(row["data_json"]) if row else None
