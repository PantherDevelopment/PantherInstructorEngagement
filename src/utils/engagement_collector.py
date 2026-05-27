"""
Engagement Data Collector
Two collection paths: current_week (week-specific data) and entire_term (totals only)
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List
from src.api.canvas_client import CanvasAPIClient


class EngagementCollector:

    def __init__(self, api_client: CanvasAPIClient):
        self.api = api_client

    def collect_instructor_data(
        self,
        course_id: str,
        instructor_id: str,
        period_start: datetime,
        period_end: datetime,
        period: str = 'current_week'   # 'current_week' or 'entire_term'
    ) -> Dict:
        data = {
            'course_id':    course_id,
            'instructor_id': instructor_id,
            'period_start': period_start.strftime('%Y-%m-%d'),
            'period_end':   period_end.strftime('%Y-%m-%d'),
        }

        # Batch 1 always runs - gives last login + total activity time
        data.update(self.batch1_enrollment(course_id, instructor_id))

        # Batch 2 - page views only meaningful for current week
        if period == 'current_week':
            data.update(self.batch2_page_views(instructor_id, course_id, period_start, period_end))
        # No login count for term report

        # Batch 3 - discussions (different fields for week vs term)
        data.update(self.batch3_discussions(course_id, instructor_id, period_start, period_end, period))

        # Batch 4 - submissions (same logic regardless of period)
        data.update(self.batch4_submissions(course_id))

        # Batch 5 - announcements filtered by period
        data.update(self.batch5_announcements(course_id, instructor_id, period_start, period_end))

        # Batch 6 - profile (always the same)
        data.update(self.batch6_profile(instructor_id))

        return data

    # -----------------------------------------------------------------------
    # BATCH 1: Enrollments - Last Login Date (ET) + Total Activity Time
    # -----------------------------------------------------------------------
    def batch1_enrollment(self, course_id: str, instructor_id: str) -> Dict:
        try:
            from zoneinfo import ZoneInfo
            eastern = ZoneInfo('America/New_York')

            enrollments = self.api._make_request(
                'GET',
                f'/api/v1/courses/{course_id}/enrollments',
                {'user_id': instructor_id, 'type[]': 'TeacherEnrollment'}
            )
            if not enrollments:
                return {'last_login_date': None, 'total_activity_time': '0h 0m'}

            enrollment    = enrollments[0]
            last_utc      = enrollment.get('last_activity_at')
            total_seconds = enrollment.get('total_activity_time', 0) or 0

            # Convert to Eastern
            last_login_et = None
            if last_utc:
                try:
                    dt_utc        = datetime.fromisoformat(last_utc.replace('Z', '+00:00'))
                    dt_et         = dt_utc.astimezone(eastern)
                    last_login_et = dt_et.strftime('%Y-%m-%d %H:%M %Z')
                except:
                    last_login_et = last_utc

            hours   = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            return {
                'last_login_date':    last_login_et,
                'total_activity_time': f"{hours}h {minutes}m"
            }
        except Exception:
            return {'last_login_date': None, 'total_activity_time': '0h 0m'}

    # -----------------------------------------------------------------------
    # BATCH 2: Page Views - unique days active in this course during the week
    # Only called for current_week reports
    # -----------------------------------------------------------------------
    def batch2_page_views(
        self,
        instructor_id: str,
        course_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        try:
            page_views = self.api._make_paginated_request(
                'GET',
                f'/api/v1/users/{instructor_id}/page_views',
                {
                    'start_time': period_start.strftime('%Y-%m-%dT00:00:00Z'),
                    'end_time':   period_end.strftime('%Y-%m-%dT23:59:59Z'),
                    'per_page':   100
                }
            )

            active_days = set()
            for view in page_views:
                if (view.get('context_type') == 'Course' and
                        str(view.get('context_id', '')) == str(course_id)):
                    created = view.get('created_at', '')
                    if created:
                        try:
                            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            active_days.add(dt.date())
                        except:
                            pass

            return {'login_count_week': len(active_days)}
        except Exception:
            return {'login_count_week': 0}

    # -----------------------------------------------------------------------
    # BATCH 3: Discussions
    # current_week: week posts/replies + term totals + unanswered >36hrs
    # entire_term:  term totals + unanswered >36hrs (no week columns)
    # -----------------------------------------------------------------------
    def batch3_discussions(
        self,
        course_id: str,
        instructor_id: str,
        period_start: datetime,
        period_end: datetime,
        period: str
    ) -> Dict:
        instr_id_str = str(instructor_id)
        is_week      = (period == 'current_week')

        posts_period    = 0
        posts_total     = 0
        replies_period  = 0
        replies_total   = 0

        try:
            topics = self.api._make_paginated_request(
                'GET',
                f'/api/v1/courses/{course_id}/discussion_topics',
                {'per_page': 100}
            )

            for topic in topics:
                topic_id = topic.get('id')
                try:
                    entries = self.api._make_paginated_request(
                        'GET',
                        f'/api/v1/courses/{course_id}/discussion_topics/{topic_id}/entries',
                        {'per_page': 100}
                    )

                    for entry in entries:
                        entry_user = str(entry.get('user_id', ''))
                        created_at = entry.get('created_at', '')

                        # Instructor top-level post
                        if entry_user == instr_id_str:
                            posts_total += 1
                            if is_week and created_at and self._in_period(created_at, period_start, period_end):
                                posts_period += 1

                        # Fetch ALL replies for this entry
                        entry_id = entry.get('id')
                        try:
                            all_replies = self.api._make_paginated_request(
                                'GET',
                                f'/api/v1/courses/{course_id}/discussion_topics/{topic_id}/entries/{entry_id}/replies',
                                {'per_page': 100}
                            )
                        except:
                            all_replies = entry.get('recent_replies', [])

                        # Count ONLY instructor replies
                        instructor_replied = False
                        for reply in all_replies:
                            reply_user    = str(reply.get('user_id', ''))
                            reply_created = reply.get('created_at', '')

                            if reply_user == instr_id_str:
                                instructor_replied = True
                                replies_total += 1
                                if is_week and reply_created and self._in_period(reply_created, period_start, period_end):
                                    replies_period += 1

                except Exception:
                    continue

        except Exception:
            pass

        result = {
            'discussion_posts_total':   posts_total,
            'discussion_replies_total': replies_total,
        }

        # Only include period-specific counts for current_week reports
        if is_week:
            result['discussion_posts_week']   = posts_period
            result['discussion_replies_week'] = replies_period

        return result

    # -----------------------------------------------------------------------
    # BATCH 4: Submissions - per-assignment approach, UTC timezone safe
    # -----------------------------------------------------------------------
    def batch4_submissions(self, course_id: str) -> Dict:
        disc_4days  = 0
        disc_7days  = 0
        other_4days = 0
        other_7days = 0
        now_utc     = datetime.now(timezone.utc)

        try:
            assignments = self.api._make_paginated_request(
                'GET',
                f'/api/v1/courses/{course_id}/assignments',
                {'per_page': 100, 'include[]': ['needs_grading_count']}
            )

            for assignment in assignments:
                if assignment.get('needs_grading_count', 0) <= 0:
                    continue

                a_id    = assignment['id']
                a_name  = assignment.get('name', '')
                is_disc = 'discussion' in a_name.lower()

                try:
                    subs = self.api._make_paginated_request(
                        'GET',
                        f'/api/v1/courses/{course_id}/assignments/{a_id}/submissions',
                        {'per_page': 100, 'workflow_state': 'submitted'}
                    )

                    for sub in subs:
                        if sub.get('graded_at') or not sub.get('submitted_at'):
                            continue
                        try:
                            submitted_dt = datetime.fromisoformat(
                                sub['submitted_at'].replace('Z', '+00:00')
                            )
                            days_old = (now_utc - submitted_dt).days

                            if is_disc:
                                if days_old > 7:
                                    disc_7days += 1
                                    disc_4days += 1
                                elif days_old > 4:
                                    disc_4days += 1
                            else:
                                if days_old > 7:
                                    other_7days += 1
                                    other_4days += 1
                                elif days_old > 4:
                                    other_4days += 1
                        except Exception:
                            continue
                except Exception:
                    continue

        except Exception:
            pass

        return {
            'discussion_not_graded_4days': disc_4days,
            'discussion_not_graded_7days': disc_7days,
            'other_not_graded_4days':      other_4days,
            'other_not_graded_7days':      other_7days,
        }

    # -----------------------------------------------------------------------
    # BATCH 5: Announcements - filtered by period dates
    # -----------------------------------------------------------------------
    def batch5_announcements(
        self,
        course_id: str,
        instructor_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        count = 0
        try:
            announcements = self.api._make_paginated_request(
                'GET',
                '/api/v1/announcements',
                {
                    'context_codes[]': f'course_{course_id}',
                    'per_page':        100,
                    'start_date':      period_start.strftime('%Y-%m-%d'),
                    'end_date':        period_end.strftime('%Y-%m-%d')
                }
            )
            for ann in announcements:
                if str(ann.get('author', {}).get('id', '')) == str(instructor_id):
                    count += 1
        except Exception:
            pass

        return {'announcements_count': count}

    # -----------------------------------------------------------------------
    # BATCH 6: Profile - Bio Complete
    # -----------------------------------------------------------------------
    def batch6_profile(self, instructor_id: str) -> Dict:
        try:
            profile = self.api._make_request('GET', f'/api/v1/users/{instructor_id}/profile')
            bio = profile.get('bio', '')
            return {'instructor_bio_complete': 'Y' if bio and bio.strip() else 'N'}
        except Exception:
            return {'instructor_bio_complete': 'N'}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _in_period(self, timestamp: str, period_start: datetime, period_end: datetime) -> bool:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
            return period_start <= dt <= period_end
        except:
            return False
