"""Start the backend server from the correct directory."""
import os
import sys
import uvicorn

# Change to backend directory so imports work
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["."]) 
