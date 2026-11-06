"""
Convenient Startup Script for AI Government Job Finder & Career Assistant
Run this script to start the local web application:
    py run_server.py
Then open http://localhost:8000 in your browser.
"""

import sys
import webbrowser
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print(" 🚀 Starting AI-Powered Government Job Finder & Career Assistant")
    print(" 🌐 Application URL: http://localhost:8000")
    print(" 📚 API Docs:        http://localhost:8000/docs")
    print("="*70 + "\n")
    
    # Run uvicorn server
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)

