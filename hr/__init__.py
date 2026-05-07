# hr/__init__.py
from .employee_manager import (
    load_employees, save_employees, add_employee,
    update_employee, delete_employee, search_employees,
    get_stats, get_employee_by_id,
)
from .video_index_manager import (
    generate_html_report,
    load_index,
)
# Import scan_and_build_index hoặc build_index tuỳ file nào có
try:
    from .video_index_manager import scan_and_build_index
except ImportError:
    from .video_index_manager import build_index as scan_and_build_index

try:
    from .video_index_manager import build_index
except ImportError:
    build_index = scan_and_build_index

from .hr_page import HRPage
from .qr_generator import employee_qr_bytes, make_employee_qr, save_employee_qr
