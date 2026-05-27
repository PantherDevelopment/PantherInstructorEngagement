"""
Week Calculation Utilities for 8-Week Terms
Handles week numbering and date ranges for instructor engagement tracking
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional


def get_week_range(week_number: int, term_start_date: datetime) -> Tuple[datetime, datetime]:
    """
    Calculate the start and end dates for a specific week in an 8-week term.
    Weeks run Monday-Sunday.
    
    Args:
        week_number: Week number (1-8)
        term_start_date: Start date of the term
        
    Returns:
        Tuple of (week_start, week_end) as datetime objects
    """
    if week_number < 1 or week_number > 8:
        raise ValueError("Week number must be between 1 and 8")
    
    # Find the first Monday on or after term start
    # Monday = 0, Sunday = 6 in weekday()
    days_until_monday = (7 - term_start_date.weekday()) % 7
    if days_until_monday == 0 and term_start_date.weekday() != 0:
        days_until_monday = 7
    elif term_start_date.weekday() == 0:
        days_until_monday = 0
    
    first_monday = term_start_date + timedelta(days=days_until_monday)
    
    # Calculate week start (Monday)
    week_start = first_monday + timedelta(weeks=week_number - 1)
    
    # Week end is Sunday (6 days later)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    return week_start, week_end


def get_current_week_number(term_start_date: datetime, current_date: Optional[datetime] = None) -> int:
    """
    Determine which week number we're currently in (1-8).
    
    Args:
        term_start_date: Start date of the term
        current_date: Date to check (defaults to today)
        
    Returns:
        Current week number (1-8), or 0 if before term starts, 9 if after term ends
    """
    if current_date is None:
        current_date = datetime.now()
    
    # Find first Monday on or after term start
    days_until_monday = (7 - term_start_date.weekday()) % 7
    if days_until_monday == 0 and term_start_date.weekday() != 0:
        days_until_monday = 7
    elif term_start_date.weekday() == 0:
        days_until_monday = 0
    
    first_monday = term_start_date + timedelta(days=days_until_monday)
    
    if current_date < first_monday:
        # We're before the first Monday, but term may have started
        # If we're between term_start and first_monday, we're in week 1
        if current_date >= term_start_date:
            return 1
        return 0  # Before term starts
    
    # Calculate weeks elapsed since first Monday
    days_elapsed = (current_date - first_monday).days
    week_number = (days_elapsed // 7) + 1
    
    if week_number > 8:
        return 9  # After term ends
    
    return week_number


def get_current_week_range(term_start_date: datetime) -> Tuple[datetime, datetime]:
    """
    Get the date range for the current week in the term.
    
    Args:
        term_start_date: Start date of the term
        
    Returns:
        Tuple of (week_start, week_end) for current week
    """
    week_num = get_current_week_number(term_start_date)
    
    if week_num == 0:
        raise ValueError("Term has not started yet")
    if week_num == 9:
        raise ValueError("Term has already ended")
    
    return get_week_range(week_num, term_start_date)


def get_entire_term_range(term_start_date: datetime) -> Tuple[datetime, datetime]:
    """
    Get the date range for the entire term (week 1 start to current date).
    
    Args:
        term_start_date: Start date of the term
        
    Returns:
        Tuple of (term_start, current_date)
    """
    # Find first Monday on or after term start
    days_until_monday = (7 - term_start_date.weekday()) % 7
    if days_until_monday == 0 and term_start_date.weekday() != 0:
        days_until_monday = 7
    elif term_start_date.weekday() == 0:
        days_until_monday = 0
    
    first_monday = term_start_date + timedelta(days=days_until_monday)
    
    return first_monday, datetime.now()


def is_older_than_hours(timestamp: str, hours: int) -> bool:
    """
    Check if a timestamp is older than a specified number of hours.
    
    Args:
        timestamp: ISO format timestamp string
        hours: Number of hours to check against
        
    Returns:
        True if timestamp is older than specified hours
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        cutoff = datetime.now(dt.tzinfo) - timedelta(hours=hours)
        return dt < cutoff
    except (ValueError, AttributeError):
        return False
