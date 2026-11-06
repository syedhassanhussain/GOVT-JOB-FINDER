"""
Vercel Serverless Function Entrypoint for FastAPI Application
"""
import sys
import traceback
from pathlib import Path

# Add project root directory to sys.path so 'backend.app' modules resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from backend.app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    err_tb = traceback.format_exc()
    print(f"[FATAL VERCEL STARTUP ERROR]:\n{err_tb}", file=sys.stderr)
    app = FastAPI(title="Diagnostic Mode")

    @app.get("/{full_path:path}")
    def error_handler(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI Initialization Failed",
                "detail": str(e),
                "traceback": err_tb.splitlines()
            }
        )
