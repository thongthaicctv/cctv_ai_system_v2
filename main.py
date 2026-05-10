import sys
import os
import ctypes
from license.license_dialog import LicenseDialog

from hr.report_db import init_report_db


from core.config_manager import load_config
from core.resource_paths import resource_path
from services.cleanup_service import cleanup_index_and_video_sync


from hr.video_index_manager import build_index, generate_html_report

# =========================
# EXE RUNTIME PATH
# =========================
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# =========================
# OPENCV RTSP TCP
# =========================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from core.gpu_acceleration import configure_opencv_acceleration, prepare_gpu_runtime
from license.license_manager import LicenseManager
from system_logger import log


def main():
    prepare_gpu_runtime()

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ATGSolution.ProVideoAISystem.1.0"
        )
    except Exception:
        pass

    from ui.main_window import MainWindow

    accel_info = configure_opencv_acceleration()
    print(accel_info["message"])

    app = QApplication(sys.argv)
    app.gpu_runtime_info = accel_info
    app_icon = QIcon(resource_path("icon.ico"))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    init_report_db()

    # =========================
    # STARTUP VIDEO MAINTENANCE
    # Chạy 1 lần khi khởi động app
    # =========================

    cfg = load_config(force=True)
    storage_path = cfg.get("storage_path", "recordings")

    print("STORAGE =", storage_path)
    print("CLEANUP ENABLED =", cfg.get("cleanup_enabled"))
    print("KEEP INDEX DAYS =", cfg.get("keep_index_days"))

    # 1. Cleanup trước
    cleanup_index_and_video_sync(
        storage_path=storage_path,
        keep_days=int(cfg.get("keep_index_days", 180)),
        enabled=bool(cfg.get("cleanup_enabled", False))
    )

    # 2. Update index sau khi cleanup
    try:
        print("[STARTUP INDEX] Updating index...")
        build_index(storage_path)
        print("[STARTUP INDEX] Done")
    except Exception as e:
        print("[STARTUP INDEX ERROR]", e)

    # 3. Update HTML sau khi update index
    try:
        print("[STARTUP HTML] Updating index.html...")
        generate_html_report(storage_path)
        print("[STARTUP HTML] Done")
    except Exception as e:
        print("[STARTUP HTML ERROR]", e)


   

    # =========================
    # LICENSE CHECK
    # =========================

    license_manager = LicenseManager()

    ok, msg = license_manager.check()

    print(msg)

    if not ok:

        dlg = LicenseDialog(
            license_manager.device_id,
            msg
        )

        dlg.exec()

        sys.exit()
    # ========================= 
    # GLOBAL LICENSE MANAGER 
    # ========================= 
    app.license_manager = license_manager
    

    
    # =========================
    # MAIN WINDOW
    # =========================

    window = MainWindow()

    QTimer.singleShot(
        1000,
        lambda: log(f"[GPU] {accel_info['message']}")
    )
    
    app.record_engine = window.record

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
