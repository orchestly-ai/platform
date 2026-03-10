#!/usr/bin/env python
"""
Run the Sandbox API server.

Usage:
    python run_sandbox.py

Then open http://localhost:8001/docs for API documentation.
"""

import uvicorn

if __name__ == "__main__":
    print("🎮 Starting AgentOrch Sandbox API...")
    print("   API Docs: http://localhost:8001/docs")
    print("   Demo Keys: demo-key-xxx, playground-key-xxx, investor-demo-key")
    print()

    uvicorn.run(
        "sandbox.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )
