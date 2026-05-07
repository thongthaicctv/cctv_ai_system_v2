# FILE: hr/hr_page.py
# Trang "Tra cứu" – tích hợp vào main_window.py tại stack index 3
# Gồm 2 tab: 👥 Nhân sự  |  🎬 Video

import os
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSizePolicy,
    QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from hr.qr_generator import employee_qr_bytes, make_employee_qr, save_employee_qr
from hr.employee_manager import (
    add_employee, delete_employee, get_stats,
    load_employees, search_employees, update_employee,
)
from hr.video_index_manager import generate_html_report, load_index
try:
    from hr.video_index_manager import scan_and_build_index
except ImportError:
    from hr.video_index_manager import build_index as scan_and_build_index

# ──────────────────────────────────────
# Màu sắc khớp theme main_window.py
# ──────────────────────────────────────
_BG     = "#111111"
_PANEL  = "#1b1b1b"
_PANEL2 = "#161616"
_BORDER = "#2a2a2a"
_ACCENT = "#0f62fe"
_TEXT   = "#dddddd"
_MUTED  = "#888888"
_GREEN  = "#22c55e"
_RED    = "#ef4444"
_ORANGE = "#f59e0b"
_YELLOW = "#eab308"

_BASE = f"""
    QWidget   {{ background:{_BG}; color:{_TEXT}; font-family:'Segoe UI',sans-serif; font-size:13px; }}
    QFrame    {{ background:{_PANEL}; border:1px solid {_BORDER}; border-radius:8px; }}
    QLineEdit, QComboBox {{
        background:{_PANEL}; border:1px solid {_BORDER}; color:{_TEXT};
        padding:6px 10px; border-radius:6px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color:{_ACCENT}; }}
    QTableWidget {{
        background:{_PANEL}; border:1px solid {_BORDER};
        gridline-color:{_BORDER}; color:{_TEXT};
    }}
    QTableWidget::item:selected {{ background:rgba(15,98,254,.2); color:{_TEXT}; }}
    QHeaderView::section {{
        background:{_BG}; color:{_MUTED}; border:none;
        padding:6px 10px; font-weight:600; font-size:11px;
        text-transform:uppercase; letter-spacing:1px;
    }}
    QScrollBar:vertical {{ width:6px; background:transparent; }}
    QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; }}
    QPushButton {{
        background:{_PANEL}; color:{_TEXT}; border:1px solid {_BORDER};
        padding:7px 14px; border-radius:8px; font-weight:600;
        text-align:center;
    }}
    QPushButton:hover {{ border-color:{_ACCENT}; color:#ffffff; }}
"""

_BTN_PRIMARY = f"""
    QPushButton {{
        background:{_ACCENT}; color:#fff; border:none;
        padding:7px 18px; border-radius:8px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#1d74ff; }}
"""
_BTN_GREEN = f"""
    QPushButton {{
        background:{_GREEN}; color:#000; border:none;
        padding:5px 12px; border-radius:6px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#4ade80; }}
"""
_BTN_DANGER = f"""
    QPushButton {{
        background:{_RED}; color:#fff; border:none;
        padding:7px 14px; border-radius:8px; font-weight:700;
        text-align:center;
    }}
    QPushButton:hover {{ background:#f87171; }}
"""


# ─────────────────────────────────────────────
# STAT CARD
# ─────────────────────────────────────────────
class _StatCard(QFrame):
    def __init__(self, label: str, value, color: str = _ACCENT):
        super().__init__()
        self.setFixedHeight(82)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 10, 16, 10)
        self._val = QLabel(str(value))
        self._val.setStyleSheet(
            f"color:{color};font-size:26px;font-weight:700;border:none;background:transparent;"
        )
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color:{_MUTED};font-size:11px;border:none;background:transparent;"
        )
        lo.addWidget(self._val)
        lo.addWidget(self._lbl)

    def set_value(self, v):
        self._val.setText(str(v))


