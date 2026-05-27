"""
Excel Report Generator
Two distinct column structures for current_week vs entire_term reports
"""

from datetime import datetime
from typing import List, Dict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExcelReportGenerator:

    MAROON     = "770000"
    LIGHT_GRAY = "F2F2F2"
    WHITE      = "FFFFFF"

    # Each entry: (header, column_width, data_key)
    WEEK_COLUMNS = [
        ('Course Code',                               18, 'course_code'),
        ('Course Name',                               32, 'course_name'),
        ('Instructor',                                26, 'instructor_name'),
        ('Total Activity Time (Term)',                24, 'total_activity_time'),
        ('Last Login Date (ET)',                      24, 'last_login_date'),
        ('Discussion Replies (This Week)',            24, 'discussion_replies_week'),
        ('Discussion Replies (Term Total)',           24, 'discussion_replies_total'),
        ('Discussion Posts Not Graded >7 Days',       26, 'discussion_not_graded_7days'),
        ('Other Assignments Not Graded >7 Days',      28, 'other_not_graded_7days'),
        ('Announcements (This Week)',                  22, 'announcements_count'),
        ('Instructor Bio Complete',                    22, 'instructor_bio_complete'),
    ]

    TERM_COLUMNS = [
        ('Course Code',                               18, 'course_code'),
        ('Course Name',                               32, 'course_name'),
        ('Instructor',                                26, 'instructor_name'),
        ('Total Activity Time (Term)',                24, 'total_activity_time'),
        ('Last Login Date (ET)',                      24, 'last_login_date'),
        ('Discussion Replies (Term Total)',           24, 'discussion_replies_total'),
        ('Discussion Posts Not Graded >7 Days',       26, 'discussion_not_graded_7days'),
        ('Other Assignments Not Graded >7 Days',      28, 'other_not_graded_7days'),
        ('Announcements (Term Total)',                 22, 'announcements_count'),
        ('Instructor Bio Complete',                    22, 'instructor_bio_complete'),
    ]

    # Keys that should be center-aligned
    CENTER_KEYS = {
        'total_activity_time', 'login_count_week',
        'discussion_posts_week', 'discussion_posts_total',
        'discussion_replies_week', 'discussion_replies_total',
        'discussion_not_graded_4days', 'discussion_not_graded_7days',
        'other_not_graded_4days', 'other_not_graded_7days',
        'announcements_count', 'instructor_bio_complete'
    }

    def generate_report(self, data: List[Dict], output_path: str, period: str = 'current_week') -> str:
        columns = self.WEEK_COLUMNS if period == 'current_week' else self.TERM_COLUMNS

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Instructor Engagement"

        # Column widths
        for col_idx, (_, width, _key) in enumerate(columns, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Styles
        thin         = Side(style='thin')
        border       = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_fill  = PatternFill(start_color=self.MAROON, end_color=self.MAROON, fill_type="solid")
        header_font  = Font(bold=True, color=self.WHITE, size=11)
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        center       = Alignment(horizontal='center')

        # Header row
        ws.row_dimensions[1].height = 50
        for col_idx, (header, _, _key) in enumerate(columns, 1):
            cell           = ws.cell(row=1, column=col_idx)
            cell.value     = header
            cell.fill      = header_fill
            cell.font      = header_font
            cell.alignment = header_align
            cell.border    = border

        # Data rows
        for row_num, record in enumerate(data, 2):
            fill_color = self.LIGHT_GRAY if row_num % 2 == 0 else self.WHITE
            row_fill   = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

            for col_idx, (_header, _width, key) in enumerate(columns, 1):
                cell        = ws.cell(row=row_num, column=col_idx)
                cell.value  = record.get(key, '')
                cell.fill   = row_fill
                cell.border = border
                if key in self.CENTER_KEYS:
                    cell.alignment = center

        ws.freeze_panes = 'A2'
        wb.save(output_path)
        return output_path
