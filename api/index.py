"""Vercel serverless function entrypoint."""
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.app import app

# Vercel expects 'app' to be exported
