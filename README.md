python client.py src/blender_mcp/server.py
# Blender MCP Client

A client implementation for interacting with the Blender MCP server using the Model Context Protocol (MCP).

## Features

- Connect to Blender MCP server
- Interactive chat interface with Google's Gemini AI
- Support for all Blender MCP tools including:
  - Scene information retrieval
  - Object manipulation
  - PolyHaven asset integration
  - Hyper3D model generation

## Requirements

- Python 3.8 or higher
- Google Gemini API key
- Blender MCP server running

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_key_here
   ```

## Usage

Run the client by providing the path to your Blender MCP server script:

```bash
python client.py path/to/server.py
```

Available commands in the interactive chat:
- `scene`: Get current scene information
- `object <name>`: Get information about a specific object
- `polyhaven status`: Check PolyHaven integration status
- `hyper3d status`: Check Hyper3D integration status
- `quit`: Exit the client

## Example Queries

1. Get scene information:
   ```
   Query: What objects are in the current scene?
   ```

2. Check object details:
   ```
   Query: Tell me about the object named "Cube"
   ```

3. Use PolyHaven:
   ```
   Query: Can you add a wooden table from PolyHaven?
   ```

4. Generate with Hyper3D:
   ```
   Query: Generate a 3D model of a coffee cup using Hyper3D
   ```
