import subprocess
import sys
import os
from flask import Flask, render_template_string

app = Flask(__name__)

# HTML Template for the control panel
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Hedge Fund Remote Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0e1117; color: white; text-align: center; padding: 20px; }
        h1 { margin-bottom: 30px; }
        .btn {
            background-color: #00d4ff;
            color: black;
            border: none;
            padding: 20px 40px;
            font-size: 24px;
            font-weight: bold;
            border-radius: 12px;
            cursor: pointer;
            width: 100%;
            max-width: 300px;
            box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4);
            transition: transform 0.2s;
        }
        .btn.stop {
            background-color: #ff4b4b;
            box-shadow: 0 4px 15px rgba(255, 75, 75, 0.4);
            margin-top: 20px;
        }
    </style>
    <script>
        function sendCommand(endpoint) {
            var btn = event.srcElement;
            var originalText = btn.innerHTML;
            var status = document.getElementById('statusMsg');
            
            btn.disabled = true;
            btn.innerHTML = "Processing...";
            status.innerHTML = "Sending command...";
            
            fetch(endpoint, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                status.innerHTML = data.message;
                btn.disabled = false;
                btn.innerHTML = originalText;
                
                if (data.status === 'success' && endpoint === '/start') {
                     document.getElementById('successMsg').style.display = 'block';
                }
            })
            .catch(err => {
                btn.innerHTML = "Error!";
                status.innerHTML = "Network Error";
                btn.disabled = false;
            });
        }
    </script>
</head>
<body>
    <h1>🤖 AI Hedge Fund<br>Remote Control</h1>
    
    <button id="startBtn" class="btn" onclick="sendCommand('/start')">START SYSTEM 🚀</button>
    <button id="stopBtn" class="btn stop" onclick="sendCommand('/stop')">STOP SYSTEM 🛑</button>
    
    <div id="statusMsg" class="status"></div>
    <div id="successMsg" class="success">
        ✅ Command Sent!<br>
        Bot and Dashboard are launching on your laptop.
    </div>
    
    <div class="bypass-msg">
        <b>Tip:</b> If you see a "Click to Continue" page before this, that is normal security from the tunnel provider.
    </div>
</body>
</html>
"""

def open_terminal(command, title="Terminal"):
    """Runs a command in a new separate window that stays open."""
    if sys.platform == "win32":
        # 'start' opens a new window
        # 'cmd /k' executes the command and keeps the window open (so you can see errors)
        # We wrap the command in quotes for safety
        full_command = f'start "{title}" cmd /k "{command}"'
        subprocess.Popen(full_command, shell=True)
    else:
        subprocess.Popen(command, shell=True)

@app.route('/')
def index():
    try:
        print("Someone accessed the control panel")
        # Return the HTML directly to avoid Jinja2 template syntax errors (e.g. conflicting braces)
        return HTML_TEMPLATE
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"CRITICAL ERROR: {str(e)}", 200

@app.route('/start', methods=['POST'])
def start_system():
    try:
        # Get the directory of this script to ensure we run main.py from the right place
        cwd = os.path.dirname(os.path.abspath(__file__))
        
        print(f"Received remote START command")
        
        # 1. Start the Trading Bot
        print("   - Launching Trading Bot...")
        open_terminal(f"python \"{os.path.join(cwd, 'main.py')}\"", title="Hedge Fund BOT")
        
        # 2. Start the Dashboard
        print("   - Launching Dashboard...")
        open_terminal(f"python -m streamlit run \"{os.path.join(cwd, 'dashboard.py')}\"", title="Hedge Fund DASHBOARD")
        
        return {"status": "success", "message": "Systems initiated"}
    except Exception as e:
        print(f"Error starting systems: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route('/stop', methods=['POST'])
def stop_system():
    try:
        print(f"Received remote STOP command")
        
        current_pid = os.getpid()
        
        # PowerShell command to:
        # 1. Kill all python processes EXCEPT this one (remote_controller)
        # 2. Kill the cmd windows titled 'Hedge Fund*'
        ps_command = (
            f"powershell -Command \""
            f"Get-Process python -ErrorAction SilentlyContinue | Where-Object {{ $_.Id -ne {current_pid} }} | Stop-Process -Force; "
            f"Get-Process | Where-Object {{ $_.MainWindowTitle -like '*Hedge Fund*' }} | Stop-Process -Force"
            f"\""
        )
        
        subprocess.run(ps_command, shell=True)
        
        return {"status": "success", "message": "Systems Stopped"}
    except Exception as e:
        print(f"Error stopping systems: {e}")
        return {"status": "error", "message": str(e)}, 500

if __name__ == '__main__':
    print("Local Server Starting on Port 5000...")
    # Run Flask on all interfaces
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
