# FILE: core/runtime_state.py
# STEP 2 - CAMERA STATE ENGINE FULL

from datetime import datetime


class RuntimeState:

    def __init__(self):
        self.states = {}

    # ==========================================
    # INIT CAMERA
    # ==========================================
    def add_camera(self, cam_id):
        if cam_id not in self.states:
            self.states[cam_id] = self.default_state()

    def remove_camera(self, cam_id):
        if cam_id in self.states:
            del self.states[cam_id]

    def default_state(self):
        return {
            "online": False,
            "status": "CHECKING",
            "latency": 0,
            "last_check": "-",

            "recording": False,
            "employee_id": "",
            "employee_name": "",
            "order_code": "",
            "shift_code": "",

            "video_file": "",
            "employee_started_at": "",
            "started_at": "",
            "stopped_at": "",

            "scan_text": "",
            "error": ""
        }

    # ==========================================
    # GET
    # ==========================================
    def get(self, cam_id):
        self.add_camera(cam_id)
        return self.states[cam_id]

    def all(self):
        return self.states

    # ==========================================
    # NETWORK STATUS
    # ==========================================
    def update_network(
        self,
        cam_id,
        online=False,
        latency=0
    ):
        self.add_camera(cam_id)

        self.states[cam_id]["online"] = online
        self.states[cam_id]["latency"] = latency
        self.states[cam_id]["last_check"] = datetime.now().strftime("%H:%M:%S")

        self._refresh_status(cam_id)

    def _refresh_status(self, cam_id):
        st = self.states[cam_id]

        if st["recording"]:
            st["status"] = "RECORDING"
        elif st["employee_id"]:
            st["status"] = "WORKING"
        else:
            st["status"] = "ONLINE" if st["online"] else "OFFLINE"

    # ==========================================
    # ASSIGN EMPLOYEE
    # ==========================================
    def assign_employee(
        self,
        cam_id,
        employee_id="",
        employee_name="",
        shift_code=""
    ):
        self.add_camera(cam_id)

        st = self.states[cam_id]

        st["employee_id"] = employee_id
        st["employee_name"] = employee_name
        st["shift_code"] = shift_code
        st["employee_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not st["recording"]:
            st["order_code"] = ""
            st["video_file"] = ""
            st["started_at"] = ""
            st["stopped_at"] = ""

        self._refresh_status(cam_id)

    # ==========================================
    # START RECORD
    # ==========================================
    def start_record(
        self,
        cam_id,
        employee_id="",
        employee_name="",
        order_code="",
        shift_code=""
    ):
        self.add_camera(cam_id)

        st = self.states[cam_id]

        st["recording"] = True
        st["status"] = "RECORDING"

        if employee_id:
            st["employee_id"] = employee_id
        if employee_name:
            st["employee_name"] = employee_name
        if shift_code:
            st["shift_code"] = shift_code

        st["order_code"] = order_code
        st["video_file"] = ""

        st["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st["stopped_at"] = ""

    # ==========================================
    # STOP RECORD
    # ==========================================
    def stop_record(self, cam_id, clear_employee=False):
        self.add_camera(cam_id)

        st = self.states[cam_id]

        st["recording"] = False
        st["stopped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        st["order_code"] = ""
        st["video_file"] = ""

        if clear_employee:
            st["employee_id"] = ""
            st["employee_name"] = ""
            st["shift_code"] = ""
            st["employee_started_at"] = ""

        self._refresh_status(cam_id)

    # ==========================================
    # SCAN QR TEXT
    # ==========================================
    def set_scan(self, cam_id, text):
        self.add_camera(cam_id)
        self.states[cam_id]["scan_text"] = text

    # ==========================================
    # VIDEO FILE
    # ==========================================
    def set_video(self, cam_id, file_path):
        self.add_camera(cam_id)
        self.states[cam_id]["video_file"] = file_path

    # ==========================================
    # ERROR
    # ==========================================
    def set_error(self, cam_id, msg):
        self.add_camera(cam_id)
        self.states[cam_id]["error"] = msg

    def clear_error(self, cam_id):
        self.add_camera(cam_id)
        self.states[cam_id]["error"] = ""
