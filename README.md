# Panther Instructor Engagement Reports

A desktop application for Canvas LMS administrators to monitor instructor activity and engagement across online courses.

## Features

- Search courses across all admin accounts
- Filter by account, year, semester, and 8-week term
- Generate engagement reports for current week or entire term
- Exports to Excel (.xlsx)

## Requirements

- Python 3.9+
- macOS or Windows

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## First Run

On first launch you will be prompted for:
1. Your institution's Canvas URL (e.g. `https://fit.instructure.com`)
2. A Canvas API token (generated in Canvas → Account → Settings → New Access Token)

Credentials are stored securely in the system keychain.

## Developed by

Darby Proctor, Ph.D.
