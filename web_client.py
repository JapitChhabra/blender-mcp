from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import sys
from client import BlenderMCPClient
import threading
from queue import Queue
import nest_asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Global client instance and event loop
blender_client = None
loop = None
executor = ThreadPoolExecutor(max_workers=1)

def format_tool_list(tools):
    """Format tools list for display"""
    return [f"- {tool['name']}: {tool['description']}" for tool in tools]

class WebStreamHandler:
    """Handler for streaming responses to the frontend"""
    def __init__(self):
        self.buffer = ""
    
    def write(self, text):
        # Emit the message to all connected clients
        socketio.emit('message', {'data': text})
        self.buffer += text
        
    def get_buffer(self):
        return self.buffer

@app.route('/')
def home():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    if blender_client and blender_client.available_tools:
        emit('tools_list', {'tools': format_tool_list(blender_client.available_tools)})

def async_query(message):
    """Run the query in a separate thread"""
    async def run():
        try:
            # Create a new stream handler for this query
            stream_handler = WebStreamHandler()
            # Set the stream handler on the client
            blender_client.set_stream_handler(stream_handler)
            # Process the query
            await blender_client.process_query(message)
        except Exception as e:
            socketio.emit('message', {'data': f'Error: {str(e)}'})
    
    future = asyncio.run_coroutine_threadsafe(run(), loop)
    try:
        future.result(timeout=60)  # 60 second timeout
    except Exception as e:
        socketio.emit('message', {'data': f'Error: {str(e)}'})

@socketio.on('send_message')
def handle_message(message):
    if not blender_client:
        emit('message', {'data': 'Error: Blender client not connected'})
        return

    # Send the user's message to the frontend first
    socketio.emit('message', {'data': message['data'], 'type': 'user'})
    
    # Run the query in a separate thread
    executor.submit(async_query, message['data'])

def start_background_loop(loop):
    """Start the event loop in the background"""
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run_flask(server_script_path):
    global blender_client, loop

    # Create a new event loop
    loop = asyncio.new_event_loop()
    
    # Start the event loop in a background thread
    thread = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
    thread.start()

    # Initialize the client in the main event loop
    async def initialize_client():
        global blender_client
        blender_client = BlenderMCPClient()
        # Set initial stream handler
        blender_client.set_stream_handler(WebStreamHandler())
        await blender_client.connect_to_server(server_script_path)
        return "Connected to Blender MCP server"

    # Initialize the client
    future = asyncio.run_coroutine_threadsafe(initialize_client(), loop)
    try:
        status = future.result(timeout=10)  # 10 second timeout
        print(status)
    except Exception as e:
        print(f"Error initializing client: {e}")
        sys.exit(1)

    # Start the Flask app with eventlet
    socketio.run(app, debug=True, port=5000, use_reloader=False)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python web_client.py <path_to_server_script>")
        sys.exit(1)

    run_flask(sys.argv[1]) 