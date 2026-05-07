import threading
from services.qr_worker import QRWorker
ENGINE_INSTANCE = None








def manual_qr_command(text):

    global ENGINE_INSTANCE

    if ENGINE_INSTANCE:
        ENGINE_INSTANCE.handle_manual_command(text)


class QREngine:

    def __init__(self, state):
        self.state = state
        self.workers = {}
        self.threads = {}

        global ENGINE_INSTANCE
        ENGINE_INSTANCE = self

    def start_camera(self, cam):
        if not cam.get("enabled", True):
            return

        cam_id = cam["id"]

        if cam_id in self.workers:
            return

        worker = QRWorker(cam, self.state)

        th = threading.Thread(
            target=worker.run,
            daemon=True
        )

        th.start()

        self.workers[cam_id] = worker
        self.threads[cam_id] = th

    def stop_camera(self, cam_id):
        if cam_id in self.workers:
            self.workers[cam_id].stop()
            del self.workers[cam_id]
            self.threads.pop(cam_id, None)

    def start_all(self, cameras):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)

        for cam in cameras:
            self.start_camera(cam)

    def stop_all(self):
        for cam_id in list(self.workers.keys()):
            self.stop_camera(cam_id)

               

    def handle_manual_command(self, text):

        for worker in self.workers.values():
            worker._handle_command(
                "manual",
                text
            )
            break
