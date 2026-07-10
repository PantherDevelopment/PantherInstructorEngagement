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
    finished  = pyqtSignal(dict)
    error     = pyqtSignal(str)
    progress  = pyqtSignal(int, int)


class CourseWorker(QRunnable):
    """
    Collects engagement data for a single course in a background thread.
    Accepts a pre-created collector to avoid import issues in threads.
    """

    def __init__(
        self,
        collector,
        course: dict,
        period_start: datetime,
        period_end: datetime,
        period: str,
        completed_ref: list,
        total: int,
        cancel_flag_ref: list = None
    ):
        super().__init__()
        self.collector    = collector
        self.course       = course
        self.period_start = period_start
        self.period_end   = period_end
        self.period       = period
        self.completed    = completed_ref
        self.total        = total
        # Shared mutable flag: cancel_flag_ref[0] is True once the user
        # has clicked Cancel. Checked between batches inside the collector
        # so a worker can stop early instead of finishing all 6 batches.
        self.cancel_flag  = cancel_flag_ref
        self.signals      = WorkerSignals()
        self.setAutoDelete(True)

    def _is_cancelled(self) -> bool:
        return bool(self.cancel_flag and self.cancel_flag[0])

    def run(self):
        """Runs in a background thread - do NOT touch UI here"""
        try:
            course_id       = self.course.get('id')
            course_name     = self.course.get('name')
            course_code     = self.course.get('course_code')
            teachers        = self.course.get('teachers', [])

            if not teachers:
                self.signals.error.emit(f"{course_code}: No instructor found")
                self.completed[0] += 1
                self.signals.progress.emit(self.completed[0], self.total)
                return

            instructor      = teachers[0]
            instructor_id   = instructor.get('id')
            instructor_name = instructor.get('display_name')

            data = self.collector.collect_instructor_data(
                str(course_id),
                str(instructor_id),
                self.period_start,
                self.period_end,
                self.period,
                cancel_check=self._is_cancelled
            )

            data['course_code']     = course_code
            data['course_name']     = course_name
            data['instructor_name'] = instructor_name

            self.completed[0] += 1
            self.signals.progress.emit(self.completed[0], self.total)
            self.signals.finished.emit(data)

        except Exception as e:
            self.completed[0] += 1
            self.signals.progress.emit(self.completed[0], self.total)
            course_code = self.course.get('course_code', 'Unknown')
            self.signals.error.emit(f"{course_code}: {e}")
