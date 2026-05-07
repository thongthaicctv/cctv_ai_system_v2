from datetime import datetime

from .hardware import get_hardware_hash, get_device_id
from .cache_manager import CacheManager
from .anti_rollback import AntiRollback


class LicenseManager:

    def __init__(self):

        self.device_id = get_device_id()
        self.hardware_hash = get_hardware_hash()

        self.data = None

    def load(self):

        data = CacheManager.load()

        if not data:
            data = CacheManager.create_default(
                self.device_id,
                self.hardware_hash
            )

        self.data = data

        return data

    def verify_hardware(self):

        if not self.data:
            return False

        return self.data.get("hardware_hash") == self.hardware_hash

    def verify_expire(self):

        expire = datetime.fromisoformat(self.data["expire_date"])

        return datetime.now() <= expire

    def verify_offline_days(self):

        last_sync = datetime.fromisoformat(self.data["last_sync"])

        days = (datetime.now() - last_sync).days

        return days <= 30

    def verify_time_rollback(self):

        return not AntiRollback.is_time_invalid(
            self.data["last_run_time"]
        )

    def update_last_run(self):

        self.data["last_run_time"] = str(datetime.now())

        CacheManager.save(self.data)

    def check(self):

        self.load()

        if not self.verify_hardware():
            return False, "LICENSE HARDWARE INVALID"

        return True, "LICENSE OK"