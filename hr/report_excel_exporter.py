import os
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from hr.report_db import query_report_by_date, query_report_by_employee


def _style_sheet(ws):
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="CCCCCC")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)

    for row in ws.iter_rows():
        for cell in row:
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            cell.alignment = Alignment(vertical="center")

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)

        for cell in col:
            max_len = max(max_len, len(str(cell.value or "")))

        ws.column_dimensions[col_letter].width = min(max_len + 4, 45)


def export_total_excel(from_date: str, to_date: str, save_path: str):
    rows = query_report_by_date(from_date, to_date)

    wb = Workbook()
    ws = wb.active
    ws.title = "Bao cao tong the"

    headers = [
        "Ngày",
        "Mã đơn",
        "Mã NV",
        "Tên nhân viên",
        "Bộ phận",
        "Camera",
        "Tên video",
        "Thời gian bắt đầu",
        "Thời gian kết thúc",
        "Độ dài (giây)",
        "Dung lượng (MB)",
        "Đường dẫn video",
    ]

    ws.append(headers)

    for r in rows:
        ws.append([
            r.get("date", ""),
            r.get("order_code", ""),
            r.get("employee_id", ""),
            r.get("employee_name", ""),
            r.get("department", ""),
            r.get("camera_name", ""),
            r.get("video_name", ""),
            r.get("start_time", ""),
            r.get("end_time", ""),
            r.get("duration_sec", 0),
            r.get("file_size_mb", 0),
            r.get("video_path", ""),
        ])

    _style_sheet(ws)

    wb.save(save_path)
    return save_path


def export_employee_excel(from_date: str, to_date: str, save_path: str):
    rows = query_report_by_employee(from_date, to_date)

    wb = Workbook()
    ws = wb.active
    ws.title = "Bao cao nhan vien"

    headers = [
        "Mã NV",
        "Tên nhân viên",
        "Bộ phận",
        "Chức vụ",
        "Tổng đơn",
        "Tổng video",
        "Tổng thời lượng (giây)",
        "Tổng thời lượng (phút)",
        "Tổng dung lượng (MB)",
    ]

    ws.append(headers)

    for r in rows:
        duration_sec = r.get("total_duration_sec") or 0
        ws.append([
            r.get("employee_id", ""),
            r.get("employee_name", ""),
            r.get("department", ""),
            r.get("position", ""),
            r.get("total_orders", 0),
            r.get("total_videos", 0),
            duration_sec,
            round(duration_sec / 60, 2),
            round(r.get("total_size_mb") or 0, 2),
        ])

    _style_sheet(ws)

    wb.save(save_path)
    return save_path