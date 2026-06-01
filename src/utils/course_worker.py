"""
Course Worker - runs data collection for a single course in a background thread.
Uses QThreadPool so multiple courses are collected simultaneously.
"""

from datetime import datetime
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal


class WorkerSignals(QObject):
    """
    Signals emitted by CourseWorker back to the main UI thread.
    QObject must be separate from QRunnable for signals to work.
    """
    finished  = pyqtSignal(dict)   # emits collected data dict on success
    error     = pyqtSignal(str)    # emits error message on failure
    progress  = pyqtSignal(int, int)  # emits (completed, total)


class CourseWorker(QRunnable):
    """
    Collects engagement data for a single course in a background thread.
    Wraps EngagementCollector.collect_instructor_data() unchanged.
    """

    def __init__(
        self,
        api_client,
        course: dict,
        period_start: datetime,
        period_end: datetime,
        period: str,
        completed_ref: list,   # shared mutable list for progress tracking
        total: int
    ):
        super().__init__()
        self.api_client   = api_client
        self.course       = course
        self.period_start = period_start
        self.period_end   = period_end
        self.period       = period
        self.completed    = completed_ref  # shared across all workers
        self.total        = total
        self.signals      = WorkerSignals()

        # Worker should not block program exit
        self.setAutoDelete(True)

    def run(self):
        """Runs in a background thread - do NOT touch UI here"""
        try:
            from src.utils.engagement_collector import EngagementCollector

            course_id       = self.course.get('id')
            course_name     = self.course.get('name')
            course_code     = self.course.get('course_code')
            teachers        = self.course.get('teachers', [])

            if not teachers:
                self.signals.error.emit(f"{course_code}: No instructor found")
                return

            instructor      = teachers[0]
            instructor_id   = instructor.get('id')
            instructor_name = instructor.get('display_name')

            collector = EngagementCollector(self.api_client)
            data = collector.collect_instructor_data(
                str(course_id),
                str(instructor_id),
                self.period_start,
                self.period_end,
                self.period
            )

            data['course_code']     = course_code
            data['course_name']     = course_name
            data['instructor_name'] = instructor_name

            # Update shared progress counter
            self.completed[0] += 1
            self.signals.progress.emit(self.completed[0], self.total)
            self.signals.finished.emit(data)

        except Exception as e:
            self.completed[0] += 1
            self.signals.progress.emit(self.completed[0], self.total)
            course_code = self.course.get('course_code', 'Unknown')
            self.signals.error.emit(f"{course_code}: {e}")