# ─────────────────────────────────────────────
# EMPLOYEE DIALOG  (form + QR preview)
# ─────────────────────────────────────────────
class _EmployeeDialog(QDialog):
    def __init__(self, parent=None, emp: dict | None = None):
        super().__init__(parent)
        self.emp = emp or {}
        self.result_data: dict = {}
        self.setWindowTitle("Thêm nhân viên" if not emp else "Cập nhật nhân viên")
        self.setFixedSize(820, 540)
        self.setStyleSheet(_BASE)
        self._build()
        # Nếu đang sửa – render QR ngay
        if emp and emp.get("id"):
            self._refresh_qr()

    def _build(self):
        # ── Outer: form bên trái | QR bên phải ──
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── LEFT: form ──────────────────────────
        left = QWidget()
        left.setStyleSheet("background:transparent;")
        lo = QVBoxLayout(left)
        lo.setContentsMargins(24, 20, 20, 20)
        lo.setSpacing(10)

        title = QLabel("👤 Thông tin nhân viên")
        title.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{_ACCENT};border:none;background:transparent;"
        )
        lo.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        def _f(ph, default=""):
            w = QLineEdit()
            w.setPlaceholderText(ph)
            w.setText(default)
            return w

        e = self.emp
        self.f_id    = _f("VD: NV006",    e.get("id", ""))
        self.f_name  = _f("Họ và tên",    e.get("name", ""))
        self.f_pos   = _f("Chức vụ",      e.get("position", ""))
        self.f_dept  = _f("Bộ phận",      e.get("department", ""))
        self.f_phone = _f("Điện thoại",   e.get("phone", ""))
        self.f_email = _f("Email",        e.get("email", ""))
        self.f_zone  = _f("VD: ECOM, Kho", ", ".join(e.get("camera_zone", [])))
        self.f_note  = _f("Ghi chú",      e.get("note", ""))

        self.f_shift = QComboBox()
        self.f_shift.addItems([
            "Ca sáng (6:00 - 14:00)",
            "Ca chiều (14:00 - 22:00)",
            "Ca đêm (22:00 - 6:00)",
            "Hành chính (8:00 - 17:00)",
        ])
        idx = self.f_shift.findText(e.get("shift", ""))
        if idx >= 0:
            self.f_shift.setCurrentIndex(idx)

        self.f_status = QComboBox()
        self.f_status.addItems(["active", "inactive"])
        self.f_status.setCurrentText(e.get("status", "active"))

        # Live update QR khi thay đổi ID / tên / bộ phận
        self.f_id.textChanged.connect(self._refresh_qr)
        self.f_name.textChanged.connect(self._refresh_qr)
        self.f_dept.textChanged.connect(self._refresh_qr)

        form.addRow("Mã NV *",    self.f_id)
        form.addRow("Họ tên *",   self.f_name)
        form.addRow("Chức vụ",    self.f_pos)
        form.addRow("Bộ phận",    self.f_dept)
        form.addRow("Điện thoại", self.f_phone)
        form.addRow("Email",      self.f_email)
        form.addRow("Khu vực",    self.f_zone)
        form.addRow("Ca làm",     self.f_shift)
        form.addRow("Trạng thái", self.f_status)
        form.addRow("Ghi chú",    self.f_note)
        lo.addLayout(form)

        btns = QHBoxLayout()
        b_cancel = QPushButton("Huỷ")
        b_save   = QPushButton("💾 Lưu")
        b_save.setStyleSheet(_BTN_PRIMARY)
        b_cancel.clicked.connect(self.reject)
        b_save.clicked.connect(self._save)
        btns.addWidget(b_cancel)
        btns.addStretch()
        btns.addWidget(b_save)
        lo.addLayout(btns)
        outer.addWidget(left, stretch=3)

        # ── RIGHT: QR panel ─────────────────────
        right = QFrame()
        right.setStyleSheet(
            f"QFrame{{background:#0d0d0d;border:none;border-left:1px solid {_BORDER};}}"
        )
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 24, 20, 20)
        rl.setSpacing(12)
        rl.setAlignment(Qt.AlignTop)

        qr_title = QLabel("QR Code Nhân viên")
        qr_title.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{_MUTED};text-transform:uppercase;"
            f"letter-spacing:1px;border:none;background:transparent;"
        )
        qr_title.setAlignment(Qt.AlignCenter)
        rl.addWidget(qr_title)

        # QR image label – khung trắng nền tối
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(240, 240)
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setStyleSheet(
            f"background:#ffffff;border:2px solid {_BORDER};border-radius:8px;"
        )
        self._set_qr_placeholder()
        rl.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        # Content label
        self.qr_content_lbl = QLabel("EMP: —")
        self.qr_content_lbl.setAlignment(Qt.AlignCenter)
        self.qr_content_lbl.setStyleSheet(
            f"color:{_MUTED};font-size:11px;font-family:Consolas,monospace;"
            f"border:none;background:transparent;"
        )
        rl.addWidget(self.qr_content_lbl)

        # Nút xuất PNG
        self.btn_export_qr = QPushButton("📥 Xuất QR (PNG)")
        self.btn_export_qr.setStyleSheet(_BTN_PRIMARY)
        self.btn_export_qr.setEnabled(False)
        self.btn_export_qr.clicked.connect(self._export_qr)
        rl.addWidget(self.btn_export_qr)

        # Nút in
        self.btn_print_qr = QPushButton("🖨️ In QR")
        self.btn_print_qr.setEnabled(False)
        self.btn_print_qr.clicked.connect(self._print_qr)
        rl.addWidget(self.btn_print_qr)

        rl.addStretch()
        outer.addWidget(right, stretch=2)

    # ── QR helpers ──────────────────────────────
    def _set_qr_placeholder(self):
        """Hiển thị placeholder khi chưa có mã NV."""
        from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
        pm = QPixmap(220, 220)
        pm.fill(QColor("#f8f8f8"))
        painter = QPainter(pm)
        pen = QPen(QColor("#cccccc"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(10, 10, 200, 200)
        painter.setPen(QColor("#aaaaaa"))
        from PySide6.QtGui import QFont as QF
        f = QF("Segoe UI", 10)
        painter.setFont(f)
        painter.drawText(pm.rect(), Qt.AlignCenter, "Nh\u1eadp m\u00e3 NV\n\u0111\u1ec3 t\u1ea1o QR")
        painter.end()
        self.qr_label.setPixmap(pm)

    def _refresh_qr(self):
        """Vẽ lại QR mỗi khi ID / tên / bộ phận thay đổi."""
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        dept   = self.f_dept.text().strip()

        if not emp_id:
            self._set_qr_placeholder()
            self.qr_content_lbl.setText("EMP: —")
            self.btn_export_qr.setEnabled(False)
            self.btn_print_qr.setEnabled(False)
            return

        try:
            from hr.qr_generator import employee_qr_bytes
            png_bytes = employee_qr_bytes(emp_id, name or emp_id, dept or "—")

            from PySide6.QtGui import QPixmap
            pm = QPixmap()
            pm.loadFromData(png_bytes)
            scaled = pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_label.setPixmap(scaled)
            self.qr_content_lbl.setText(f"EMP:{emp_id}")
            self.btn_export_qr.setEnabled(True)
            self.btn_print_qr.setEnabled(True)
            # Cache bytes để xuất
            self._qr_png_bytes = png_bytes
        except Exception as ex:
            self.qr_content_lbl.setText(f"Lỗi: {ex}")

    def _export_qr(self):
        from PySide6.QtWidgets import QFileDialog
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu QR Code",
            f"QR_{emp_id}_{name}.png",
            "PNG Image (*.png)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(self._qr_png_bytes)
            QMessageBox.information(self, "\u2705 \u0110\u00e3 l\u01b0u", f"QR code \u0111\u00e3 l\u01b0u t\u1ea1i:\\n{path}")

    def _print_qr(self):
        """In QR ra máy in mặc định."""
        emp_id = self.f_id.text().strip()
        name   = self.f_name.text().strip()
        dept   = self.f_dept.text().strip()
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QPixmap, QPainter
            from PySide6.QtCore import QRectF

            printer = QPrinter(QPrinter.HighResolution)
            dlg     = QPrintDialog(printer, self)
            if dlg.exec() != QPrintDialog.Accepted:
                return

            pm = QPixmap()
            pm.loadFromData(self._qr_png_bytes)

            painter = QPainter(printer)
            rect    = painter.viewport()
            size    = pm.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pm.rect())
            painter.drawPixmap(0, 0, pm)
            painter.end()
        except Exception as ex:
            QMessageBox.critical(self, "Lỗi in", str(ex))

    def _save(self):
        if not self.f_id.text().strip() or not self.f_name.text().strip():
            QMessageBox.warning(self, "Lỗi", "Mã NV và Họ tên không được để trống!")
            return
        zones = [z.strip() for z in self.f_zone.text().split(",") if z.strip()]
        self.result_data = {
            "id":          self.f_id.text().strip(),
            "name":        self.f_name.text().strip(),
            "position":    self.f_pos.text().strip(),
            "department":  self.f_dept.text().strip(),
            "phone":       self.f_phone.text().strip(),
            "email":       self.f_email.text().strip(),
            "camera_zone": zones,
            "shift":       self.f_shift.currentText(),
            "status":      self.f_status.currentText(),
            "note":        self.f_note.text().strip(),
        }
        self.accept()



# ─────────────────────────────────────────────
# QR VIEW DIALOG  (xem & xuất từ bảng nhân sự)
# ─────────────────────────────────────────────
class _QRViewDialog(QDialog):
    """Dialog hiển thị QR lớn, xuất PNG, in."""

    def __init__(self, parent=None, emp: dict | None = None):
        super().__init__(parent)
        self.emp = emp or {}
        self.setWindowTitle(f"QR Code – {emp.get('name', '')}")
        self.setFixedSize(380, 480)
        self.setStyleSheet(_BASE)
        self._png_bytes = b""
        self._build()
        self._render()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        # Tiêu đề
        t = QLabel("QR Code Nhân viên")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(
            f"font-size:13px;font-weight:700;color:{_MUTED};"
            f"text-transform:uppercase;letter-spacing:1px;border:none;background:transparent;"
        )
        lo.addWidget(t)

        # Khung QR
        self.qr_lbl = QLabel()
        self.qr_lbl.setFixedSize(300, 300)
        self.qr_lbl.setAlignment(Qt.AlignCenter)
        self.qr_lbl.setStyleSheet(
            "background:#ffffff;border:2px solid #333;border-radius:10px;"
        )
        lo.addWidget(self.qr_lbl, alignment=Qt.AlignCenter)

        # Content string
        self.content_lbl = QLabel()
        self.content_lbl.setAlignment(Qt.AlignCenter)
        self.content_lbl.setStyleSheet(
            f"color:{_ACCENT};font-family:Consolas,monospace;font-size:13px;"
            f"font-weight:700;border:none;background:transparent;"
        )
        lo.addWidget(self.content_lbl)

        # Tên + bộ phận
        self.info_lbl = QLabel()
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet(
            f"color:{_MUTED};font-size:12px;border:none;background:transparent;"
        )
        lo.addWidget(self.info_lbl)

        # Nút
        btn_row = QHBoxLayout()
        b_export = QPushButton("📥 Xuất PNG")
        b_export.setStyleSheet(_BTN_PRIMARY)
        b_export.clicked.connect(self._export)
        b_print  = QPushButton("🖨️ In")
        b_print.clicked.connect(self._print)
        b_close  = QPushButton("Đóng")
        b_close.clicked.connect(self.accept)
        btn_row.addWidget(b_export)
        btn_row.addWidget(b_print)
        btn_row.addWidget(b_close)
        lo.addLayout(btn_row)

    def _render(self):
        emp = self.emp
        emp_id = emp.get("id", "")
        name   = emp.get("name", emp_id)
        dept   = emp.get("department", "")
        if not emp_id:
            return
        try:
            from hr.qr_generator import employee_qr_bytes
            self._png_bytes = employee_qr_bytes(emp_id, name, dept)
            from PySide6.QtGui import QPixmap
            pm = QPixmap()
            pm.loadFromData(self._png_bytes)
            scaled = pm.scaled(290, 290, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_lbl.setPixmap(scaled)
            self.content_lbl.setText(f"EMP:{emp_id}")
            self.info_lbl.setText(f"{name}  •  {dept}")
        except Exception as ex:
            self.content_lbl.setText(f"Lỗi: {ex}")

    def _export(self):
        emp_id = self.emp.get("id", "NV")
        name   = self.emp.get("name", "")
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu QR Code", f"QR_{emp_id}_{name}.png", "PNG Image (*.png)"
        )
        if path and self._png_bytes:
            with open(path, "wb") as f:
                f.write(self._png_bytes)
            QMessageBox.information(self, "\u2705 \u0110\u00e3 l\u01b0u", f"\u0110\u00e3 l\u01b0u:\\n{path}")

    def _print(self):
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QPixmap, QPainter
            printer = QPrinter(QPrinter.HighResolution)
            dlg     = QPrintDialog(printer, self)
            if dlg.exec() != QPrintDialog.Accepted:
                return
            pm = QPixmap(); pm.loadFromData(self._png_bytes)
            painter = QPainter(printer)
            rect = painter.viewport()
            size = pm.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pm.rect())
            painter.drawPixmap(0, 0, pm)
            painter.end()
        except Exception as ex:
            QMessageBox.critical(self, "Lỗi in", str(ex))


