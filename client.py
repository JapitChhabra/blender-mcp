import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()  # load environment variables from .env

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Google AI client
genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant that controls Blender through an MCP server.
You have access to several tools to interact with Blender. When you need to perform an action in Blender,
you should respond with a tool call in this exact format:

{
    "tool_call": {
        "name": "tool_name",
        "args": {
            "arg1": "value1",
            "arg2": "value2"
        }
    }
}

For example, to create a sphere, you would respond with:
{
    "tool_call": {
        "name": "execute_blender_code",
        "args": {
            "code": "import bpy\\nbpy.ops.mesh.primitive_uv_sphere_add()"
        }
    }
}

Only use the tools that are available to you. Always respond with proper JSON for tool calls.
After using a tool, provide a natural language response explaining what you did."""

class StreamPrinter:
    def __init__(self):
        self.buffer = ""
    
    def write(self, text):
        print(text, end="", flush=True)
        self.buffer += text
    
    def get_buffer(self):
        return self.buffer

class BlenderMCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.available_tools = []
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.stream_handler = StreamPrinter()  # Default stream handler

    def set_stream_handler(self, handler):
        """Set a custom stream handler"""
        self.stream_handler = handler

    async def call_gemini_stream(self, query, tools=None):
        """Call the Gemini API with streaming response"""
        # Format the prompt with system prompt, tools, and query
        prompt = f"{SYSTEM_PROMPT}\n\n"
        if tools:
            prompt += "Available tools:\n"
            for tool in tools:
                prompt += f"\n{json.dumps(tool, indent=2)}\n"
        
        prompt += f"\nUser query: {query}"

        # Get streaming response
        response = self.model.generate_content(
            prompt,
            stream=True
        )

        # Collect the complete response
        full_response = ""
        self.stream_handler.write("\nGemini: ")
        for chunk in response:
            if chunk.text:
                self.stream_handler.write(chunk.text)
                full_response += chunk.text
        self.stream_handler.write("\n")

        # Try to extract tool call from the response
        try:
            # Look for JSON object in the response
            start_idx = full_response.find("{")
            end_idx = full_response.rfind("}") + 1
            if start_idx != -1 and end_idx != -1:
                json_str = full_response[start_idx:end_idx]
                tool_data = json.loads(json_str)
                
                if "tool_call" in tool_data:
                    tool_call = tool_data["tool_call"]
                    return {
                        "type": "tool_use",
                        "name": tool_call["name"],
                        "input": tool_call["args"]
                    }
        except json.JSONDecodeError:
            pass
        except KeyError:
            pass
        
        # If no valid tool call found, return as text
        return {
            "type": "text",
            "text": full_response
        }

    async def connect_to_server(self, server_script_path: str):
        """Connect to the Blender MCP server

        Args:
            server_script_path: Path to the server script (.py)
        """
        if not server_script_path.endswith('.py'):
            raise ValueError("Server script must be a .py file")

        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        self.available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        print("\nConnected to Blender MCP server with tools:", [tool["name"] for tool in self.available_tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        while True:
            response = await self.call_gemini_stream(query, self.available_tools)
            
            if response["type"] == "text":
                break
            elif response["type"] == "tool_use":
                tool_name = response["name"]
                tool_args = response["input"]

                # Execute tool call
                try:
                    self.stream_handler.write(f"\n[Executing tool {tool_name}...]\n")
                    result = await self.session.call_tool(tool_name, tool_args)
                    self.stream_handler.write(f"[Tool {tool_name} executed successfully]\n")
                    
                    # Update query to get final response after tool execution
                    query = f"Tool {tool_name} executed with result: {result.content}. Please provide a natural language response."
                except Exception as e:
                    self.stream_handler.write(f"\n[Error executing tool {tool_name}: {str(e)}]\n")
                    break

        return ""  # Return empty string since we're printing responses directly

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = BlenderMCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                await client.process_query(query)

            except Exception as e:
                print(f"\nError: {str(e)}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 