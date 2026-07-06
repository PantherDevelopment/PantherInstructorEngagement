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
        period: str = 'current_week'
    ) -> Dict:
        data = {
            'course_id':    course_id,
            'instructor_id': instructor_id,
            'period_start': period_start.strftime('%Y-%m-%d'),
            'period_end':   period_end.strftime('%Y-%m-%d'),
        }
        errors = []

        def merge(result):
            """Merge batch result, capturing any error or info flags"""
            err = result.pop('_error', None)
            no_disc = result.pop('_no_discussions', False)
            if err:
                errors.append(err)
            if no_disc:
                errors.append('No discussion topics in this course')
            data.update(result)

        # Batch 1 always runs
        merge(self.batch1_enrollment(course_id, instructor_id))

        # Batch 2 - page views only for current week
        if period == 'current_week':
            merge(self.batch2_page_views(instructor_id, course_id, period_start, period_end))

        # Batch 3 - discussions
        merge(self.batch3_discussions(course_id, instructor_id, period_start, period_end, period))

        # Batch 4 - submissions
        merge(self.batch4_submissions(course_id))

        # Batch 5 - announcements
        merge(self.batch5_announcements(course_id, instructor_id, period_start, period_end))

        # Batch 6 - profile
        merge(self.batch6_profile(instructor_id))

        # Summarize errors for Excel notes column
        data['collection_notes'] = '; '.join(errors) if errors else 'OK'

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
        except Exception as e:
            return {'last_login_date': None, 'total_activity_time': '0h 0m', '_error': f'Enrollment API: {e}'}

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
        except Exception as e:
            return {'login_count_week': 0, '_error': f'Page Views API: {e}'}

    # -----------------------------------------------------------------------
    # BATCH 3: Discussions
    # current_week: week posts/replies + term totals
    # entire_term:  term totals only
    # If no discussion topics exist, returns N/A for all discussion fields
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
        NA           = 'N/A'

        posts_period    = 0
        posts_total     = 0
        replies_period  = 0
        replies_total   = 0
        error_msg       = None

        try:
            topics = self.api._make_paginated_request(
                'GET',
                f'/api/v1/courses/{course_id}/discussion_topics',
                {'per_page': 100}
            )

            # No discussion topics - return N/A for all fields
            if not topics:
                result = {
                    'discussion_posts_total':   NA,
                    'discussion_replies_total': NA,
                    '_no_discussions':          True,
                }
                if is_week:
                    result['discussion_posts_week']   = NA
                    result['discussion_replies_week'] = NA
                return result

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

                        if entry_user == instr_id_str:
                            posts_total += 1
                            if is_week and created_at and self._in_period(created_at, period_start, period_end):
                                posts_period += 1

                        entry_id = entry.get('id')
                        try:
                            all_replies = self.api._make_paginated_request(
                                'GET',
                                f'/api/v1/courses/{course_id}/discussion_topics/{topic_id}/entries/{entry_id}/replies',
                                {'per_page': 100}
                            )
                        except:
                            all_replies = entry.get('recent_replies', [])

                        for reply in all_replies:
                            reply_user    = str(reply.get('user_id', ''))
                            reply_created = reply.get('created_at', '')

                            if reply_user == instr_id_str:
                                replies_total += 1
                                if is_week and reply_created and self._in_period(reply_created, period_start, period_end):
                                    replies_period += 1

                except Exception:
                    continue

        except Exception as e:
            error_msg = f'Discussions API: {e}'

        result = {
            'discussion_posts_total':   posts_total,
            'discussion_replies_total': replies_total,
        }

        if is_week:
            result['discussion_posts_week']   = posts_period
            result['discussion_replies_week'] = replies_period

        if error_msg:
            result['_error'] = error_msg

        return result

    # -----------------------------------------------------------------------
    # BATCH 4: Submissions - per-assignment approach, UTC timezone safe
    # -----------------------------------------------------------------------
    def batch4_submissions(self, course_id: str) -> Dict:
        disc_7days  = 0
        other_7days = 0
        now_utc     = datetime.utcnow()

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

                # Use due date - only count if due more than 7 days ago
                due_at = assignment.get('due_at')
                if not due_at:
                    continue  # skip assignments with no due date

                due_dt   = datetime.fromisoformat(due_at.replace('Z', '+00:00')).replace(tzinfo=None)
                days_due = (now_utc - due_dt).days

                if days_due <= 7:
                    continue  # due date not yet 7 days past

                # Count all ungraded submissions for this assignment
                try:
                    subs = self.api._make_paginated_request(
                        'GET',
                        f'/api/v1/courses/{course_id}/assignments/{a_id}/submissions',
                        {'per_page': 100}
                    )

                    for sub in subs:
                        if sub.get('workflow_state') not in ('submitted', 'pending_review'):
                            continue
                        if not sub.get('submitted_at'):
                            continue

                        if is_disc:
                            disc_7days += 1
                        else:
                            other_7days += 1

                except Exception:
                    continue

        except Exception as e:
            return {
                'discussion_not_graded_7days': 0,
                'other_not_graded_7days':      0,
                '_error': f'Submissions API: {e}'
            }

        return {
            'discussion_not_graded_7days': disc_7days,
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
        except Exception as e:
            return {'announcements_count': 0, '_error': f'Announcements API: {e}'}

        return {'announcements_count': count}

    # -----------------------------------------------------------------------
    # BATCH 6: Profile - Bio Complete
    # -----------------------------------------------------------------------
    def batch6_profile(self, instructor_id: str) -> Dict:
        try:
            profile = self.api._make_request('GET', f'/api/v1/users/{instructor_id}/profile')
            bio = profile.get('bio', '')
            return {'instructor_bio_complete': 'Y' if bio and bio.strip() else 'N'}
        except Exception as e:
            return {'instructor_bio_complete': 'N', '_error': f'Profile API: {e}'}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _in_period(self, timestamp: str, period_start: datetime, period_end: datetime) -> bool:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
            return period_start <= dt <= period_end
        except:
            return False