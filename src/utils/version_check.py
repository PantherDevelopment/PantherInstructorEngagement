"""
Version checker - checks GitHub releases for newer versions on startup
"""

import sys
import os
import requests
from pathlib import Path


GITHUB_REPO = "PantherDevelopment/PantherInstructorEngagement"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def get_current_version() -> str:
    """Read current version from VERSION file - works both in dev and bundled app"""
    try:
        # When bundled with PyInstaller, files are in sys._MEIPASS
        if hasattr(sys, '_MEIPASS'):
            version_file = Path(sys._MEIPASS) / 'VERSION'
        else:
            version_file = Path(__file__).parent.parent.parent / 'VERSION'
        return version_file.read_text().strip()
    except Exception:
        return "0.0.0"


def get_latest_release() -> dict:
    """
    Fetch latest release info from GitHub.
    Returns dict with 'version', 'url', 'name' or None if check fails.
    """
    try:
        response = requests.get(
            RELEASES_URL,
            timeout=5,
            headers={'Accept': 'application/vnd.github.v3+json'}
        )
        if response.status_code == 200:
            data = response.json()
            tag = data.get('tag_name', '').lstrip('v')
            return {
                'version': tag,
                'name':    data.get('name', f'v{tag}'),
                'url':     data.get('html_url', ''),
            }
    except Exception:
        pass
    return None


def is_newer(latest: str, current: str) -> bool:
    """Return True if latest version is newer than current"""
    try:
        def parse(v):
            return tuple(int(x) for x in v.strip().split('.'))
        return parse(latest) > parse(current)
    except Exception:
        return False


def check_for_updates() -> dict:
    """
    Check if a newer version is available.
    Returns dict with update info, or None if up to date or check failed.
    """
    current = get_current_version()
    latest  = get_latest_release()

    if latest and is_newer(latest['version'], current):
        return {
            'current': current,
            'latest':  latest['version'],
            'name':    latest['name'],
            'url':     latest['url'],
        }
    return None