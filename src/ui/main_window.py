"""
Panther Instructor Engagement Reports
Main Application Window
Created by Darby Proctor, PhD. with assistance from Claude AI
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QApplication, QDialog, QLineEdit,
    QComboBox, QRadioButton, QButtonGroup, QGroupBox, QListWidget,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
import sys
import os
from pathlib import Path
import keyring
from datetime import datetime

from src.utils.config import get_config
from src.api.browser_auth import SimpleBrowserAuthDialog, TokenBasedCanvasClient


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.canvas_client = None
        self.api_client = None
        self.filtered_courses = []
        self.admin_accounts = []          # list of {id, name} dicts

        self.setWindowTitle("Panther Instructor Engagement Reports")
        self.setMinimumSize(1000, 900)
        self.resize(1200, 1000)

        # Set window icon
        icon_path = Path(__file__).parent.parent.parent / 'assets' / 'icon.png'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        if not self.authenticate():
            sys.exit(0)

        self.setup_ui()
        self.apply_styles()
        self.load_admin_accounts()

        # Check for updates in background after UI is ready
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, self.check_for_updates)        # populate account dropdown after UI is built

    # ── Authentication ────────────────────────────────────────────────────────
    def authenticate(self) -> bool:
        try:
            canvas_url = keyring.get_password("PantherInstructorEngagement", "canvas_url")
        except:
            canvas_url = None

        if not canvas_url:
            canvas_url = self.prompt_for_canvas_url()
            if not canvas_url:
                return False
            try:
                keyring.set_password("PantherInstructorEngagement", "canvas_url", canvas_url)
            except:
                pass

        try:
            saved_token = keyring.get_password("PantherInstructorEngagement", "canvas_token")
        except:
            saved_token = None

        if saved_token:
            client = TokenBasedCanvasClient(canvas_url, saved_token)
            if client.test_connection():
                self.canvas_client = client
                from src.api.canvas_client import CanvasAPIClient
                self.api_client = CanvasAPIClient(canvas_url, saved_token)
                return True
            else:
                try:
                    keyring.delete_password("PantherInstructorEngagement", "canvas_token")
                except:
                    pass

        auth_dialog = SimpleBrowserAuthDialog(canvas_url, self)
        if auth_dialog.exec() == QDialog.DialogCode.Accepted:
            token = auth_dialog.get_token()
            if token:
                client = TokenBasedCanvasClient(canvas_url, token)
                if client.test_connection():
                    try:
                        keyring.set_password("PantherInstructorEngagement", "canvas_token", token)
                    except:
                        pass
                    self.canvas_client = client
                    from src.api.canvas_client import CanvasAPIClient
                    self.api_client = CanvasAPIClient(canvas_url, token)
                    return True
        return False

    def prompt_for_canvas_url(self) -> str:
        dialog = QDialog(self)
        dialog.setWindowTitle("Canvas URL Setup")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        instructions = QLabel(
            "Welcome to Panther Instructor Engagement Reports!\n\n"
            "Please enter your institution's Canvas URL.\n"
            "Example: https://fit.instructure.com"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Canvas URL:"))
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://")
        url_layout.addWidget(url_input)
        layout.addLayout(url_layout)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Continue")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.setDefault(True)
        url_input.returnPressed.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = url_input.text().strip()
            if url and (url.startswith('http://') or url.startswith('https://')):
                return url.rstrip('/')
            else:
                QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL")
                return self.prompt_for_canvas_url()
        return ""

    # ── UI Setup ──────────────────────────────────────────────────────────────
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(20)

        main.addWidget(self.create_header())
        main.addWidget(self.create_filters_section())
        main.addWidget(self.create_week_range_section())
        main.addStretch()

        self.generate_btn = QPushButton("Generate Engagement Report")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.generate_report)
        main.addWidget(self.generate_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.status_label)

        footer = QLabel("Developed by Darby Proctor, Ph.D.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #666; font-size: 14px;")
        main.addWidget(footer)

    def create_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        logo = QLabel("🐾")
        logo.setStyleSheet("font-size: 48px;")
        layout.addWidget(logo)
        layout.addSpacing(20)

        text = QVBoxLayout()
        title = QLabel("Panther Instructor Engagement")
        title.setStyleSheet(f"color: {self.config.primary_color}; font-size: 32px; font-weight: bold;")
        subtitle = QLabel("Monitor Instructor Activity and Engagement")
        subtitle.setStyleSheet("color: #000000; font-size: 18px;")
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text)
        layout.addStretch()
        return header

    def create_filters_section(self) -> QGroupBox:
        group = QGroupBox("Filters")
        layout = QVBoxLayout()

        # Info banner
        info = QLabel("At least one filter must be filled before searching")
        info.setStyleSheet("color: #C62828; padding: 8px; background-color: #FFEBEE; border-radius: 4px; font-size: 14px; font-weight: bold;")
        layout.addWidget(info)

        # ── Row 0: Account filter ─────────────────────────────────────────────
        row0 = QHBoxLayout()
        row0.addWidget(QLabel("Account:"))
        self.account_filter = QComboBox()
        self.account_filter.addItem("Loading accounts...", None)
        self.account_filter.setEnabled(False)
        row0.addWidget(self.account_filter, stretch=1)
        row0.addStretch()
        layout.addLayout(row0)

        # ── Row 1: Course Code + Instructor ───────────────────────────────────
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Course Code:"))
        self.course_code_filter = QLineEdit()
        self.course_code_filter.setPlaceholderText("e.g., PSY1411")
        self.course_code_filter.returnPressed.connect(self.search_courses)
        row1.addWidget(self.course_code_filter)
        row1.addSpacing(20)
        row1.addWidget(QLabel("Instructor:"))
        self.instructor_filter = QLineEdit()
        self.instructor_filter.setPlaceholderText("Last name")
        self.instructor_filter.returnPressed.connect(self.search_courses)
        row1.addWidget(self.instructor_filter)
        layout.addLayout(row1)

        # ── Row 2: Year + Semester + Search ───────────────────────────────────
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Year:"))
        self.year_filter = QComboBox()
        self.year_filter.addItem("")
        current_year = datetime.now().year
        for y in range(current_year - 3, current_year + 2):
            self.year_filter.addItem(str(y))
        row2.addWidget(self.year_filter)

        row2.addWidget(QLabel("Semester:"))
        self.semester_filter = QComboBox()
        self.semester_filter.addItems(["", "Fall", "Spring", "Summer"])
        row2.addWidget(self.semester_filter)

        row2.addWidget(QLabel("Term:"))
        self.term_filter = QComboBox()
        self.term_filter.addItems(["", "8-Week Term 1", "8-Week Term 2"])
        row2.addWidget(self.term_filter)

        row2.addStretch()
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.search_courses)
        row2.addWidget(self.search_btn)
        layout.addLayout(row2)

        # ── Course list label ─────────────────────────────────────────────────
        self.course_list_label = QLabel("Click a course to select it for the report. Click again to deselect. Multiple courses can be selected.")
        self.course_list_label.setWordWrap(True)
        self.course_list_label.setStyleSheet("color: #770000; font-size: 14px; font-style: italic; padding: 4px 0;")
        layout.addWidget(self.course_list_label)

        # ── Course list ───────────────────────────────────────────────────────
        self.course_list = QListWidget()
        self.course_list.setMinimumHeight(250)
        self.course_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.course_list)

        group.setLayout(layout)
        return group

    def create_week_range_section(self) -> QGroupBox:
        group = QGroupBox("Report Period")
        layout = QHBoxLayout()

        self.week_button_group = QButtonGroup(self)

        self.current_week_radio = QRadioButton("Current Week")
        self.current_week_radio.setChecked(True)
        self.week_button_group.addButton(self.current_week_radio)
        layout.addWidget(self.current_week_radio)

        self.entire_term_radio = QRadioButton("Entire Term (All Weeks to Date)")
        self.week_button_group.addButton(self.entire_term_radio)
        layout.addWidget(self.entire_term_radio)

        layout.addStretch()
        group.setLayout(layout)
        return group

    # ── Update check ─────────────────────────────────────────────────────────
    def check_for_updates(self):
        """Check GitHub for a newer version and notify user if found"""
        try:
            from src.utils.version_check import check_for_updates
            update = check_for_updates()

            if update:
                from PyQt6.QtWidgets import QMessageBox
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl

                msg = QMessageBox(self)
                msg.setWindowTitle("Update Available")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(
                    f"A new version of Panther Instructor Engagement is available!\n\n"
                    f"Current version:  {update['current']}\n"
                    f"Latest version:   {update['latest']}\n\n"
                    f"Click Download to get the latest version."
                )
                download_btn = msg.addButton("Download", QMessageBox.ButtonRole.AcceptRole)
                msg.addButton("Remind Me Later", QMessageBox.ButtonRole.RejectRole)

                msg.exec()

                if msg.clickedButton() == download_btn:
                    QDesktopServices.openUrl(QUrl(update['url']))

        except Exception:
            pass  # Never crash the app over an update check

    # ── Account loading ───────────────────────────────────────────────────────
    def load_admin_accounts(self):
        """Load admin accounts and populate dropdown after UI is ready"""
        try:
            accounts = self.api_client.get_accounts()
            self.admin_accounts = accounts

            self.account_filter.clear()
            self.account_filter.addItem("All Accounts", None)

            for acc in accounts:
                self.account_filter.addItem(acc.get('name', 'Unknown'), acc.get('id'))

            self.account_filter.setEnabled(True)
            self.status_label.setText(f"✓ Loaded {len(accounts)} admin account(s)")
        except Exception as e:
            self.account_filter.clear()
            self.account_filter.addItem("Error loading accounts", None)
            self.status_label.setText(f"✗ Could not load accounts: {e}")

    # ── Search ────────────────────────────────────────────────────────────────
    def search_courses(self):
        if not self.canvas_client:
            QMessageBox.warning(self, "Not Connected", "Please log in first.")
            return

        course_code  = self.course_code_filter.text().strip()
        instructor   = self.instructor_filter.text().strip()
        year         = self.year_filter.currentText().strip()
        semester     = self.semester_filter.currentText().strip()
        term_filter  = self.term_filter.currentText().strip()

        if not course_code and not instructor and not year and not semester and not term_filter:
            QMessageBox.information(
                self, "Filter Required",
                "Please enter at least one filter:\n\n• Course Code\n• Instructor\n• Year\n• Semester"
            )
            return

        # Which account(s)?
        selected_account_id   = self.account_filter.currentData()
        selected_account_name = self.account_filter.currentText()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        original_text = self.search_btn.text()
        self.search_btn.setText("Searching...")
        self.search_btn.setEnabled(False)

        if selected_account_id:
            self.status_label.setText(f"Searching courses in {selected_account_name}...")
        else:
            self.status_label.setText("Searching courses across all admin accounts...")
        QApplication.processEvents()

        try:
            # Fetch courses from selected account or all accounts
            if selected_account_id:
                courses = self.api_client.get_courses_for_account(str(selected_account_id))
            else:
                courses = self.api_client.get_all_courses_admin()

            if not courses:
                QApplication.restoreOverrideCursor()
                self.search_btn.setText(original_text)
                self.search_btn.setEnabled(True)
                QMessageBox.information(self, "No Courses Found", "No courses found.")
                self.status_label.setText("")
                return

            self.status_label.setText("Filtering results...")
            QApplication.processEvents()

            self.filtered_courses = []
            for course in courses:
                course_code_val = course.get('course_code', '')
                term            = course.get('term', {})
                term_name       = term.get('name', '') if isinstance(term, dict) else ''
                teachers        = course.get('teachers', [])
                teacher_names   = [t.get('display_name', '') for t in teachers] if teachers else []

                if course_code and course_code.upper() not in course_code_val.upper():
                    continue
                if instructor and not any(instructor.upper() in n.upper() for n in teacher_names):
                    continue
                if year and year not in term_name:
                    continue
                if semester and semester not in term_name:
                    continue
                if term_filter and term_filter not in term_name:
                    continue

                self.filtered_courses.append(course)

            QApplication.restoreOverrideCursor()
            self.search_btn.setText(original_text)
            self.search_btn.setEnabled(True)

            self.status_label.setText("Populating course list...")
            QApplication.processEvents()

            # Sort by course code prefix then numerically
            def course_sort_key(course):
                code = course.get('course_code', '')
                # Split into alpha prefix and numeric part e.g. "PSY1411" -> ("PSY", 1411)
                import re
                match = re.match(r'^([A-Za-z]*)(\d*)', code)
                if match:
                    prefix = match.group(1).upper()
                    number = int(match.group(2)) if match.group(2) else 0
                    return (prefix, number, code)
                return ('', 0, code)

            self.filtered_courses.sort(key=course_sort_key)

            self.course_list.clear()
            for course in self.filtered_courses:
                course_name     = course.get('name', 'Unnamed Course')
                term            = course.get('term', {})
                term_name       = term.get('name', 'No Term') if isinstance(term, dict) else 'No Term'
                course_code_val = course.get('course_code', '')
                teachers        = course.get('teachers', [])
                teacher_names   = ', '.join([t.get('display_name', '') for t in teachers]) if teachers else 'No instructor'

                import re
                # Canvas names look like:
                # "PSY1411: Intro to Psychology, Spring 2026 (8-Week Term 1), Sect. 101"
                # We want just: "PSY1411: Intro to Psychology"
                # Strip everything from the first ", Fall/Spring/Summer/[4-digit year]" onwards
                clean_name = re.sub(
                    r',\s*(Fall|Spring|Summer|\d{4}).*$',
                    '',
                    course_name,
                    flags=re.IGNORECASE
                ).strip()

                # Fallback: if nothing was stripped, try stripping from Sect.
                if clean_name == course_name:
                    clean_name = re.sub(r',?\s*Sect\.\s*\d+.*$', '', course_name, flags=re.IGNORECASE).strip()

                display = f"{clean_name} ({term_name}) - {teacher_names}"
                self.course_list.addItem(display)

            count = len(self.filtered_courses)
            self.status_label.setText(f"✓ Found {count} course(s) matching your filters")

            if count == 0:
                QMessageBox.information(self, "No Matches", "No courses matched your filters.")
                self.generate_btn.setEnabled(False)
            else:
                self.generate_btn.setEnabled(True)

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.search_btn.setText(original_text)
            self.search_btn.setEnabled(True)
            self.status_label.setText(f"✗ Error: {e}")
            QMessageBox.critical(self, "Error", f"Error:\n\n{e}")

    # ── Generate Report ───────────────────────────────────────────────────────
    def generate_report(self):
        if not self.filtered_courses:
            QMessageBox.warning(self, "No Courses", "Search for courses first.")
            return

        selected_indices = [item.row() for item in self.course_list.selectedIndexes()]
        if not selected_indices:
            QMessageBox.warning(self, "No Selection", "Please select at least one course from the list.")
            return

        selected_courses = [self.filtered_courses[i] for i in selected_indices]

        # ── Ask where to save ─────────────────────────────────────────────────
        timestamp     = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name  = f'Instructor_Engagement_Report_{timestamp}.xlsx'

        # Recall last save folder from keyring
        try:
            last_folder = keyring.get_password("PantherInstructorEngagement", "last_save_folder")
        except:
            last_folder = None
        default_dir = last_folder or os.path.expanduser('~/Documents')

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Engagement Report",
            os.path.join(default_dir, default_name),
            "Excel Files (*.xlsx)"
        )

        if not save_path:
            return          # user cancelled

        # Remember the folder for next time
        try:
            keyring.set_password(
                "PantherInstructorEngagement",
                "last_save_folder",
                str(Path(save_path).parent)
            )
        except:
            pass

        # ── Week range ────────────────────────────────────────────────────────
        if self.current_week_radio.isChecked():
            week_type = 'current_week'
        else:
            week_type = 'entire_term'

        # ── Collect data ──────────────────────────────────────────────────────
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.status_label.setText("Collecting engagement data from Canvas...")
        QApplication.processEvents()

        try:
            from src.utils.engagement_collector import EngagementCollector
            from src.utils.week_utils import get_current_week_range, get_entire_term_range

            collector = EngagementCollector(self.api_client)
            all_data  = []

            for course in selected_courses:
                course_id   = course.get('id')
                course_name = course.get('name')
                course_code = course.get('course_code')

                term       = course.get('term', {})
                term_start = term.get('start_at')

                if not term_start:
                    continue

                term_start_date = datetime.fromisoformat(term_start.replace('Z', '+00:00')).replace(tzinfo=None)

                # Determine period - fall back to entire_term if term has ended
                effective_period = week_type
                if week_type == 'current_week':
                    try:
                        week_start, week_end = get_current_week_range(term_start_date)
                    except ValueError as e:
                        # Term has ended or not started - fall back to entire term
                        effective_period = 'entire_term'
                        week_start, week_end = get_entire_term_range(term_start_date)
                        fallback_courses = getattr(self, '_fallback_courses', [])
                        fallback_courses.append(course_code)
                        self._fallback_courses = fallback_courses
                else:
                    week_start, week_end = get_entire_term_range(term_start_date)

                teachers = course.get('teachers', [])
                if not teachers:
                    continue

                instructor      = teachers[0]
                instructor_id   = instructor.get('id')
                instructor_name = instructor.get('display_name')

                self.status_label.setText(f"Collecting data for {course_code} – {instructor_name}...")
                QApplication.processEvents()

                data = collector.collect_instructor_data(
                    str(course_id), str(instructor_id), week_start, week_end, effective_period
                )
                data['course_code']      = course_code
                data['course_name']      = course_name
                data['instructor_name']  = instructor_name
                all_data.append(data)

            QApplication.restoreOverrideCursor()

            if all_data:
                from src.utils.excel_generator import ExcelReportGenerator
                self.status_label.setText("Generating Excel report...")
                QApplication.processEvents()

                # Use the user's chosen period for the Excel structure.
                # If ALL courses fell back, use entire_term structure.
                fallback_courses = getattr(self, '_fallback_courses', [])
                excel_period = week_type
                if fallback_courses and len(fallback_courses) == len(all_data):
                    excel_period = 'entire_term'
                self._fallback_courses = []  # reset for next run

                generator = ExcelReportGenerator()
                generator.generate_report(all_data, save_path, excel_period)

                # Build notice about any fallbacks
                fallback_note = ''
                if fallback_courses:
                    fallback_note = (
                        f"\n\n⚠ Note: {len(fallback_courses)} course(s) had concluded terms "
                        f"and were reported using Entire Term instead of Current Week:\n"
                        + '\n'.join(f"  • {c}" for c in fallback_courses)
                    )

                QMessageBox.information(
                    self, "Report Generated",
                    f"Report saved successfully!\n\n"
                    f"Courses: {len(all_data)}\n"
                    f"File: {Path(save_path).name}\n"
                    f"Location: {Path(save_path).parent}"
                    + fallback_note
                )
                self.status_label.setText(f"✓ Report saved: {Path(save_path).name}")
            else:
                QMessageBox.warning(self, "No Data", "No engagement data could be collected.")
                self.status_label.setText("⚠ No data collected")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error collecting data:\n\n{e}")
            self.status_label.setText(f"✗ Error: {e}")

    # ── Styles ────────────────────────────────────────────────────────────────
    def apply_styles(self):
        primary   = self.config.primary_color
        secondary = self.config.secondary_color

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: white; }}
            QLabel {{ color: #333333; font-size: 16px; }}
            QGroupBox {{
                font-weight: bold; font-size: 17px;
                border: 2px solid {secondary}; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }}
            QGroupBox::title {{
                color: {primary}; subcontrol-origin: margin;
                left: 10px; padding: 0 5px;
            }}
            QPushButton {{
                background-color: {primary}; color: white;
                border: none; padding: 12px 24px;
                border-radius: 4px; font-weight: bold; font-size: 16px;
            }}
            QPushButton:hover {{ background-color: #5a0000; }}
            QPushButton:disabled {{ background-color: #CCCCCC; color: #666666; }}
            QLineEdit {{
                padding-left: 12px; padding-right: 12px;
                padding-top: 8px; padding-bottom: 8px;
                border: 2px solid {secondary}; border-radius: 4px;
                font-size: 16px; min-height: 25px;
            }}
            QLineEdit:focus {{ border-color: {primary}; }}
            QComboBox {{
                padding-left: 12px; padding-right: 30px;
                padding-top: 8px; padding-bottom: 8px;
                border: 2px solid {secondary}; border-radius: 4px;
                font-size: 16px; min-height: 25px;
            }}
            QComboBox:focus {{ border-color: {primary}; }}
            QComboBox QAbstractItemView {{
                border: 2px solid {secondary};
                selection-background-color: {primary};
                selection-color: white; font-size: 16px;
            }}
            QListWidget {{
                border: 2px solid {secondary}; border-radius: 4px;
                font-size: 16px; padding: 5px;
            }}
            QListWidget::item {{ padding: 2px; }}
            QListWidget::item:selected {{
                background-color: {primary}; color: white;
            }}
            QRadioButton {{ font-size: 16px; }}
        """)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
