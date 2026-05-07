import threading

from services.record_worker import DEFAULT_RECORD_AUTO_STOP_SECONDS, RecordWorker
from PySide6.QtWidgets import QApplication

from core.logger import write_license_log

class RecordEngine:
    def __init__(self, state, storage_path, auto_stop_seconds=DEFAULT_RECORD_AUTO_STOP_SECONDS):
        self.state = state
        self.storage_path = storage_path
        self.auto_stop_seconds = auto_stop_seconds
        self.workers = {}
        self.threads = {}

    def start_camera(self, cam):

        if not cam.get("enabled", True):
            return

        # =========================
        # LICENSE CHECK
        # =========================
        license_manager = QApplication.instance().license_manager

        max_camera = int(
            license_manager.data.get("max_camera", 0)
        )

        active_camera = len(self.workers)

        print("LICENSE MAX:", max_camera)
        print("ACTIVE WORKERS:", active_camera)

        if active_camera >= max_camera:

            msg = (
                f"LICENSE LIMIT BLOCK: "
                f"{active_camera}/{max_camera}"
            )

            print(msg)

            write_license_log(msg)

            return

        # =========================
        # START WORKER
        # =========================
        cam_id = cam["id"]

        if cam_id in self.workers:
            return

        worker = RecordWorker(
            cam,
            self.state,
            self.storage_path,
            self.auto_stop_seconds,
        )

        thread = threading.Thread(
            target=worker.run,
            daemon=True,
        )

        self.workers[cam_id] = worker
        self.threads[cam_id] = thread

        thread.start()

    def stop_camera(self, cam_id):
        if cam_id not in self.workers:
            return

        self.workers[cam_id].stop()
        del self.workers[cam_id]
        self.threads.pop(cam_id, None)

    def start_all(self, cameras):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)

        license_manager = QApplication.instance().license_manager

        max_camera = int(
            license_manager.data.get("max_camera", 0)
        )

        enabled_cameras = [
            cam for cam in cameras
            if cam.get("enabled", True)
        ]

        print(
            f"LICENSE START LIMIT: "
            f"{max_camera}/{len(enabled_cameras)}"
        )

        # HARD LIMIT
        limited_cameras = enabled_cameras[:max_camera]

        print("START_ALL RUNNING")
        print("LIMITED CAMERAS:")
        print([c["id"] for c in limited_cameras])

        for cam in limited_cameras:

            self.start_camera(cam)

        # debug blocked
        for cam in enabled_cameras[max_camera:]:

            msg = (
                f"LICENSE BLOCK CAMERA: "
                f"{cam.get('id')}"
            )

            print(msg)

            write_license_log(msg)

    def update_settings(self, storage_path, auto_stop_seconds):
        self.storage_path = storage_path
        self.auto_stop_seconds = auto_stop_seconds

        for worker in self.workers.values():
            worker.storage_path = storage_path
            worker.auto_stop_seconds = auto_stop_seconds

    def stop_all(self):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)
