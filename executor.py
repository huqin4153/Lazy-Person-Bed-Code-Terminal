import requests
import yaml
import time
import subprocess
import os

# ===== Configuration =====
# The address of the relay/task server
SERVER = "http://127.0.0.1:8000" 

# Secret token for authentication
TOKEN = "<your api token>"

# The root directory where tasks will be executed locally
BASE_DIR = "./project"

# Path to the virtual environment's Python interpreter. 
# Update this to match your local setup.
VENV_PYTHON = r"<your python.exe path>"

# Path to the virtual environment's Pip tool.
VENV_PIP = r"<your pip.exe path>"

# Standard authorization headers
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ===== Utility Functions =====
def run_pip(command, package):
    """
    Executes pip commands (install/uninstall) within the specified virtual environment.
    """
    try:
        # Construct the base command list
        cmd_list = [VENV_PIP, command, package]
        
        # Add auto-confirm flag only for uninstallation
        if command == "uninstall":
            cmd_list.append("-y")
            
        # Execute the process with a 5-minute timeout
        result = subprocess.run(
            cmd_list,
            capture_output=True, 
            text=True, 
            timeout=300
        )
        
        # Return success with combined stdout and stderr for debugging
        return True, result.stdout + result.stderr
    except Exception as e:
        return False, f"Pip execution failed: {str(e)}"

def create_file(file, content):
    """
    Creates a new file or overwrites an existing one. 
    Automatically creates parent directories if they don't exist.
    """
    abs_path = os.path.join(BASE_DIR, file)
    
    # Create the directory structure if it doesn't exist
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    
    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"File '{file}' created successfully."
    except Exception as e:
        return False, f"Failed to create file: {str(e)}"

def delete_file(file):
    """
    Removes a file from the local file system.
    """
    abs_path = os.path.join(BASE_DIR, file)
    
    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
            return True, f"File '{file}' deleted successfully."
        return False, "Delete failed: File not found."
    except Exception as e:
        # Handle cases like "Permission Denied"
        return False, f"Delete failed: {str(e)}"

