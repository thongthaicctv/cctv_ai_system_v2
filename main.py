import sys
import os

# =========================
# EXE RUNTIME PATH
# =========================
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# =========================
# OPENCV RTSP TCP
# =========================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

from PySide6.QtWidgets import QApplication, QMessageBox

from core.gpu_acceleration import configure_opencv_acceleration, prepare_gpu_runtime
from license.license_manager import LicenseManager
from system_logger import log


def main():
    prepare_gpu_runtime()

    from ui.main_window import MainWindow

    accel_info = configure_opencv_acceleration()
    print(accel_info["message"])

    app = QApplication(sys.argv)
    app.gpu_runtime_info = accel_info

    # =========================
    # LICENSE CHECK
    # =========================

    license_manager = LicenseManager()

    ok, msg = license_manager.check()

    print(msg)

    if not ok:
        QMessageBox.critical(None, "License", msg)
        sys.exit()
    # ========================= 
    # GLOBAL LICENSE MANAGER 
    # ========================= 
    app.license_manager = license_manager
    

    
    # =========================
    # MAIN WINDOW
    # =========================

    window = MainWindow()
    log(accel_info["message"])
    
    app.record_engine = window.record

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
