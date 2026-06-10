import json
import uuid
import os
from datetime import datetime
from datetime import date
from openai import OpenAI
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

#client = OpenAI(api_key=os.getenv("Open_API_KEY"))
client = AzureOpenAI(
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview"
)


#Tool definitions passed to the OpenAI API
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name":"read_brd",
            "description":"Extract and structure content from BRD that the user has posted or uploaded",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_text": {
                        "type": "string",
                        "description": "The raw BRD text to extract content from ",
                    },
                },
                "required": ["raw_text"],
            },
    }
},
{
    "type": "function",
    "function": {
        "name":"generate_charter",
        "description":"Generate a project charter based on the provided BRD content",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": { "type": "string", "description": "A unique identifier for the project" },
                "brd_content": {"type": "string", "description": "The structured content extracted from the BRD" },
                "feedback": {"type": "string", "description": "Reviewer feedback for regeneration (empty for first version)" },
            },
            "required": ["project_id", "brd_content"],
        },
    }
},

    {
    "type": "function",
    "function": {
        "name":"generate_stories",
        "description":"Generate user stories based on the finalized project charter",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": { "type": "string"},
            }, 
            "required": ["project_id"]
        },
    }
},
 
]

# ── Tool implementations ─────────────────────────────────────────────────────

def read_brd(raw_text:str) -> dict:
    print(f"Read_brd is accessed")
    "clean & return the BRD Text"
    return{
        "success": True,
        "content": raw_text.strip(),
        "length": len(raw_text.split()),
    }

def generate_charter(project_id:str, brd_content:str, feedback:str="") -> dict:
    print(f"generate_charter is accessed")
    "Call GPT to generate a project charter based on the BRD content and optional feedback"
    from db.database import save_charter,get_latest_version
    from agent.prompts import CHARTER_PROMPT

    current_version = get_latest_version(project_id)
    new_version = current_version + 1 

    feedback_section = ""
    if feedback:
        feedback_section = f"Reviewer Feedback:\n{feedback}\n\n"
    
    prompt = CHARTER_PROMPT.format(
        version=new_version,
        date=date.today().strftime("%B %d, %Y"),
        brd_content=brd_content,
        feedback_section=feedback_section
    )

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        max_tokens=1500,
        messages=[{"role": "system", "content": prompt}],
    )

    charter_text= response.choices[0].message.content
    print ("charter_text:" ,charter_text)
    save_charter(project_id, new_version, charter_text,brd_content)

    return {
        "success": True,
        "project_id": project_id,
        "version": new_version,
        "charter": charter_text,
    }

def generate_stories(project_id:str) -> dict:
    "Call GPT to generate user stories based on the finalized project charter"
    print(f"generate_Stories is accessed")
    from db.database import get_latest_charter,save_stories
    from agent.prompts import STORIES_PROMPT
    charter = get_latest_charter(project_id)
    if not charter:
        return {
            "success": False,
            "error": "No charter found for this project. Please generate a charter first.",
        }
    prompt = STORIES_PROMPT.format(charter_content=charter)

    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        max_tokens=2000,
        messages=[{"role": "system", "content": prompt}],
    )

    raw= response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
 
    stories_data = json.loads(raw)
    save_stories(project_id, stories_data)
 
    epic_count  = len(stories_data["epics"])
    story_count = sum(len(e["stories"]) for e in stories_data["epics"])
 
    return {
        "success": True,
        "project_id": project_id,
        "epic_count": epic_count,
        "story_count": story_count,
        "data": stories_data
    }
 
  
  
def push_to_trello(project_id:str) -> dict:
    "Push user stories to Trello board"
    from db.database import get_stories
    from integrations.trello import create_trello_board,create_list,create_card

    stories_data = get_stories(project_id)
    if not stories_data:
        return {
            "success": False,
            "error": "No user stories found for this project. Please generate user stories first.",
        }
    
    board = create_trello_board(f"Project {project_id[:8]} ")
    board_id= board["id"]
    board_url = board["url"]

    
    for epic in stories_data["epics"]:
        trello_list = create_list(board_id, epic["name"])
        list_id= trello_list["id"]
        for story in epic["stories"]:
            desc  = story["title"] + "\n\nAcceptance Criteria:\n"
            desc += "\n".join(f"- {ac}" for ac in story["acceptance_criteria"])
            desc += f"\n\nPriority: {story['priority']} | Estimate: {story['estimate']}"
            create_card(list_id, story["title"], desc)
 
    return {
        "success": True,
        "project_id": project_id,
        "board_url": board_url,
        "message": "User stories pushed to Trello successfully.",
    }                            

#--Tool router ────────────────────────────────────────────────────────────────

def run_tool(tool_name:str, tool_input:dict) -> str:
    "Route to the correct tool implementation based on the tool name"
    tool_map={
        "read_brd": read_brd,
        "generate_charter": generate_charter,
        "generate_stories": generate_stories,
        #"push_to_trello": push_to_trello
        }
    
    if tool_name not in tool_map:
        return f"Error: Tool {tool_name} not found"
    
    try:
        result = tool_map[tool_name](**tool_input)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        }) 
