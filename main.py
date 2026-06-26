"""
Panther Instructor Engagement Reports
Main entry point for the application
"""
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.main_window import main

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    finally:
        try:
            from PyQt6.QtCore import QThreadPool
            pool = QThreadPool.globalInstance()
            if pool is not None:
                pool.waitForDone(3000)
        except Exception:
            pass
        sys.exit(0)