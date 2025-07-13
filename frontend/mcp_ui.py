import streamlit as st
import os
import json
from dotenv import load_dotenv
import httpx
from openai import OpenAI
import uuid

# Load secrets
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8000/mcp/")

client = OpenAI(api_key=OPENAI_API_KEY)

# Define tools (MCP functions)
tools = [
    {
        "type": "function",
        "function": {
            "name": "clone_and_test",
            "description": "Clones a repo and runs tests locally or on AWS",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "GitHub repo URL"
                    },
                    "run_on_aws": {
                        "type": "boolean",
                        "description": "If true, run on AWS instead of locally",
                        "default": False
                    }
                },
                "required": ["repo_url"]
            }
        }
    }
]

# Streamlit UI
st.set_page_config(page_title="MCP Prompt UI")
st.title("🧠 LLM-Powered MCP Prompt Runner")

user_prompt = st.text_input("💬 Prompt", placeholder="e.g., Run tests from https://github.com/your/repo")

if st.button("🚀 Run"):
    if not user_prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Thinking with GPT-4..."):
            try:
                # Step 1: Ask GPT to select function + args
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": "You're an assistant that helps users run tools via MCP server."
                        },
                        {"role": "user", "content": user_prompt}
                    ],
                    tools=tools,
                    tool_choice="auto"
                )

                tool_call = response.choices[0].message.tool_calls[0]
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                st.info(f"🛠 Calling `{tool_name}` with: `{args}`")

                # Step 2: Call MCP tool
                session_id = str(uuid.uuid4())  # can be any unique ID, e.g., a UUID

                tool_response = httpx.post(
                        MCP_URL,  # should be something like "http://localhost:8000/mcp/"
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                            "X-Session-ID": session_id
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": "1",
                            "method": tool_name,
                            "params": args
                        },
                        timeout=60
                )
                

                st.success("✅ Tool executed.")
                st.text_area("📄 Output", value=tool_response.text, height=400)

            except Exception as e:
                st.error(f"❌ Error: {e}")
