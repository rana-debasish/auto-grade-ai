"""
🏠 AI Evaluation System - Local Launcher
Use this script for development and debugging. It enables verbose logging and debug mode.
"""
import os
import sys
import subprocess

# 1. Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Enable verbose logging and debug mode
os.environ['SILENT_STARTUP'] = '0'
os.environ['FLASK_DEBUG'] = '1'

# 2. Add backend to sys.path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.chdir(backend_dir)

# 3. Start App
try:
    from app import app
    print("=" * 60)
    print("🚀 Starting AI Evaluation System (LOCAL DEBUG MODE)")
    print(f"🏠 Access locally at: http://localhost:{os.getenv('PORT', 5000)}")
    print("=" * 60)
    # Disable reloader to prevent the "can't open file backend/start_locally.py" error on Windows
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True, use_reloader=False)
except Exception as e:
    print(f"\n❌ SERVER CRASHED: {e}")
    import traceback
    traceback.print_exc()
