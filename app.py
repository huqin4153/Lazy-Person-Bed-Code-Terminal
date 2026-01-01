from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="static")
CORS(app)

# ===== Configuration =====
API_TOKEN = "<your api token>"
BASE_DIR = "./storage"
COMMAND_DIR = os.path.join(BASE_DIR, "command")
RESULT_DIR = os.path.join(BASE_DIR, "result")

# Ensure storage directories exist
os.makedirs(COMMAND_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# ===== Helpers =====
def get_target_dir(file_type):
    """Maps file types to their respective directory paths."""
    if file_type == "command":
        return COMMAND_DIR
    elif file_type == "result":
        return RESULT_DIR
    return None

def verify_token(req):
    """Simple Bearer Token authentication."""
    return req.headers.get("Authorization") == f"Bearer {API_TOKEN}"

@app.before_request
def auth_middleware():
    """Middleware to check authentication for all non-UI endpoints."""
    # Skip authentication for UI and static assets
    if request.path.startswith("/ui") or request.path.startswith("/static"):
        return
    
    if not verify_token(request):
        return jsonify({"success": False, "error": "Unauthorized access"}), 401

# ===== API Endpoints =====
@app.route("/read_file")
def read_file():
    """Fetches content of a specific command or result file."""
    file_type = request.args.get("type")
    filename = request.args.get("filename")
    
    directory = get_target_dir(file_type)
    if not directory:
        return jsonify({"success": False, "error": "Invalid file type"})

    file_path = os.path.join(directory, filename)
    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"success": True, "content": content})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/save_file", methods=["POST"])
def save_file():
    """Saves a task command or an execution result."""
    data = request.json
    directory = get_target_dir(data.get("type"))
    
    if not directory:
        return jsonify({"success": False, "error": "Invalid directory type"})
        
    file_path = os.path.join(directory, data["filename"])
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data.get("content", ""))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/delete_file", methods=["POST"])
def delete_file():
    """Removes a file from the server queues."""
    data = request.json
    directory = get_target_dir(data.get("type"))
    
    if not directory:
        return jsonify({"success": False, "error": "Invalid directory type"})
        
    file_path = os.path.join(directory, data["filename"])
    if os.path.exists(file_path):
        os.remove(file_path)
    return jsonify({"success": True})

@app.route("/list_commands", methods=["GET"])
def list_commands():
    """Lists all pending YAML commands."""
    file_type = request.args.get("type")
    dir_path = get_target_dir(file_type)
    
    if not dir_path:
        return jsonify({"success": False, "error": "Unknown file type"})

    try:
        files = [f for f in os.listdir(dir_path) if f.endswith(".yaml")]
        return jsonify({"success": True, "files": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/list_results", methods=["GET"])
def list_results():
    """Lists all available execution results."""
    try:
        files = [f for f in os.listdir(RESULT_DIR) if f.endswith(".yaml")]
        return jsonify({"success": True, "files": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ===== UI Routes =====

@app.route("/ui/")
def serve_ui_root():
    """Serves the main dashboard page."""
    return send_from_directory("static", "index.html")

@app.route("/ui/<path:path>")
def serve_static_assets(path):
    """Serves static files (CSS, JS, Images) for the dashboard."""
    return send_from_directory("static", path)

if __name__ == "__main__":
    # Listening on all interfaces for remote access
    app.run(host="0.0.0.0", port=8000)
