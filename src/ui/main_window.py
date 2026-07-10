"""
Panther Instructor Engagement Reports
Main Application Window
Created by Darby Proctor, PhD. with assistance from Claude AI
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QApplication, QDialog, QLineEdit,
    QComboBox, QRadioButton, QButtonGroup, QGroupBox, QListWidget,
    QFileDialog, QMenuBar, QScrollArea
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QIcon, QDesktopServices, QAction
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
        self.setMinimumSize(800, 600)
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
        # Outer widget holds the scroll area
        outer = QWidget()
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scroll area wraps all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        # Inner widget is what actually gets scrolled
        inner = QWidget()
        scroll.setWidget(inner)
        main = QVBoxLayout(inner)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(20)

        # Menu bar
        self.create_menu_bar()

        main.addWidget(self.create_header())
        main.addWidget(self.create_filters_section())
        main.addWidget(self.create_week_range_section())
        main.addStretch()

        self.generate_btn = QPushButton("Generate Engagement Report")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.generate_report)
        main.addWidget(self.generate_btn)

        # Progress bar (hidden until report generation starts)
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(24)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self.config.secondary_color};
                border-radius: 4px;
                text-align: center;
                font-size: 13px;
            }}
            QProgressBar::chunk {{
                background-color: {self.config.primary_color};
                border-radius: 2px;
            }}
        """)
        main.addWidget(self.progress_bar)

        # Cancel button (hidden until report generation starts)
        self.cancel_btn = QPushButton("Cancel Report")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setMaximumWidth(200)
        self.cancel_btn.clicked.connect(self.cancel_report)
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_row.addWidget(self.cancel_btn)
        cancel_row.addStretch()
        main.addLayout(cancel_row)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.status_label)

        footer = QLabel("Developed by Darby Proctor, Ph.D.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 14px;")
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
        subtitle.setStyleSheet("font-size: 18px;")
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text)
        layout.addStretch()
        return header

    def create_filters_section(self) -> QGroupBox:
        group = QGroupBox("Filters")
        layout = QVBoxLayout()

        # Info banner
        from src.utils.theme import get_palette, is_dark_mode
        p = get_palette(self.config.primary_color, self.config.secondary_color, is_dark_mode())
        info = QLabel("At least one filter must be filled before searching")
        info.setStyleSheet(
            f"color: {p['error_text']}; padding: 8px; "
            f"background-color: {p['error_bg']}; border-radius: 4px; "
            f"font-size: 14px; font-weight: bold;"
        )
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
        # Reverse chronological (most recent first), no future year
        # until it actually arrives
        for y in range(current_year, current_year - 4, -1):
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

        # ── Course list label + select all button ─────────────────────────────
        list_header = QHBoxLayout()
        self.course_list_label = QLabel("Click a course to select it for the report. Click again to deselect. Multiple courses can be selected.")
        self.course_list_label.setWordWrap(True)
        self.course_list_label.setStyleSheet("color: #770000; font-size: 14px; font-style: italic; padding: 4px 0;")
        list_header.addWidget(self.course_list_label)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedWidth(160)
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        list_header.addWidget(self.select_all_btn)
        layout.addLayout(list_header)

        # ── Course list ───────────────────────────────────────────────────────
        self.course_list = QListWidget()
        self.course_list.setMinimumHeight(250)
        self.course_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.course_list.itemSelectionChanged.connect(self.update_select_all_btn)
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

    # ── Menu Bar ──────────────────────────────────────────────────────────────
    def create_menu_bar(self):
        menubar = self.menuBar()

        help_menu = menubar.addMenu("Help")

        version_action = QAction("About Panther Instructor Engagement", self)
        version_action.triggered.connect(self.show_about)
        help_menu.addAction(version_action)

        guide_action = QAction("User Guide", self)
        guide_action.triggered.connect(self.show_user_guide)
        help_menu.addAction(guide_action)

        help_menu.addSeparator()

        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(self.check_for_updates_manual)
        help_menu.addAction(update_action)

        help_menu.addSeparator()

        reset_action = QAction("Reset Canvas Settings", self)
        reset_action.triggered.connect(self.reset_canvas_settings)
        help_menu.addAction(reset_action)

    def reset_canvas_settings(self):
        """Clear stored Canvas URL and API token so they can be re-entered"""
        reply = QMessageBox.question(
            self,
            "Reset Canvas Settings",
            "This will remove your saved Canvas URL and API token.\n\n"
            "Use this if you changed institutions or your API token "
            "expired.\n\n"
            "The application will close. When you reopen it, you will be "
            "prompted to enter your Canvas URL and a new API token.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            for key in ("canvas_url", "canvas_token"):
                try:
                    keyring.delete_password("PantherInstructorEngagement", key)
                except Exception:
                    pass  # entry may not exist
            QMessageBox.information(
                self,
                "Settings Reset",
                "Canvas settings cleared. The application will now close.\n\n"
                "Reopen it to enter your new Canvas URL and API token."
            )
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not reset settings:\n\n{e}")

    def show_about(self):
        """Show about dialog with version number"""
        from src.utils.version_check import get_current_version
        version = get_current_version()

        msg = QMessageBox(self)
        msg.setWindowTitle("About Panther Instructor Engagement")
        msg.setIconPixmap(self.windowIcon().pixmap(64, 64))
        msg.setText(
            f"<b>Panther Instructor Engagement Reports</b><br><br>"
            f"Version {version}<br><br>"
            f"A Canvas LMS tool for monitoring instructor activity<br>"
            f"across online courses.<br><br>"
            f"Developed by Darby Proctor, Ph.D.<br>"
            f"Florida Institute of Technology"
        )
        msg.exec()

    def check_for_updates_manual(self):
        """Manually triggered update check from menu"""
        from src.utils.version_check import check_for_updates, get_current_version
        update = check_for_updates()

        if update:
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                f"A new version is available!\n\n"
                f"Current version:  {update['current']}\n"
                f"Latest version:   {update['latest']}\n\n"
                f"Click Download to get the latest version."
            )
            download_btn = msg.addButton("Download", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == download_btn:
                QDesktopServices.openUrl(QUrl(update['url']))
        else:
            QMessageBox.information(
                self,
                "No Updates Available",
                f"You are running the latest version ({get_current_version()})."
            )

    def show_user_guide(self):
        """Show scrollable user guide dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("User Guide")
        dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)

        guide_text = QLabel(self._get_user_guide_text())
        guide_text.setWordWrap(True)
        guide_text.setTextFormat(Qt.TextFormat.RichText)
        guide_text.setFont(QFont("Arial", 12))
        guide_text.setAlignment(Qt.AlignmentFlag.AlignTop)

        content_layout.addWidget(guide_text)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _get_user_guide_text(self) -> str:
        return """
<h2 style='color:#770000;'>Panther Instructor Engagement Reports — User Guide</h2>

<h3 style='color:#770000;'>Overview</h3>
<p>This application connects to your Canvas LMS account and generates Excel reports
showing instructor engagement activity for online courses. Reports can be generated
for the current week or the entire term to date.</p>

<h3 style='color:#770000;'>First-Time Setup</h3>
<p>On first launch you will be prompted for:</p>
<ul>
<li><b>Canvas URL</b> — your institution's Canvas address (e.g. https://fit.instructure.com)</li>
<li><b>API Token</b> — generated in Canvas under Account → Settings → New Access Token</li>
</ul>
<p>Your credentials are stored securely in your system keychain and will not need
to be entered again.</p>

<h3 style='color:#770000;'>Searching for Courses</h3>
<p>Use the <b>Filters</b> section to find courses. At least one filter must be filled
before clicking Search.</p>
<ul>
<li><b>Account</b> — filter to a specific admin account or search all accounts</li>
<li><b>Course Code</b> — type part of a course code (e.g. PSY, PSY1411)</li>
<li><b>Instructor</b> — type part of an instructor's last name</li>
<li><b>Year</b> — select the academic year</li>
<li><b>Semester</b> — select Fall, Spring, or Summer</li>
<li><b>Term</b> — select 8-Week Term 1 or 8-Week Term 2 for online courses</li>
</ul>
<p>Click <b>🔍 Search</b> to run the search. Results appear in the course list below the filters.
Searches may take a moment depending on the number of courses in your accounts.</p>

<h3 style='color:#770000;'>Selecting Courses</h3>
<p>Click a course in the list to select it. Click again to deselect.
Multiple courses can be selected at the same time — hold nothing special,
just click each course you want to include.</p>
<p>Courses are sorted alphabetically by course prefix and then numerically by course number.</p>

<h3 style='color:#770000;'>Report Period</h3>
<p>Choose the time period for the report:</p>
<ul>
<li><b>Current Week</b> — activity from the current Monday–Sunday week of the term</li>
<li><b>Entire Term (All Weeks to Date)</b> — cumulative activity since the term started</li>
</ul>
<p>If a course's term has already ended and you select Current Week, the report will
automatically use Entire Term for that course and note this in the success message.</p>

<h3 style='color:#770000;'>Generating the Report</h3>
<p>After selecting courses and a report period, click <b>Generate Engagement Report</b>.
You will be prompted to choose where to save the Excel file. The app remembers
your last save location.</p>
<p>Data collection may take a minute or two depending on how many courses are selected
and how many discussion topics each course has.</p>

<h3 style='color:#770000;'>Report Columns</h3>
<p><b>Current Week Report:</b></p>
<ul>
<li><b>Course Code / Course Name / Instructor</b> — course identification</li>
<li><b>Total Activity Time (Term)</b> — total time the instructor has been active in Canvas for this course since the term started</li>
<li><b>Last Login Date (ET)</b> — the last time the instructor was active in this course, shown in Eastern Time</li>
<li><b>Discussion Replies (This Week)</b> — number of discussion replies posted by the instructor this week</li>
<li><b>Discussion Replies (Term Total)</b> — total discussion replies posted by the instructor since the term started</li>
<li><b>Discussion Posts Not Graded >7 Days</b> — discussion board assignments submitted by students more than 7 days ago that have not been graded</li>
<li><b>Other Assignments Not Graded >7 Days</b> — non-discussion assignments submitted more than 7 days ago that have not been graded</li>
<li><b>Announcements (This Week)</b> — number of announcements posted by the instructor this week</li>
<li><b>Instructor Bio Complete</b> — Y or N indicating whether the instructor has completed their Canvas profile bio</li>
</ul>
<p><b>Entire Term Report</b> contains the same columns except it omits the weekly
discussion replies column and shows term totals only.</p>

<h3 style='color:#770000;'>Tips</h3>
<ul>
<li>Use the Term filter (8-Week Term 1 / 8-Week Term 2) to separate online sections
that run within the same semester</li>
<li>You can select courses from different terms in the same report run</li>
<li>The report file is named with a timestamp so each run creates a new file</li>
</ul>

<h3 style='color:#770000;'>Updates</h3>
<p>The application checks for updates automatically when it launches. You can also
check manually at any time using <b>About → Check for Updates</b>. When an update
is available you will be given a direct link to download the latest version.</p>

<p style='color:#888; margin-top:30px;'><i>Developed by Darby Proctor, Ph.D. — Florida Institute of Technology</i></p>
"""

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

    def toggle_select_all(self):
        """Select all or deselect all courses in the list"""
        if self.course_list.selectedItems():
            self.course_list.clearSelection()
        else:
            self.course_list.selectAll()

    def update_select_all_btn(self):
        """Update Select All button label based on current selection"""
        if self.course_list.selectedItems():
            self.select_all_btn.setText("Deselect All")
        else:
            self.select_all_btn.setText("Select All")

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
                self.select_all_btn.setEnabled(False)
            else:
                self.generate_btn.setEnabled(True)
                self.select_all_btn.setEnabled(True)

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
        timestamp    = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f'Instructor_Engagement_Report_{timestamp}.xlsx'

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
            return

        try:
            keyring.set_password(
                "PantherInstructorEngagement",
                "last_save_folder",
                str(Path(save_path).parent)
            )
        except:
            pass

        # ── Week range ────────────────────────────────────────────────────────
        week_type = 'current_week' if self.current_week_radio.isChecked() else 'entire_term'

        # ── Resolve date ranges per course ────────────────────────────────────
        from src.utils.week_utils import get_current_week_range, get_entire_term_range

        courses_with_dates = []
        fallback_courses   = []

        for course in selected_courses:
            term_start = course.get('term', {}).get('start_at')
            if not term_start:
                continue

            term_start_date  = datetime.fromisoformat(term_start.replace('Z', '+00:00')).replace(tzinfo=None)
            effective_period = week_type

            if week_type == 'current_week':
                try:
                    period_start, period_end = get_current_week_range(term_start_date)
                except ValueError:
                    effective_period = 'entire_term'
                    period_start, period_end = get_entire_term_range(term_start_date)
                    fallback_courses.append(course.get('course_code', ''))
            else:
                period_start, period_end = get_entire_term_range(term_start_date)

            courses_with_dates.append((course, period_start, period_end, effective_period))

        if not courses_with_dates:
            QMessageBox.warning(self, "No Data", "No courses had valid term dates.")
            return

        # ── Set up UI for progress ────────────────────────────────────────────
        total = len(courses_with_dates)
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Collecting data: 0 of {total} courses")
        self.cancel_btn.setVisible(True)
        self._report_cancelled = False
        self.status_label.setText("Starting data collection...")
        QApplication.processEvents()

        # ── Thread-safe result storage ────────────────────────────────────────
        self._report_results   = []
        self._report_errors    = []
        self._report_completed = [0]
        self._report_total     = total
        self._report_save_path = save_path
        self._report_week_type = week_type
        self._report_fallbacks = fallback_courses
        # Shared mutable flag passed into every worker so they can check
        # cancellation cooperatively between batches/topics.
        self._report_cancel_flag = [False]

        # ── Launch workers ────────────────────────────────────────────────────
        from PyQt6.QtCore import QThreadPool
        from src.utils.course_worker import CourseWorker
        from src.utils.engagement_collector import EngagementCollector

        # Create collector once and share across all workers
        # (avoids import issues inside threads)
        collector = EngagementCollector(self.api_client)

        pool = QThreadPool.globalInstance()
        pool.setMaxThreadCount(4)

        for course, period_start, period_end, effective_period in courses_with_dates:
            worker = CourseWorker(
                collector       = collector,
                course          = course,
                period_start    = period_start,
                period_end      = period_end,
                period          = effective_period,
                completed_ref   = self._report_completed,
                total           = total,
                cancel_flag_ref = self._report_cancel_flag
            )
            worker.signals.finished.connect(self._on_course_complete)
            worker.signals.error.connect(self._on_course_error)
            worker.signals.progress.connect(self._on_progress_update)
            pool.start(worker)

    def cancel_report(self):
        """
        Cancel report generation. The cancellation flag is set FIRST,
        before showing any dialog, so that no worker signal arriving
        while the confirmation dialog is open can slip past _check_complete
        and finalize the report behind the user's back. The confirmation
        dialog only decides whether the partial results get saved.
        """
        from PyQt6.QtCore import QThreadPool, QTimer

        # Set BOTH flags immediately, before any modal dialog runs.
        # _report_cancel_flag is shared with running workers so they can
        # stop early (checked between batches/topics in the collector).
        # _report_cancelled blocks _check_complete from auto-finalizing.
        self._report_cancelled = True
        self._report_cancel_flag[0] = True

        pool = QThreadPool.globalInstance()
        pool.clear()  # drop any queued-but-not-yet-started workers

        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling...")

        collected = len(self._report_results)
        reply = QMessageBox.question(
            self,
            "Cancel Report",
            f"Data has been collected for {collected} of {self._report_total} "
            f"course(s) so far.\n\n"
            f"Save a report with the courses collected so far?\n\n"
            f"Yes = save partial report\n"
            f"No = discard and stop",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        self._save_partial = (reply == QMessageBox.StandardButton.Yes)

        self.status_label.setText("Cancelling - waiting for in-progress courses to finish...")

        # Poll until active workers drain, then finalize or discard.
        # Workers should now stop quickly since they check the cancel
        # flag between batches/topics rather than running to completion.
        self._cancel_timer = QTimer(self)
        self._cancel_timer.setInterval(300)
        def _check_drained():
            if pool.activeThreadCount() == 0:
                self._cancel_timer.stop()
                if self._save_partial and self._report_results:
                    self._finalize_report(cancelled=True)
                else:
                    self.generate_btn.setEnabled(True)
                    self.progress_bar.setVisible(False)
                    self.cancel_btn.setVisible(False)
                    self.cancel_btn.setEnabled(True)
                    self.status_label.setText("Report cancelled")
        self._cancel_timer.timeout.connect(_check_drained)
        self._cancel_timer.start()

    def _on_progress_update(self, completed: int, total: int):
        """Update progress bar as each course finishes"""
        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f"Collecting data: {completed} of {total} courses")
        self.status_label.setText(f"Collecting data: {completed} of {total} courses complete...")
        # Don't finalize here - _check_complete runs after data is appended

    def _on_course_complete(self, data: dict):
        """Called when a course worker finishes successfully"""
        self._report_results.append(data)
        self._check_complete()

    def _on_course_error(self, error_msg: str):
        """Called when a course worker fails"""
        self._report_errors.append(error_msg)
        self._check_complete()

    def _check_complete(self):
        """Finalize only when all workers have reported back"""
        if getattr(self, '_report_cancelled', False):
            return  # cancel path finalizes via its own timer
        total_received = len(self._report_results) + len(self._report_errors)
        if total_received >= self._report_total:
            self._finalize_report()

    def _finalize_report(self, cancelled: bool = False):
        """Generate Excel file once all workers are done"""
        from src.utils.excel_generator import ExcelReportGenerator

        save_path = self._report_save_path
        week_type = self._report_week_type
        all_data  = self._report_results
        fallbacks = self._report_fallbacks
        errors    = self._report_errors

        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)

        # Detect expired/invalid API token across worker errors
        auth_failures = [e for e in errors
                         if 'Invalid API token' in e or '401' in e]
        if auth_failures:
            QMessageBox.warning(
                self,
                "Canvas Authentication Problem",
                "Some or all courses failed because your Canvas API token "
                "appears to be invalid or expired.\n\n"
                "Use Help → Reset Canvas Settings to enter a new token."
            )

        if not all_data:
            if not auth_failures:
                QMessageBox.warning(self, "No Data", "No engagement data could be collected.")
            self.status_label.setText("⚠ No data collected")
            return

        excel_period = week_type
        if fallbacks and len(fallbacks) == len(all_data):
            excel_period = 'entire_term'

        self.status_label.setText("Generating Excel report...")
        QApplication.processEvents()

        try:
            import re
            def sort_key(d):
                code = d.get('course_code', '')
                m = re.match(r'^([A-Za-z]*)(\d*)', code)
                if m:
                    return (m.group(1).upper(), int(m.group(2)) if m.group(2) else 0)
                return ('', 0)

            all_data.sort(key=sort_key)

            generator = ExcelReportGenerator()
            generator.generate_report(all_data, save_path, excel_period)

            fallback_note = ''
            if fallbacks:
                fallback_note = (
                    f"\n\n⚠ Note: {len(fallbacks)} course(s) used Entire Term instead of Current Week:\n"
                    + '\n'.join(f"  • {c}" for c in fallbacks)
                )

            error_note = ''
            if errors:
                error_note = (
                    f"\n\n⚠ {len(errors)} course(s) failed to collect:\n"
                    + '\n'.join(f"  • {e}" for e in errors)
                )

            cancel_note = ''
            if cancelled:
                cancel_note = (
                    f"\n\n⚠ Report was cancelled - contains "
                    f"{len(all_data)} of {self._report_total} selected course(s)."
                )

            QMessageBox.information(
                self, "Report Generated",
                f"Report saved successfully!\n\n"
                f"Courses: {len(all_data)}\n"
                f"File: {Path(save_path).name}\n"
                f"Location: {Path(save_path).parent}"
                + cancel_note + fallback_note + error_note
            )
            self.status_label.setText(f"✓ Report saved: {Path(save_path).name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating Excel file:\n\n{e}")
            self.status_label.setText(f"✗ Error: {e}")

    # ── Styles ────────────────────────────────────────────────────────────────
    def apply_styles(self):
        from src.utils.theme import apply_theme, is_dark_mode
        self.setStyleSheet(apply_theme(
            primary=self.config.primary_color,
            secondary=self.config.secondary_color,
            dark_mode=is_dark_mode()
        ))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()

    # Live-update styling if the user switches OS light/dark mode
    # while the app is running
    app.styleHints().colorSchemeChanged.connect(window.apply_styles)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()