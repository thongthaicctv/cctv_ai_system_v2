import os


_ACCELERATION_INFO = None


def _preferred_opencl_vendor():
    try:
        import GPUtil
    except Exception:
        return ""

    try:
        for gpu in GPUtil.getGPUs():
            name = str(getattr(gpu, "name", "")).lower()
            if "nvidia" in name:
                return "NVIDIA"
            if "amd" in name or "radeon" in name:
                return "AMD"
    except Exception:
        return ""

    return ""


def prepare_gpu_runtime():
    os.environ.setdefault("QT_OPENGL", "desktop")
    os.environ.setdefault("OPENCV_DNN_OPENCL_ALLOW_ALL_DEVICES", "1")

    if "OPENCV_OPENCL_DEVICE" not in os.environ:
        vendor = _preferred_opencl_vendor()
        os.environ["OPENCV_OPENCL_DEVICE"] = f"{vendor}:GPU:" if vendor else ":GPU:"


def configure_opencv_acceleration(force=False):
    global _ACCELERATION_INFO

    if _ACCELERATION_INFO is not None and not force:
        return dict(_ACCELERATION_INFO)

    prepare_gpu_runtime()

    import cv2

    info = {
        "mode": "cpu",
        "cuda_devices": 0,
        "opencl_enabled": False,
        "device_name": "",
        "device_vendor": "",
        "is_discrete_gpu": False,
        "message": "OpenCV acceleration: CPU",
    }

    try:
        cuda_count = int(getattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)())
    except Exception:
        cuda_count = 0

    info["cuda_devices"] = cuda_count
    if cuda_count > 0:
        try:
            cv2.cuda.setDevice(0)
        except Exception:
            pass
        info["mode"] = "cuda"
        info["message"] = f"OpenCV acceleration: CUDA ({cuda_count} device)"
        _ACCELERATION_INFO = info
        return dict(info)

    try:
        have_opencl = bool(cv2.ocl.haveOpenCL())
        cv2.ocl.setUseOpenCL(have_opencl)
        use_opencl = bool(cv2.ocl.useOpenCL())
    except Exception:
        have_opencl = False
        use_opencl = False

    if use_opencl:
        try:
            device = cv2.ocl.Device_getDefault()
            device_name = str(device.name())
            device_vendor = str(device.vendorName())
            device_type = int(device.type())
        except Exception:
            device_name = ""
            device_vendor = ""
            device_type = 0

        vendor_lower = device_vendor.lower()
        is_discrete = (
            device_type == getattr(cv2.ocl, "Device_TYPE_DGPU", -1)
            or ("nvidia" in vendor_lower)
            or ("amd" in vendor_lower)
            or ("radeon" in vendor_lower)
        )

        info.update(
            {
                "mode": "opencl",
                "opencl_enabled": True,
                "device_name": device_name,
                "device_vendor": device_vendor,
                "is_discrete_gpu": is_discrete,
            }
        )

        target_label = "dGPU" if is_discrete else "GPU"
        device_label = " / ".join(x for x in (device_vendor, device_name) if x) or "default device"
        info["message"] = f"OpenCV acceleration: OpenCL {target_label} ({device_label})"

    _ACCELERATION_INFO = info
    return dict(info)


def opencl_processing_enabled():
    info = configure_opencv_acceleration()
    return bool(info.get("opencl_enabled"))


def to_processing_buffer(image):
    if image is None or not opencl_processing_enabled():
        return image

    import cv2

    try:
        return cv2.UMat(image)
    except Exception:
        return image


def to_host_array(image):
    if hasattr(image, "get"):
        try:
            return image.get()
        except Exception:
            return image
    return image


def video_capture_params(cv2, open_timeout_msec=None, read_timeout_msec=None):
    params = []

    hw_accel = getattr(cv2, "CAP_PROP_HW_ACCELERATION", None)
    hw_use_opencl = getattr(cv2, "CAP_PROP_HW_ACCELERATION_USE_OPENCL", None)
    accel_any = getattr(cv2, "VIDEO_ACCELERATION_ANY", None)

    if hw_accel is not None and accel_any is not None:
        params.extend([hw_accel, int(accel_any)])

    if hw_use_opencl is not None:
        params.extend([hw_use_opencl, 1])

    open_timeout_prop = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
    if open_timeout_prop is not None and open_timeout_msec is not None:
        params.extend([open_timeout_prop, int(open_timeout_msec)])

    read_timeout_prop = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if read_timeout_prop is not None and read_timeout_msec is not None:
        params.extend([read_timeout_prop, int(read_timeout_msec)])

    return params
