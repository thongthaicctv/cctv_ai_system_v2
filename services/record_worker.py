import math
import os
import time
from datetime import datetime

import cv2

from system_logger import log
from utils.url_helper import camera_rtsp_url, open_rtsp_capture


DEFAULT_RECORD_AUTO_STOP_SECONDS = 300
IDLE_POLL_INTERVAL_SECONDS = 0.25
RETRY_DELAY_SECONDS = 1.0
FRAME_WRITE_DELAY_SECONDS = 0.001


class RecordWorker:
    def __init__(self, cam, state, storage_path, auto_stop_seconds):
        self.cam = cam
        self.state = state
        self.storage_path = storage_path
        self.auto_stop_seconds = int(auto_stop_seconds or DEFAULT_RECORD_AUTO_STOP_SECONDS)
        self.running = True

        self.capture = None
        self.writer = None
        self.current_file = ""
        self.current_order = ""
        self.current_employee = ""
        self.record_started_mono = 0.0

    def run(self):
        cam_id = self.cam["id"]

        while self.running:
            snapshot = dict(self.state.get(cam_id))

            if not snapshot.get("recording") or not snapshot.get("order_code"):
                self._close_session("STOP")
                time.sleep(IDLE_POLL_INTERVAL_SECONDS)
                continue

            if self.writer is None or self.capture is None:
                if not self._open_session(snapshot):
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
            elif self.current_order != snapshot.get("order_code", ""):
                if not self._switch_order(snapshot):
                    self._close_session("SWITCH")
                    if not self._open_session(snapshot):
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
            else:
                self.current_employee = snapshot.get("employee_id", "")

            if self._auto_stop_due():
                self._close_session("AUTO")
                self.state.stop_record(cam_id, clear_employee=False)
                time.sleep(IDLE_POLL_INTERVAL_SECONDS)
                continue

            if not self._write_next_frame():
                self.state.set_error(cam_id, "Main stream lost during recording")
                self._close_session("FAIL")
                self.state.stop_record(cam_id, clear_employee=False)
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            time.sleep(FRAME_WRITE_DELAY_SECONDS)

        self._close_session("STOP")

    def _open_session(self, snapshot):
        cam_id = self.cam["id"]
        rtsp = camera_rtsp_url(self.cam, prefer="main")
        if not rtsp:
            self.state.set_error(cam_id, "Missing main RTSP URL for recording")
            return False

        capture = open_rtsp_capture(
            rtsp,
            open_timeout_msec=self.cam.get("record_open_timeout_msec", 5000),
            read_timeout_msec=self.cam.get("record_read_timeout_msec", 5000),
        )
        if not capture.isOpened():
            self.state.set_error(cam_id, "Cannot open main RTSP stream for recording")
            return False

        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            self.state.set_error(cam_id, "Cannot read main stream frame for recording")
            return False

        writer, output_path = self._create_writer(capture, frame, snapshot)
        if writer is None:
            capture.release()
            self.state.set_error(cam_id, "Cannot create video writer")
            return False

        writer.write(frame)

        self.capture = capture
        self.writer = writer
        self.current_file = output_path
        self.current_order = snapshot.get("order_code", "")
        self.current_employee = snapshot.get("employee_id", "")
        self.record_started_mono = time.monotonic()

        self.state.set_video(cam_id, output_path)
        self.state.clear_error(cam_id)
        log(f"{self.cam['name']} START {self.current_order}")
        return True

    def _switch_order(self, snapshot):
        if self.capture is None or self.writer is None:
            return False

        try:
            ok, frame = self.capture.read()
        except Exception:
            ok, frame = False, None

        if not ok or frame is None:
            return False

        new_writer, output_path = self._create_writer(self.capture, frame, snapshot)
        if new_writer is None:
            return False

        old_order = self.current_order
        old_writer = self.writer

        self.writer = new_writer
        self.current_file = output_path
        self.current_order = snapshot.get("order_code", "")
        self.current_employee = snapshot.get("employee_id", "")
        self.record_started_mono = time.monotonic()

        self.writer.write(frame)
        old_writer.release()

        self.state.set_video(self.cam["id"], output_path)
        self.state.clear_error(self.cam["id"])
        if old_order != self.current_order:
            log(f"{self.cam['name']} STOP {old_order}")
            log(f"{self.cam['name']} START {self.current_order}")
        return True

    def _create_writer(self, capture, frame, snapshot):
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not fps or math.isnan(fps) or fps < 1 or fps > 120:
            fps = 20.0

        height, width = frame.shape[:2]
        base_dir = self._build_output_dir()
        base_name = self._build_output_name(snapshot)

        candidates = [
            (os.path.join(base_dir, f"{base_name}.mp4"), "mp4v"),
            (os.path.join(base_dir, f"{base_name}.avi"), "XVID"),
        ]

        for output_path, codec in candidates:
            writer = cv2.VideoWriter(
                output_path,
                cv2.VideoWriter_fourcc(*codec),
                fps,
                (width, height),
            )
            if writer.isOpened():
                return writer, os.path.abspath(output_path)
            writer.release()

        return None, ""

    def _write_next_frame(self):
        if self.capture is None or self.writer is None:
            return False

        try:
            ok, frame = self.capture.read()
        except Exception:
            ok, frame = False, None

        if not ok or frame is None:
            return False

        self.writer.write(frame)
        return True

    def _auto_stop_due(self):
        seconds = int(self.cam.get("record_auto_stop_seconds", self.auto_stop_seconds))
        if seconds <= 0 or self.record_started_mono <= 0:
            return False

        return (time.monotonic() - self.record_started_mono) >= seconds

    def _close_session(self, reason=None):
        if self.current_order:
            status = {
                "AUTO": f"REC AUTO STOP {self.current_order}",
                "FAIL": f"REC FAIL {self.current_order}",
            }.get(reason, f"REC STOP {self.current_order}")
            log(f"{self.cam['name']} {status}")

        if self.writer is not None:
            self.writer.release()
            self.writer = None

        if self.capture is not None:
            self.capture.release()
            self.capture = None

        self.current_file = ""
        self.current_order = ""
        self.current_employee = ""
        self.record_started_mono = 0.0

    def _build_output_dir(self):
        day = datetime.now().strftime("%Y-%m-%d")
        directory = os.path.join(self.storage_path, day)
        os.makedirs(directory, exist_ok=True)
        return directory

    def _build_output_name(self, snapshot):
        now = datetime.now()
        date_text = now.strftime("%Y%m%d")
        time_text = now.strftime("%H%M%S")
        employee_id = self._safe_name(snapshot.get("employee_id", "NOEMP")) or "NA"
        order_code = self._safe_name(snapshot.get("order_code", "NOORDER"))
        cam = self._safe_name(self.cam["id"])
        return f"{order_code}_C{cam}_{employee_id}_{date_text}_{time_text}"

    def _safe_name(self, value):
        cleaned = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in str(value).strip()
        )
        return cleaned or "NA"

    def stop(self):
        self.running = False
