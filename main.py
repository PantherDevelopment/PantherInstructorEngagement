"""
Panther Instructor Engagement Reports
Main entry point for the application
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.main_window import main
import sys

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    finally:
        from PyQt6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(3000)  # wait max 3s for threads
        sys.exit(0)