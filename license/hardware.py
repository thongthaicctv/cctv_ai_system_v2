import hashlib
import subprocess
import uuid


def _run(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True,creationflags=subprocess.CREATE_NO_WINDOW)
        return output.decode(errors="ignore").strip().split("\n")[-1].strip()
    except:
        return "UNKNOWN"


def get_cpu_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_Processor).ProcessorId"'
    )


def get_bios_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_BIOS).SerialNumber"'
    )


def get_disk_id():

    return _run(
        'powershell -Command "(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).SerialNumber"'
    )


def get_mac():
    mac = uuid.getnode()
    return ':'.join(f'{(mac >> ele) & 0xff:02x}' for ele in range(40, -8, -8))


def get_hardware_string():
    return "|".join([
        get_cpu_id(),
        get_bios_id(),
        get_disk_id(),
        get_mac()
    ])


def get_hardware_hash():
    raw = get_hardware_string()
    return hashlib.sha256(raw.encode()).hexdigest()


def get_device_id():
    hw = get_hardware_hash().upper()

    return f"CCTV-{hw[:4]}-{hw[4:8]}-{hw[8:12]}"