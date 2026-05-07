import json
import re
import threading

import cv2

from core.gpu_acceleration import opencl_processing_enabled, to_host_array, to_processing_buffer

try:
    from pyzbar.pyzbar import ZBarSymbol, decode as zbar_decode
except Exception:
    ZBarSymbol = None
    zbar_decode = None


FIELD_ALIASES = {
    "EMP": "employee_id",
    "EMPLOYEE": "employee_id",
    "EMPLOYEE_ID": "employee_id",
    "ID": "employee_id",
    "NAME": "employee_name",
    "EMPLOYEE_NAME": "employee_name",
    "ORDER": "order_code",
    "ORDER_CODE": "order_code",
    "SHIFT": "shift_code",
    "SHIFT_CODE": "shift_code",
}

_THREAD_LOCAL = threading.local()


def _as_gray(frame):
    if frame is None or frame.size == 0:
        return None

    if len(frame.shape) == 2:
        return frame

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _decode_variants(frame):
    gray = _as_gray(frame)
    if gray is None:
        return []

    h, w = gray.shape[:2]
    if opencl_processing_enabled():
        try:
            return _decode_variants_opencl(gray, h, w)
        except cv2.error:
            pass
        except Exception:
            pass

    return _decode_variants_cpu(gray, h, w)


def _decode_variants_cpu(gray, h, w):
    variants = [gray]

    if min(h, w) < 360 and max(h, w) <= 700:
        variants.append(
            cv2.resize(
                gray,
                None,
                fx=2.0,
                fy=2.0,
                interpolation=cv2.INTER_CUBIC,
            )
        )

    equalized = cv2.equalizeHist(gray)
    variants.append(equalized)

    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    _, otsu = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    variants.append(otsu)
    variants.append(cv2.bitwise_not(otsu))

    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        5,
    )
    variants.append(adaptive)

    return variants


def _decode_variants_opencl(gray, h, w):
    variants = [gray]
    gpu_gray = to_processing_buffer(gray)

    if min(h, w) < 360 and max(h, w) <= 700:
        scaled = cv2.resize(
            gpu_gray,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC,
        )
        variants.append(to_host_array(scaled))

    equalized = cv2.equalizeHist(gpu_gray)
    variants.append(to_host_array(equalized))

    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    _, otsu = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    variants.append(to_host_array(otsu))
    variants.append(to_host_array(cv2.bitwise_not(otsu)))

    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        5,
    )
    variants.append(to_host_array(adaptive))
    return variants


def _clean_text(raw):
    if raw is None:
        return ""

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")

    return str(raw).replace("\x00", "").strip()


def _append_unique(results, text):
    text = _clean_text(text)
    if text and text not in results:
        results.append(text)


def _zbar_symbols(include_barcodes):
    if ZBarSymbol is None:
        return None

    if not include_barcodes:
        return [ZBarSymbol.QRCODE]

    return [
        ZBarSymbol.QRCODE,
        ZBarSymbol.CODE128,
        ZBarSymbol.EAN13,
        ZBarSymbol.EAN8,
        ZBarSymbol.CODE39,
    ]


def _decode_with_zbar(image, include_barcodes):
    if zbar_decode is None:
        return []

    try:
        codes = zbar_decode(image, symbols=_zbar_symbols(include_barcodes))
    except Exception:
        return []

    results = []
    for code in codes:
        _append_unique(results, getattr(code, "data", b""))

    return results


def _decode_with_opencv(image):
    detector = getattr(_THREAD_LOCAL, "qr_detector", None)
    if detector is None:
        detector = cv2.QRCodeDetector()
        _THREAD_LOCAL.qr_detector = detector

    results = []

    if hasattr(detector, "detectAndDecodeMulti"):
        try:
            ok, decoded_info, _points, _straight = detector.detectAndDecodeMulti(image)
            if ok:
                for text in decoded_info:
                    _append_unique(results, text)
        except cv2.error:
            pass

    try:
        text, _points, _straight = detector.detectAndDecode(image)
        _append_unique(results, text)
    except cv2.error:
        pass

    return results


def decode_qr_texts_fast(frame, include_barcodes=False):
    gray = _as_gray(frame)
    if gray is None:
        return []

    results = []

    for text in _decode_with_zbar(gray, include_barcodes):
        _append_unique(results, text)

    if results:
        return results

    if include_barcodes:
        _, threshold = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        for text in _decode_with_zbar(threshold, include_barcodes):
            _append_unique(results, text)

    return results


def decode_qr_texts(frame, include_barcodes=False):
    """
    Return unique decoded QR payloads from a frame.

    The decoder tries raw grayscale, scaled, equalized and thresholded variants.
    pyzbar is preferred when available; OpenCV QRCodeDetector is used as a
    fallback so the app can still scan QR codes without a working zbar runtime.
    """
    results = []
    variants = _decode_variants(frame)

    for image in variants:
        for text in _decode_with_zbar(image, include_barcodes):
            _append_unique(results, text)

        if results and not include_barcodes:
            return results

    for image in variants:
        for text in _decode_with_opencv(image):
            _append_unique(results, text)

        if results and not include_barcodes:
            return results

    return results


def _parse_json_payload(text):
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}

    if not isinstance(payload, dict):
        return {}

    fields = {}
    for key, value in payload.items():
        field = FIELD_ALIASES.get(str(key).strip().upper())
        if field and value is not None:
            fields[field] = str(value).strip()

    return fields


def _parse_key_value_payload(text):
    fields = {}

    for token in re.split(r"[|;,\n]+", text):
        token = token.strip()
        if not token:
            continue

        if ":" in token:
            key, value = token.split(":", 1)
        elif "=" in token:
            key, value = token.split("=", 1)
        else:
            continue

        field = FIELD_ALIASES.get(key.strip().upper())
        value = value.strip()
        if field and value:
            fields[field] = value

    return fields


def parse_qr_command(text):
    text = _clean_text(text)
    upper_text = text.upper()

    if upper_text == "STOP":
        return {
            "action": "stop",
            "raw": text,
        }

    fields = _parse_json_payload(text)
    if not fields:
        fields = _parse_key_value_payload(text)

    employee_id = fields.get("employee_id", "")
    if upper_text.startswith("EMP:") or employee_id:
        if not employee_id and ":" in text:
            employee_id = text.split(":", 1)[1].strip()

        return {
            "action": "employee",
            "raw": text,
            "employee_id": employee_id,
            "employee_name": fields.get("employee_name", ""),
            "shift_code": fields.get("shift_code", ""),
        }

    order_code = fields.get("order_code", "")
    if not order_code:
        order_code = text

    if order_code:
        return {
            "action": "order",
            "raw": text,
            "order_code": order_code,
        }

    return {
        "action": "scan",
        "raw": text,
    }
