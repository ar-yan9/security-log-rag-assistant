"""Run the built workbench on loopback only. Ctrl+C stops it."""
from pathlib import Path
import sys
import uvicorn

if __name__ == '__main__':
    if not (Path(__file__).parent / 'frontend' / 'dist' / 'index.html').is_file():
        sys.exit('Build the frontend first: cd frontend, npm ci, npm run build')
    uvicorn.run('app:app', host='127.0.0.1', port=8000, reload=False)
