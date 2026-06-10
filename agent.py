import json
import time
import os
from dotenv import load_dotenv
from openai import AzureOpenAI, RateLimitError
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DEFINITIONS, run_tool

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview"
)

def run_agent(conversation_history: list, user_message: str) -> tuple[str, list]:
    conversation_history.append({"role": "user", "content": user_message})

    while True:
        try:
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                max_tokens=1000,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[-6:],
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
        except RateLimitError:
            print("[rate limit] waiting 30 seconds...")
            time.sleep(30)
            continue  # retry

        message = response.choices[0].message

        if message.tool_calls is not None and len(message.tool_calls) > 0:
            # Add assistant tool call to history
            conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # Run each tool and add result to history
            for tc in message.tool_calls:
                tool_name  = tc.function.name
                tool_input = json.loads(tc.function.arguments)
                print(f"  [tool] calling {tool_name}...")
                result = run_tool(tool_name, tool_input)
                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            # Loop back — let GPT respond after seeing tool results

        else:
            # No tool calls — this is the final reply to the user
            reply = message.content or ""
            conversation_history.append({
                "role": "assistant",
                "content": reply,
            })
            return reply, conversation_history
    