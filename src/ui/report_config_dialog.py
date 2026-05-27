"""
Report Configuration Dialog
Allows users to set filters for generating engagement reports
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QRadioButton, QButtonGroup, QGroupBox,
    QMessageBox, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Optional, Dict, Any


class ReportConfigDialog(QDialog):
    """Dialog for configuring report parameters and filters"""
    
    def __init__(self, available_terms: list, parent=None):
        super().__init__(parent)
        self.available_terms = available_terms
        self.config = None
        
        self.setWindowTitle("Configure Engagement Report")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.setup_ui()
        self.connect_signals()
        self.validate_inputs()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Configure Engagement Report")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "* = Required field\n"
            "At least one of Term or Instructor must be specified"
        )
        instructions.setStyleSheet("color: #C62828; font-weight: bold;")
        layout.addWidget(instructions)
        
        # Filters group
        filters_group = QGroupBox("Report Filters")
        filters_layout = QVBoxLayout(filters_group)
        filters_layout.setSpacing(15)
        
        # Term selector
        term_layout = QVBoxLayout()
        term_label = QLabel("* Term:")
        term_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        term_layout.addWidget(term_label)
        
        self.term_combo = QComboBox()
        self.term_combo.addItem("(Not Selected)", None)
        
        # Add terms sorted by most recent first
        sorted_terms = sorted(
            self.available_terms,
            key=lambda t: t.get('start_at', ''),
            reverse=True
        )
        
        for term in sorted_terms:
            term_name = term.get('name', 'Unknown Term')
            term_id = term.get('id')
            self.term_combo.addItem(term_name, term_id)
        
        term_help = QLabel("Select a specific term, or leave unselected to search all terms")
        term_help.setStyleSheet("color: #666; font-size: 10pt;")
        
        term_layout.addWidget(self.term_combo)
        term_layout.addWidget(term_help)
        filters_layout.addLayout(term_layout)
        
        # Instructor filter
        instructor_layout = QVBoxLayout()
        instructor_label = QLabel("* Instructor:")
        instructor_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        instructor_layout.addWidget(instructor_label)
        
        self.instructor_input = QLineEdit()
        self.instructor_input.setPlaceholderText("Enter instructor last name or partial name...")
        instructor_help = QLabel("Search by last name (e.g., 'Smith', 'Johnson')")
        instructor_help.setStyleSheet("color: #666; font-size: 10pt;")
        
        instructor_layout.addWidget(self.instructor_input)
        instructor_layout.addWidget(instructor_help)
        filters_layout.addLayout(instructor_layout)
        
        # Course prefix filter (optional)
        prefix_layout = QVBoxLayout()
        prefix_label = QLabel("Course Prefix (optional):")
        prefix_label.setFont(QFont("Arial", 11))
        prefix_layout.addWidget(prefix_label)
        
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("e.g., PSY, HUM, COM...")
        self.prefix_input.setMaxLength(10)
        prefix_help = QLabel("Filter by department/subject code")
        prefix_help.setStyleSheet("color: #666; font-size: 10pt;")
        
        prefix_layout.addWidget(self.prefix_input)
        prefix_layout.addWidget(prefix_help)
        filters_layout.addLayout(prefix_layout)
        
        layout.addWidget(filters_group)
        
        # Week range group
        week_group = QGroupBox("Week Range")
        week_layout = QVBoxLayout(week_group)
        
        self.week_button_group = QButtonGroup(self)
        
        self.current_week_radio = QRadioButton("Current Week")
        self.current_week_radio.setChecked(True)
        self.week_button_group.addButton(self.current_week_radio)
        week_layout.addWidget(self.current_week_radio)
        
        # Specific week option
        specific_week_layout = QHBoxLayout()
        self.specific_week_radio = QRadioButton("Specific Week:")
        self.week_button_group.addButton(self.specific_week_radio)
        specific_week_layout.addWidget(self.specific_week_radio)
        
        self.week_combo = QComboBox()
        for i in range(1, 9):
            self.week_combo.addItem(f"Week {i}", i)
        self.week_combo.setEnabled(False)
        specific_week_layout.addWidget(self.week_combo)
        specific_week_layout.addStretch()
        
        week_layout.addLayout(specific_week_layout)
        
        self.entire_term_radio = QRadioButton("Entire Term (All Weeks to Date)")
        self.week_button_group.addButton(self.entire_term_radio)
        week_layout.addWidget(self.entire_term_radio)
        
        layout.addWidget(week_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setDefault(True)
        self.generate_btn.clicked.connect(self.accept_config)
        button_layout.addWidget(self.generate_btn)
        
        layout.addLayout(button_layout)
    
    def connect_signals(self):
        """Connect UI signals"""
        # Enable/disable week combo based on radio selection
        self.specific_week_radio.toggled.connect(
            lambda checked: self.week_combo.setEnabled(checked)
        )
        
        # Validate whenever inputs change
        self.term_combo.currentIndexChanged.connect(self.validate_inputs)
        self.instructor_input.textChanged.connect(self.validate_inputs)
    
    def validate_inputs(self):
        """Validate that at least term or instructor is specified"""
        term_selected = self.term_combo.currentIndex() > 0
        instructor_entered = len(self.instructor_input.text().strip()) > 0
        
        is_valid = term_selected or instructor_entered
        
        self.generate_btn.setEnabled(is_valid)
        
        if not is_valid:
            self.generate_btn.setToolTip(
                "Please select a Term or enter an Instructor name"
            )
        else:
            self.generate_btn.setToolTip("")
    
    def accept_config(self):
        """Validate and accept the configuration"""
        # Double-check validation
        term_selected = self.term_combo.currentIndex() > 0
        instructor_entered = len(self.instructor_input.text().strip()) > 0
        
        if not term_selected and not instructor_entered:
            QMessageBox.warning(
                self,
                "Missing Required Fields",
                "Please select a Term or enter an Instructor name.\n\n"
                "At least one of these fields is required to generate a report."
            )
            return
        
        # Build configuration
        self.config = {
            'term_id': self.term_combo.currentData() if term_selected else None,
            'term_name': self.term_combo.currentText() if term_selected else "All Terms",
            'instructor': self.instructor_input.text().strip() if instructor_entered else None,
            'course_prefix': self.prefix_input.text().strip().upper() or None,
            'week_range': self.get_week_range_config()
        }
        
        self.accept()
    
    def get_week_range_config(self) -> Dict[str, Any]:
        """Get the week range configuration"""
        if self.current_week_radio.isChecked():
            return {'type': 'current_week'}
        elif self.specific_week_radio.isChecked():
            return {
                'type': 'specific_week',
                'week_number': self.week_combo.currentData()
            }
        else:  # entire_term_radio
            return {'type': 'entire_term'}
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get the report configuration"""
        return self.config