# ─────────────────────────────────────────────
# HR TAB – Quản lý nhân sự
# ─────────────────────────────────────────────
class _HRTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)
        self._build()
        self._reload()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("👥 Quản lý Nhân sự")
        t.setStyleSheet(
            f"font-size:18px;font-weight:700;color:#ffffff;border:none;background:transparent;"
        )
        hdr.addWidget(t)
        hdr.addStretch()
        btn_add = QPushButton("+ Thêm nhân viên")
        btn_add.setStyleSheet(_BTN_PRIMARY)
        btn_add.clicked.connect(self._add)
        hdr.addWidget(btn_add)
        lo.addLayout(hdr)

        # Stats
        self.c_total    = _StatCard("Tổng nhân viên", 0, _ACCENT)
        self.c_active   = _StatCard("Đang làm",       0, _GREEN)
        self.c_inactive = _StatCard("Tạm nghỉ",       0, _ORANGE)
        self.c_depts    = _StatCard("Bộ phận",         0, _YELLOW)
        row_stats = QHBoxLayout()
        for c in [self.c_total, self.c_active, self.c_inactive, self.c_depts]:
            row_stats.addWidget(c)
        lo.addLayout(row_stats)

        # Search
        row_search = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Tìm tên, mã NV, bộ phận, khu vực...")
        self.txt_search.textChanged.connect(self._search)
        self.txt_search.setFixedHeight(34)
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tất cả", "active", "inactive"])
        self.cmb_status.currentTextChanged.connect(self._search)
        row_search.addWidget(self.txt_search)
        row_search.addWidget(self.cmb_status)
        lo.addLayout(row_search)

        # Table
        cols = ["Mã NV", "Họ & Tên", "Chức vụ", "Bộ phận", "Ca làm", "Khu vực",
                "Điện thoại", "Trạng thái", ""]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lo.addWidget(self.table)

    def _reload(self):
        s = get_stats()
        self.c_total.set_value(s["total"])
        self.c_active.set_value(s["active"])
        self.c_inactive.set_value(s["inactive"])
        self.c_depts.set_value(len(s["departments"]))
        self._fill(load_employees())

    def _fill(self, employees: list):
        self.table.setRowCount(0)
        for emp in employees:
            r = self.table.rowCount()
            self.table.insertRow(r)
            status = emp.get("status", "active")
            sc = _GREEN if status == "active" else _ORANGE
            zones = ", ".join(emp.get("camera_zone", []))
            vals = [
                emp.get("id", ""),
                emp.get("name", ""),
                emp.get("position", ""),
                emp.get("department", ""),
                emp.get("shift", ""),
                zones,
                emp.get("phone", ""),
                status,
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c == 7:
                    item.setForeground(QColor(sc))
                    item.setFont(QFont("Segoe UI", 11, QFont.Bold))
                self.table.setItem(r, c, item)

            # Action buttons
            aw = QWidget()
            aw.setStyleSheet("background:transparent;")
            ahl = QHBoxLayout(aw)
            ahl.setContentsMargins(4, 2, 4, 2)
            ahl.setSpacing(6)
            b_edit = QPushButton("✏️")
            b_edit.setFixedSize(28, 26)
            b_edit.setToolTip("Sửa")
            b_edit.clicked.connect(lambda _, e=emp: self._edit(e))
            b_del  = QPushButton("🗑")
            b_del.setFixedSize(28, 26)
            b_del.setToolTip("Xoá")
            b_del.clicked.connect(lambda _, eid=emp["id"]: self._delete(eid))
            ahl.addWidget(b_edit)
            ahl.addWidget(b_del)
            b_qr = QPushButton("\u25a3")
            b_qr.setFixedSize(28, 26)
            b_qr.setToolTip("Xem / Xu\u1ea5t QR")
            b_qr.setStyleSheet(
                f"QPushButton{{background:#1a1a2e;color:{_ACCENT};border:1px solid {_BORDER};"
                f"border-radius:4px;font-weight:700;font-size:13px;}}"
                f"QPushButton:hover{{border-color:{_ACCENT};;}}"
            )
            b_qr.clicked.connect(lambda _, e=emp: self._show_qr(e))
            ahl.addWidget(b_qr)
            self.table.setCellWidget(r, 8, aw)

    def _show_qr(self, emp: dict):
        """Mở dialog xem / xuất QR riêng từ bảng nhân sự."""
        dlg = _QRViewDialog(self, emp)
        dlg.exec()

    def _search(self):
        kw = self.txt_search.text()
        sf = self.cmb_status.currentText()
        res = search_employees(kw)
        if sf != "Tất cả":
            res = [e for e in res if e.get("status") == sf]
        self._fill(res)

    def _add(self):
        dlg = _EmployeeDialog(self)
        if dlg.exec() == QDialog.Accepted:
            if add_employee(dlg.result_data):
                self._reload()
                QMessageBox.information(self, "✅", f"Đã thêm {dlg.result_data['name']}")
            else:
                QMessageBox.warning(self, "Lỗi", f"Mã {dlg.result_data['id']} đã tồn tại!")

    def _edit(self, emp: dict):
        dlg = _EmployeeDialog(self, emp)
        if dlg.exec() == QDialog.Accepted:
            update_employee(emp["id"], dlg.result_data)
            self._reload()

    def _delete(self, emp_id: str):
        if QMessageBox.question(
            self, "Xác nhận", f"Xoá nhân viên <b>{emp_id}</b>?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            delete_employee(emp_id)
            self._reload()


# ─────────────────────────────────────────────
# VIDEO TAB – Tra cứu video đã ghi
# ─────────────────────────────────────────────
class _RebuildThread(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            idx = scan_and_build_index(self.path)
            generate_html_report(self.path)
            self.done.emit(idx)
        except Exception as e:
            self.error.emit(str(e))


class _VideoTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)
        self._thread: _RebuildThread | None = None
        from core.config_manager import load_config
        self._storage = load_config().get("storage_path", "records")
        self._videos: list = []
        self._build()
        self._load()

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("🎬 Tra cứu Video Đã Ghi")
        t.setStyleSheet(
            f"font-size:18px;font-weight:700;color:#ffffff;border:none;background:transparent;"
        )
        hdr.addWidget(t)
        hdr.addStretch()

        self.btn_folder  = QPushButton("📁 Đổi thư mục")
        self.btn_folder.clicked.connect(self._pick_folder)
        self.btn_rebuild = QPushButton("🔄 Cập nhật index")
        self.btn_rebuild.setStyleSheet(_BTN_PRIMARY)
        self.btn_rebuild.clicked.connect(self._rebuild)
        self.btn_html    = QPushButton("🌐 Mở HTML")
        self.btn_html.clicked.connect(self._open_html)

        for b in [self.btn_folder, self.btn_rebuild, self.btn_html]:
            hdr.addWidget(b)
        lo.addLayout(hdr)

        # Info
        self.lbl_path = QLabel(f"📂 {self._storage}")
        self.lbl_path.setStyleSheet(
            f"color:{_MUTED};font-size:11px;background:transparent;border:none;"
        )
        lo.addWidget(self.lbl_path)

        # Stats
        self.c_total = _StatCard("Tổng video",      0,  _ACCENT)
        self.c_size  = _StatCard("Dung lượng",  "0 MB", _ORANGE)
        self.c_cams  = _StatCard("Camera IDs",      0,  _YELLOW)
        self.c_emps  = _StatCard("Nhân viên",        0,  _GREEN)
        rr = QHBoxLayout()
        for c in [self.c_total, self.c_size, self.c_cams, self.c_emps]:
            rr.addWidget(c)
        rr.addStretch()
        lo.addLayout(rr)

        # Filters
        flt = QHBoxLayout()
        self.f_kw    = QLineEdit(); self.f_kw.setPlaceholderText("🔍 Mã đơn, nhân viên, camera...")
        self.f_kw.textChanged.connect(self._filter)
        self.f_kw.setFixedHeight(34)

        self.f_cam  = QComboBox()
        self.f_cam.addItem("Tất cả camera")
        self.f_cam.currentTextChanged.connect(self._filter)

        self.f_date = QLineEdit(); self.f_date.setPlaceholderText("Ngày YYYY-MM-DD")
        self.f_date.setFixedWidth(130); self.f_date.setFixedHeight(34)
        self.f_date.textChanged.connect(self._filter)

        self.f_order = QLineEdit(); self.f_order.setPlaceholderText("Mã đơn")
        self.f_order.setFixedWidth(130); self.f_order.setFixedHeight(34)
        self.f_order.textChanged.connect(self._filter)

        flt.addWidget(self.f_kw)
        flt.addWidget(self.f_cam)
        flt.addWidget(self.f_date)
        flt.addWidget(self.f_order)
        lo.addLayout(flt)

        # Table
        cols = ["Camera", "Tên camera", "Ngày", "Giờ", "Thời lượng",
                "Mã đơn", "Nhân viên", "Bộ phận", "Dung lượng", ""]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lo.addWidget(self.table)

    # ── Data ──────────────────────────────────
    def _load(self):
        idx = load_index(self._storage)
        self._videos = idx.get("videos", [])
        self._update_stats()
        self._update_cam_filter()
        self._fill(self._videos)

    def _update_stats(self):
        total = len(self._videos)
        size  = sum(v.get("file_size_mb", 0) for v in self._videos)
        cams  = len(set(v.get("camera_id", "") for v in self._videos))
        emps  = len(set(v.get("employee_id", "") for v in self._videos if v.get("employee_id") not in ("NOEMP", "", None)))
        self.c_total.set_value(total)
        self.c_size.set_value(f"{size:.1f} MB")
        self.c_cams.set_value(cams)
        self.c_emps.set_value(emps)

    def _update_cam_filter(self):
        cams = sorted(set(v.get("camera_id", "") for v in self._videos))
        self.f_cam.clear()
        self.f_cam.addItem("Tất cả camera")
        for c in cams:
            self.f_cam.addItem(c)

    def _fill(self, videos: list):
        self.table.setRowCount(0)
        for v in videos:
            r = self.table.rowCount()
            self.table.insertRow(r)

            dur = v.get("duration_sec", 0)
            dur_txt = f"{dur//60}:{dur%60:02d}"
            emp = v.get("employee_name") or v.get("employee_id", "—")

            cam_item = QTableWidgetItem(v.get("camera_id", ""))
            cam_item.setForeground(QColor(_ACCENT))
            cam_item.setFont(QFont("Consolas", 11, QFont.Bold))

            order_item = QTableWidgetItem(v.get("order_code", "—"))
            order_item.setForeground(QColor(_YELLOW))

            vals = [
                (cam_item, None),
                (QTableWidgetItem(v.get("camera_name", "")), None),
                (QTableWidgetItem(v.get("date", "")), None),
                (QTableWidgetItem(v.get("start_time", "")[11:16]), None),
                (QTableWidgetItem(dur_txt), None),
                (order_item, None),
                (QTableWidgetItem(emp), None),
                (QTableWidgetItem(v.get("department", "—")), None),
                (QTableWidgetItem(f"{v.get('file_size_mb',0)} MB"), None),
            ]
            for c, (item, _) in enumerate(vals):
                self.table.setItem(r, c, item)

            # Actions
            full_path = os.path.join(self._storage, v.get("file_path", v.get("filename", "")))
            aw = QWidget(); aw.setStyleSheet("background:transparent;")
            ahl = QHBoxLayout(aw); ahl.setContentsMargins(4, 2, 4, 2); ahl.setSpacing(4)
            b_play = QPushButton("▶")
            b_play.setFixedSize(28, 26)
            b_play.setStyleSheet(_BTN_GREEN.replace("padding:5px 12px", "padding:0"))
            b_play.clicked.connect(lambda _, p=full_path: self._play(p))
            b_dl = QPushButton("⬇")
            b_dl.setFixedSize(28, 26)
            b_dl.setToolTip("Tải về")
            b_dl.clicked.connect(lambda _, p=full_path, n=v.get("filename",""): self._download(p, n))
            ahl.addWidget(b_play); ahl.addWidget(b_dl)
            self.table.setCellWidget(r, 9, aw)

    def _filter(self):
        kw    = self.f_kw.text().lower()
        cam   = self.f_cam.currentText()
        date  = self.f_date.text().strip()
        order = self.f_order.text().strip().lower()
        res = [
            v for v in self._videos
            if (not kw or any(kw in str(v.get(f, "")).lower()
                              for f in ("camera_id","camera_name","order_code","employee_id","employee_name","filename")))
            and (cam == "Tất cả camera" or v.get("camera_id") == cam)
            and (not date or v.get("date", "").startswith(date))
            and (not order or order in v.get("order_code", "").lower())
        ]
        self._fill(res)

    def _rebuild(self):
        if self._thread and self._thread.isRunning():
            return
        self.btn_rebuild.setEnabled(False)
        self.btn_rebuild.setText("⏳ Đang quét...")
        self._thread = _RebuildThread(self._storage)
        self._thread.done.connect(self._on_rebuild_done)
        self._thread.error.connect(self._on_rebuild_error)
        self._thread.start()

    def _on_rebuild_done(self, idx: dict):
        self.btn_rebuild.setEnabled(True)
        self.btn_rebuild.setText("🔄 Cập nhật index")
        self._videos = idx.get("videos", [])
        self._update_stats()
        self._update_cam_filter()
        self._fill(self._videos)
        QMessageBox.information(
            self, "✅ Xong",
            f"Đã cập nhật: {idx['total']} video\nĐã tạo index.html"
        )

    def _on_rebuild_error(self, msg: str):
        self.btn_rebuild.setEnabled(True)
        self.btn_rebuild.setText("🔄 Cập nhật index")
        QMessageBox.critical(self, "Lỗi", msg)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục video", self._storage)
        if folder:
            self._storage = folder
            self.lbl_path.setText(f"📂 {folder}")
            self._load()

    def _play(self, path: str):
        if not os.path.exists(path):
            QMessageBox.warning(self, "Không tìm thấy", f"File không tồn tại:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi phát video", str(e))

    def _download(self, src: str, filename: str):
        if not os.path.exists(src):
            QMessageBox.warning(self, "Không tìm thấy", f"File không tồn tại:\n{src}")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Lưu video", filename)
        if dest:
            import shutil
            shutil.copy2(src, dest)
            QMessageBox.information(self, "✅ Đã lưu", f"Đã lưu tại:\n{dest}")

    def _open_html(self):
        html_path = os.path.join(self._storage, "index.html")
        if not os.path.exists(html_path):
            generate_html_report(self._storage)
        try:
            if sys.platform == "win32":
                os.startfile(html_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", html_path])
            else:
                subprocess.Popen(["xdg-open", html_path])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


# ─────────────────────────────────────────────
# HR PAGE – Widget chính gắn vào stack index 3
# ─────────────────────────────────────────────
class HRPage(QWidget):
    """
    Gắn vào main_window.py tại stack index 3 (thay QLabel "Tra cứu đơn hàng").
    Sidebar trái chọn tab: Nhân sự | Video.
    """

    def __init__(self):
        super().__init__()
        self.setStyleSheet(_BASE)
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ──────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(148)
        sidebar.setStyleSheet(
            f"QFrame{{background:{_PANEL2};border:none;border-right:1px solid {_BORDER};border-radius:0;}}"
        )
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(10, 18, 10, 18)
        sb.setSpacing(6)

        lbl = QLabel("TRA CỨU")
        lbl.setStyleSheet(
            f"color:{_MUTED};font-size:10px;font-weight:700;letter-spacing:2px;background:transparent;border:none;padding:0 4px;"
        )
        sb.addWidget(lbl)

        self._tab_btns = []
        for i, (icon, text) in enumerate([("👥", "Nhân sự"), ("🎬", "Video")]):
            btn = QPushButton(f"{icon}  {text}")
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton{{
                    background:transparent;color:{_MUTED};border:none;
                    text-align:left;padding:10px 12px;border-radius:6px;font-size:13px;
                }}
                QPushButton:hover{{background:rgba(255,255,255,.05);color:{_TEXT};}}
                QPushButton:checked{{background:rgba(15,98,254,.25);color:#ffffff;font-weight:700;}}
            """)
            btn.clicked.connect(lambda _, idx=i: self._switch(idx))
            sb.addWidget(btn)
            self._tab_btns.append(btn)

        sb.addStretch()
        outer.addWidget(sidebar)

        # ── Stacked content ──────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(_HRTab())    # 0
        self._stack.addWidget(_VideoTab()) # 1
        outer.addWidget(self._stack)

        self._switch(0)

    def _switch(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, b in enumerate(self._tab_btns):
            b.setChecked(i == idx)
