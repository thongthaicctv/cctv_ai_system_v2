import os
import json
from datetime import datetime, timedelta


VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov")


def cleanup_index_and_video_sync(storage_path: str, keep_days: int, enabled: bool):
    """
    Chỉ chạy khi enabled=True.
    Xoá đồng bộ:
    - đọc index/YYYY-MM-DD.json cũ
    - xoá toàn bộ video được ghi trong index đó
    - xoá file index đó
    """

    if not enabled:
        print("[CLEANUP] Disabled")
        return

    if keep_days <= 0:
        return

    index_dir = os.path.join(storage_path, "index")

    if not os.path.exists(index_dir):
        return

    limit_date = datetime.now() - timedelta(days=keep_days)

    for file_name in os.listdir(index_dir):
        if not file_name.endswith(".json"):
            continue

        date_str = file_name.replace(".json", "")

        try:
            index_date = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue

        if index_date >= limit_date:
            continue

        index_path = os.path.join(index_dir, file_name)

        # 1. Đọc index để lấy danh sách video cần xoá
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[CLEANUP] Read index failed: {index_path} | {e}")
            continue

        videos = data.get("videos", [])

        # 2. Xoá video nằm trong index
        for v in videos:
            rel_path = (
                v.get("video_path")
                or v.get("file_path")
                or v.get("path")
                or v.get("filename")
                or ""
            )

            if not rel_path:
                continue

            video_path = rel_path.replace("\\", "/")

            if not os.path.isabs(video_path):
                video_path = os.path.join(storage_path, video_path)

            video_path = os.path.normpath(video_path)

            if not video_path.lower().endswith(VIDEO_EXTS):
                continue

            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    print(f"[CLEANUP] Deleted video: {video_path}")
                except Exception as e:
                    print(f"[CLEANUP] Delete video failed: {video_path} | {e}")

        # 3. Xoá index sau khi xoá video
        try:
            os.remove(index_path)
            print(f"[CLEANUP] Deleted index: {index_path}")
        except Exception as e:
            print(f"[CLEANUP] Delete index failed: {index_path} | {e}")

    _remove_empty_dirs(storage_path)


def _remove_empty_dirs(storage_path: str):
    for root, dirs, files in os.walk(storage_path, topdown=False):
        if root == storage_path:
            continue

        try:
            if not os.listdir(root):
                os.rmdir(root)
                print(f"[CLEANUP] Removed empty folder: {root}")
        except Exception:
            pass