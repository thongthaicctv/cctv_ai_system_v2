from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QFrame
from PySide6.QtCore import QTimer, Qt
import psutil
import shutil
import os

from core.config_manager import load_config

try:
    import GPUtil
except:
    GPUtil = None




class InfoCard(QFrame):
    def __init__(self, title):
        super().__init__()

        self.setMinimumHeight(130)

        

        self.setStyleSheet("""
        QFrame{
            background:#0f0f0f;
            border:1px solid #2d2d2d;
            border-radius:10px;
        }
        QLabel{
            color:white;
            border:none;
        }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("""
            font-size:45px;
            font-weight:bold;
            color:#ffffff;
            letter-spacing:1px;
        """)

        self.lbl_value = QLabel("...")
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setStyleSheet("""
            font-size:34px;
            font-weight:bold;
            color:#00ffaa;
        """)

        layout.addWidget(self.lbl_title)
        layout.addStretch()
        layout.addWidget(self.lbl_value)
        layout.addStretch()

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        self.record_path = self.load_storage_path()

        self.cards = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(25, 25, 25, 25)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i, name in enumerate(["CPU", "RAM", "GPU", "DISK"]):
            card = InfoCard(name)
            self.cards[name] = card
            grid.addWidget(card, i // 2, i % 2)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_info)

    def showEvent(self, e):
        self.update_info()
        self.timer.start(3000)   # 3 giây update 1 lần

    def hideEvent(self, e):
        self.timer.stop()

    def update_info(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        try:
            self.record_path = self.load_storage_path()

            drive = os.path.splitdrive(self.record_path)[0] + "\\"

            disk = shutil.disk_usage(drive)

            used = round(disk.used / 1024 / 1024 / 1024)
            total = round(disk.total / 1024 / 1024 / 1024)
            free = round(disk.free / 1024 / 1024 / 1024)

        except Exception as e:
            print("DISK ERROR:", e)

            used = 0
            total = 0
            free = 0

        gpu = 0
        gpu_text = "N/A"

        if GPUtil:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0].load * 100
                    gpu_text = f"{gpu:.0f}%"
            except:
                pass

        self.cards["CPU"].lbl_value.setText(f"{cpu}%")
        self.cards["RAM"].lbl_value.setText(f"{ram}%")
        self.cards["GPU"].lbl_value.setText(gpu_text)
        self.cards["DISK"].lbl_value.setText(f"{used}/{total} GB")

        # Màu cảnh báo
        self.cards["CPU"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if cpu >= 95 else '#00ffaa'};"
        )

        self.cards["RAM"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if ram >= 95 else '#00ffaa'};"
        )

        self.cards["GPU"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if gpu >= 95 else '#00ffaa'};"
        )

        self.cards["DISK"].lbl_value.setStyleSheet(
            f"font-size:34px;font-weight:bold;color:{'red' if free < 10 else '#00ffaa'};"
        )

    def load_storage_path(self):
        try:
            config = load_config()
            return config.get("storage_path", "C:\\")
        except Exception as e:
            print("LOAD CONFIG ERROR:", e)
            return "C:\\"