def update_file(file, range_str, content):
    """
    Updates specific lines, appends content, or overwrites the entire file.
    Supports smart line-break handling to prevent concatenation issues.
    """
    abs_path = os.path.join(BASE_DIR, file)
    if not os.path.exists(abs_path):
        return False, "File not found."

    # --- Full File Overwrite Patch ---
    # Triggered by a specific range from the frontend for total replacement
    if range_str == "0-999999":
        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, "File overwritten successfully."
        except Exception as e:
            return False, f"Overwrite failed: {str(e)}"

    # Read existing content
    with open(abs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Normalize input: split into lines and ensure each has a newline character
    new_lines = [line + "\n" for line in content.splitlines()]

    # Append Mode: triggered if range_str is empty, "0", or "append"
    if not range_str or range_str.lower() == "append":
        # Ensure the existing last line ends with a newline to prevent "sticking"
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.extend(new_lines)
        msg = "Content successfully appended to end of file."
    
    # Range Mode: handles line replacement (e.g., "5-10") or single-line edits ("5")
    else:
        try: 
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
            else:
                # Support single line shorthand, e.g., "5"
                start = end = int(range_str)

            # Fix: Ensure the line before the update has a newline
            if start > 1 and len(lines) >= start - 1:
                if not lines[start-2].endswith("\n"):
                    lines[start-2] += "\n"

            # Python list slicing is start-inclusive and end-exclusive (0-based)
            # lines[0:1] represents the first line in human terms.
            lines[start-1:end] = new_lines
            msg = f"Lines {start}-{end} updated."
        except ValueError:
            return False, "Invalid line range. Use 'start-end' or 'append'."

    # Write the processed list back to the file
    with open(abs_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True, msg

def read_file(file, range_str=None):
    """
    Reads a file with a 5MB safety limit. 
    Uses binary mode and 'ignore' decoding to prevent crashes on non-UTF-8 or binary files.
    """
    abs_path = os.path.join(BASE_DIR, file)
    if not os.path.exists(abs_path):
        return False, "File not found."

    try:
        # 1. Use "rb" (binary read) mode for maximum safety across all file types
        with open(abs_path, "rb") as f:
            # 2. Safety Limit: Read up to 5MB to prevent memory exhaustion (OOM)
            # 5MB covers almost any source code while keeping the response snappy
            if not range_str:
                raw_data = f.read(5 * 1024 * 1024) 
                # Decode with errors="ignore" to ensure the process never crashes on binary data
                return True, raw_data.decode("utf-8", errors="ignore")
            
            # 3. Line Range Reading
            # We read the first 5MB and then process line slices
            f.seek(0)  # Reset to beginning of file
            content = f.read(5 * 1024 * 1024).decode("utf-8", errors="ignore")
            line_list = content.splitlines(keepends=True)
            
            try:
                if "-" in range_str:
                    start, end = map(int, range_str.split("-"))
                else:
                    start = end = int(range_str)
                
                # Python slicing is safe even if indices are out of range
                return True, "".join(line_list[start-1:end])
            except ValueError:
                return False, "Invalid range format. Use 'start-end'."

    except Exception as e:
        return False, f"Read error: {str(e)}"

def compile_file_unused(file, output):
    """
    Note: This is a legacy function and is not integrated into the current task executor.
    """
    abs_path = os.path.join(BASE_DIR, file)
    if not os.path.exists(abs_path):
        return False, "File not found."
    
    try:
        import py_compile
        # Compiles the source file to the specified output path
        py_compile.compile(abs_path, cfile=output)
        return True, f"Compilation successful. Output: {output}"
    except Exception as e:
        # Return the error message if compilation fails (e.g., SyntaxError)
        return False, f"Compilation failed: {str(e)}"

def execute_file(file, args=""):
    """
    Executes a Python file using the configured virtual environment.
    Captures standard output (stdout) and error output (stderr).
    """
    abs_path = os.path.join(BASE_DIR, file)
    if not os.path.exists(abs_path):
        return False, "File not found."

    try:
        # Build the command: [Python_Interpreter, Script_Path, Argument1, Argument2, ...]
        cmd = [VENV_PYTHON, abs_path] + args.split()
        
        # Execute the script with a 5-minute (300s) timeout protection
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300
        )
        
        # Return both stdout and stderr for remote debugging
        return True, {
            "stdout": result.stdout, 
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return False, "Execution failed: Script timed out (limit: 300s)."
    except Exception as e:
        return False, f"Execution error: {str(e)}"
       
# ===== Task Dispatcher =====
def process_command_file(filename):
    """
    Fetches and dispatches commands. 
    Each action is wrapped in a try-except block to ensure that a single 
    KeyError or parameter issue doesn't break the entire cleanup loop.
    """
    # 1. Fetch & Parse YAML
    try:
        r = requests.get(f"{SERVER}/read_file", params={"type":"command", "filename": filename}, headers=HEADERS)
        if not r.ok: return
        
        yaml_content = r.json().get("content", "")
        try:
            config = yaml.safe_load(yaml_content)
            if not config: raise ValueError("Empty YAML payload")
        except Exception as yaml_err:
            # If YAML is unreadable, delete it directly to unblock the queue
            print(f"Skipping corrupted YAML {filename}: {yaml_err}")
            requests.post(f"{SERVER}/delete_file", json={"type":"command","filename":filename}, headers=HEADERS)
            return
            
        # --- Pre-validation Check ---
        action = config.get("action")
        if not action:
            result = {"success": False, "error": "Missing 'action' attribute in YAML"}
            # Jump to finalization to cleanup this invalid command
            finalize_task(filename, result)
            return
        result = {"success": False} # Default to False unless successful

        # 2. Action Dispatching with Individual "Bulletproof" Wrappers
        # Each block is isolated to catch missing keys (KeyError) or invalid arguments
        if action == "install_pip":
            try:
                success, msg = run_pip("install", config["package"])
                result = {"success": success, "message": msg}
            except Exception as e:
                result["error"] = f"Pip install error: {str(e)}"

        elif action == "uninstall_pip":
            try:
                success, msg = run_pip("uninstall", config["package"])
                result = {"success": success, "message": msg}
            except Exception as e:
                result["error"] = f"Pip uninstall error: {str(e)}"

        elif action == "create_file":
            try:
                success, msg = create_file(config["file"], config.get("content",""))
                result = {"success": success, "message": msg}
            except Exception as e:
                result["error"] = f"Create file error: {str(e)}"

        elif action == "delete_file":
            try:
                success, msg = delete_file(config["file"])
                result = {"success": success, "message": msg}
            except Exception as e:
                result["error"] = f"Delete file error: {str(e)}"

        elif action == "update_file":
            try:
                success, msg = update_file(config["file"], config["range"], config.get("content",""))
                result = {"success": success, "message": msg}
            except Exception as e:
                result["error"] = f"Update file error: {str(e)}"

        elif action == "read_file":
            try:
                success, content = read_file(config["file"], config.get("range"))
                result = {"success": success, "content": content}
            except Exception as e:
                result["error"] = f"Read file error: {str(e)}"

        elif action == "execute":
            try:
                success, output = execute_file(config["file"], config.get("args", ""))
                result = {"success": success}
                if success: result.update(output)
                else: result["error"] = output
            except Exception as e:
                result["error"] = f"Execution error: {str(e)}"

        elif action == "list_executor_dir":
            try:
                file_list = []
                for root, dirs, files in os.walk(BASE_DIR):
                    for f in files:
                        rel_path = os.path.relpath(os.path.join(root,f), BASE_DIR)
                        file_list.append(rel_path)
                result = {"success": True, "files": file_list}
            except Exception as e:
                result["error"] = f"Directory listing error: {str(e)}"

        else:
            result["error"] = f"Unknown action: {action}"

    except Exception as network_e:
        print(f"Network error: {network_e}")
        return

    # 3. Finalization: Ensures corrupted/finished tasks are always cleared
    finalize_task(filename, result)

def finalize_task(filename, result):
    """Helper to upload results and delete the command file."""
    try:
        requests.post(f"{SERVER}/save_file", json={"type":"result","filename":filename,"content":yaml.safe_dump(result)}, headers=HEADERS)
        requests.post(f"{SERVER}/delete_file", json={"type":"command","filename":filename}, headers=HEADERS)
    except Exception as e:
        print(f"Finalization failed for {filename}: {e}")

# ===== Main Polling Loop =====
def main_loop():
    """
    Main execution loop that polls the remote server for new commands.
    """
    print(f"Executor started. Monitoring server at: {SERVER}")
    print("Base directory:", os.path.abspath(BASE_DIR))

    while True:
        try:
            # 1. Fetch the list of pending command files from the server
            # We use a 10s timeout to prevent the loop from hanging on network issues
            r = requests.get(
                f"{SERVER}/list_commands", 
                params={"type": "command"}, 
                headers=HEADERS, 
                timeout=10
            )
            
            if r.ok:
                files = r.json().get("files", [])
                if files:
                    print(f"Found {len(files)} new task(s). Processing...")
                
                for filename in files:
                    try:
                        # Dispatch each task to the processor
                        process_command_file(filename)
                    except Exception as e:
                        print(f"[ERROR] Critical failure while processing {filename}: {e}")
            else:
                print(f"[WARNING] Failed to fetch command list. Status Code: {r.status_code}")
        
        except requests.exceptions.RequestException as e:
            # Catching connection errors, timeouts, etc.
            print(f"[NETWORK ERROR] Server unreachable: {e}")

        # Polling interval to prevent CPU/Network exhaustion
        time.sleep(1)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nExecutor stopped by user.")
