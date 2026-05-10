import math
import os
import shutil
import subprocess
import time
from datetime import datetime

import cv2

from system_logger import log
from core.resource_paths import resource_path
from services.audio_service import record_error
from utils.url_helper import camera_rtsp_url, open_rtsp_capture


DEFAULT_RECORD_AUTO_STOP_SECONDS = 300
WAIT_RECORD_UPDATE_TIMEOUT_SECONDS = 1.0
RETRY_DELAY_SECONDS = 1.0
FRAME_WRITE_DELAY_SECONDS = 0.0
RECORD_ERROR_SOUND_INTERVAL_SECONDS = 10.0
FFMPEG_STARTUP_CHECK_SECONDS = 1.0
FFMPEG_POLL_DELAY_SECONDS = 0.2
FFMPEG_PATHS = (
    r"C:\ffmpeg\bin\ffmpeg.exe",
    "ffmpeg",
)


class RecordWorker:
    def __init__(self, cam, state, storage_path, auto_stop_seconds):
        self.cam = cam
        self.state = state
        self.storage_path = storage_path
        self.auto_stop_seconds = int(auto_stop_seconds or DEFAULT_RECORD_AUTO_STOP_SECONDS)
        self.running = True

        self.capture = None
        self.writer = None
        self.ffmpeg_process = None
        self.ffmpeg_mode = ""
        self.current_file = ""
        self.current_order = ""
        self.current_employee = ""
        self.record_started_mono = 0.0
        self.last_error_sound_mono = 0.0

    def run(self):
        cam_id = self.cam["id"]

        while self.running:
            snapshot = self.state.get(cam_id)
            if not snapshot.get("recording") or not snapshot.get("order_code"):
                self._close_session("STOP")
                snapshot = self.state.wait_for_record_update(
                    cam_id,
                    snapshot.get("record_version", 0),
                    timeout=WAIT_RECORD_UPDATE_TIMEOUT_SECONDS,
                )
                if not self.running:
                    break
                if not snapshot.get("recording") or not snapshot.get("order_code"):
                    continue

            if not self._has_active_session():
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
                continue

            if self.ffmpeg_process is not None:
                if self.ffmpeg_process.poll() is not None:
                    self._set_record_error("FFmpeg recording stopped unexpectedly")
                    self._close_session("FAIL")
                    self.state.stop_record(cam_id, clear_employee=False)
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    time.sleep(FFMPEG_POLL_DELAY_SECONDS)
                continue

            if not self._write_next_frame():
                self._set_record_error("Main stream lost during recording")
                self._close_session("FAIL")
                self.state.stop_record(cam_id, clear_employee=False)
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            if FRAME_WRITE_DELAY_SECONDS > 0:
                time.sleep(FRAME_WRITE_DELAY_SECONDS)

        self._close_session("STOP")

    def _open_session(self, snapshot):
        if self._open_ffmpeg_session(snapshot):
            return True

        return self._open_cv2_session(snapshot)

    def _open_cv2_session(self, snapshot):
        cam_id = self.cam["id"]
        rtsp = camera_rtsp_url(self.cam, prefer="main")
        if not rtsp:
            self._set_record_error("Missing main RTSP URL for recording")
            return False

        capture = open_rtsp_capture(
            rtsp,
            open_timeout_msec=self.cam.get("record_open_timeout_msec", 5000),
            read_timeout_msec=self.cam.get("record_read_timeout_msec", 5000),
        )
        if not capture.isOpened():
            self._set_record_error("Cannot open main RTSP stream for recording")
            return False

        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            self._set_record_error("Cannot read main stream frame for recording")
            return False

        writer, output_path = self._create_writer(capture, frame, snapshot)
        if writer is None:
            capture.release()
            self._set_record_error("Cannot create video writer")
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

    def _open_ffmpeg_session(self, snapshot):
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            return False

        rtsp = camera_rtsp_url(self.cam, prefer="main")
        if not rtsp:
            self._set_record_error("Missing main RTSP URL for recording")
            return False

        base_dir = self._build_output_dir()
        base_name = self._build_output_name(snapshot)
        output_path = os.path.abspath(os.path.join(base_dir, f"{base_name}.mp4"))

        attempts = []
        if self._ffmpeg_has_encoder(ffmpeg, "h264_nvenc"):
            attempts.append(("ffmpeg-nvenc", self._ffmpeg_nvenc_command(ffmpeg, rtsp, output_path)))
        attempts.append(("ffmpeg-copy", self._ffmpeg_copy_command(ffmpeg, rtsp, output_path)))

        for mode, command in attempts:
            process = self._start_ffmpeg(command)
            if process is None:
                continue

            time.sleep(FFMPEG_STARTUP_CHECK_SECONDS)
            if process.poll() is None:
                self.ffmpeg_process = process
                self.ffmpeg_mode = mode
                self.current_file = output_path
                self.current_order = snapshot.get("order_code", "")
                self.current_employee = snapshot.get("employee_id", "")
                self.record_started_mono = time.monotonic()

                self.state.set_video(self.cam["id"], output_path)
                self.state.clear_error(self.cam["id"])
                log(f"{self.cam['name']} START {self.current_order} ({mode})")
                return True

            self._terminate_ffmpeg_process(process)

        self._set_record_error("Cannot start FFmpeg recording")
        return False

    def _switch_order(self, snapshot):
        if self.ffmpeg_process is not None:
            self._close_session("SWITCH")
            return self._open_session(snapshot)

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

    def _has_active_session(self):
        if self.ffmpeg_process is not None:
            return self.ffmpeg_process.poll() is None
        return self.writer is not None and self.capture is not None

    def _find_ffmpeg(self):
        configured = str(self.cam.get("ffmpeg_path", "")).strip()
        candidates = [configured] if configured else []
        candidates.append(resource_path("ffmpeg.exe"))
        candidates.extend(FFMPEG_PATHS)

        for candidate in candidates:
            if not candidate:
                continue
            resolved = shutil.which(candidate) if candidate.lower() == "ffmpeg" else candidate
            if resolved and os.path.exists(resolved):
                return resolved

        return ""

    def _ffmpeg_base_input_args(self, rtsp):
        timeout_us = int(self.cam.get("record_open_timeout_msec", 5000)) * 1000
        return [
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-timeout",
            str(timeout_us),
            "-rw_timeout",
            str(timeout_us),
            "-i",
            rtsp,
        ]

    def _ffmpeg_nvenc_command(self, ffmpeg, rtsp, output_path):
        bitrate = str(self.cam.get("record_nvenc_bitrate", "4M"))
        maxrate = str(self.cam.get("record_nvenc_maxrate", "8M"))
        return [
            ffmpeg,
            "-hwaccel",
            "cuda",
            *self._ffmpeg_base_input_args(rtsp),
            "-an",
            "-c:v",
            "h264_nvenc",
            "-preset",
            str(self.cam.get("record_nvenc_preset", "p4")),
            "-rc",
            "vbr",
            "-cq",
            str(self.cam.get("record_nvenc_cq", 23)),
            "-b:v",
            bitrate,
            "-maxrate",
            maxrate,
            "-bufsize",
            maxrate,
            "-movflags",
            "+faststart",
            "-y",
            output_path,
        ]

    def _ffmpeg_copy_command(self, ffmpeg, rtsp, output_path):
        return [
            ffmpeg,
            *self._ffmpeg_base_input_args(rtsp),
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            "-y",
            output_path,
        ]

    def _ffmpeg_has_encoder(self, ffmpeg, encoder):
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return False

        return result.returncode == 0 and encoder in result.stdout

    def _start_ffmpeg(self, command):
        try:
            return subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return None

    def _terminate_ffmpeg_process(self, process):
        if process is None:
            return

        if process.poll() is not None:
            return

        try:
            if process.stdin:
                process.stdin.write(b"q\n")
                process.stdin.flush()
            process.wait(timeout=8)
        except Exception:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _set_record_error(self, message):
        self.state.set_error(self.cam["id"], message)

        now = time.monotonic()
        if now - self.last_error_sound_mono < RECORD_ERROR_SOUND_INTERVAL_SECONDS:
            return

        self.last_error_sound_mono = now
        record_error()

    def _close_session(self, reason=None):
        if self.current_order:
            status = {
                "AUTO": f"REC AUTO STOP {self.current_order}",
                "FAIL": f"REC FAIL {self.current_order}",
            }.get(reason, f"REC STOP {self.current_order}")
            mode = f" ({self.ffmpeg_mode})" if self.ffmpeg_mode else ""
            log(f"{self.cam['name']} {status}{mode}")

        if self.ffmpeg_process is not None:
            self._terminate_ffmpeg_process(self.ffmpeg_process)
            self.ffmpeg_process = None
            self.ffmpeg_mode = ""

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
