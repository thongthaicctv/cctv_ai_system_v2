"""
video_index_manager.py - Quản lý index video đã ghi
Tạo và cập nhật index.json, sinh index.html để tra cứu/phát video
"""

import json
import os
import glob
from datetime import datetime

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "recordings")
INDEX_JSON = os.path.join(RECORDINGS_DIR, "index.json")
INDEX_HTML = os.path.join(RECORDINGS_DIR, "index.html")


def scan_recordings(recordings_dir=None) -> list:
    """Quét thư mục recordings, trả về danh sách video."""
    base = recordings_dir or RECORDINGS_DIR
    if not os.path.exists(base):
        os.makedirs(base, exist_ok=True)
        return []

    videos = []
    for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
        for fpath in sorted(glob.glob(os.path.join(base, "**", ext), recursive=True)):
            fname = os.path.basename(fpath)
            stat = os.stat(fpath)
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            mtime = datetime.fromtimestamp(stat.st_mtime)

            # Cố gắng parse tên file: camera_YYYYMMDD_HHMMSS.mp4
            camera_id = "unknown"
            date_str = mtime.strftime("%Y-%m-%d")
            time_str = mtime.strftime("%H:%M:%S")
            parts = fname.replace(".mp4", "").replace(".avi", "").replace(".mkv", "").split("_")
            if len(parts) >= 3:
                camera_id = parts[0]
                try:
                    date_str = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
                    time_str = f"{parts[2][:2]}:{parts[2][2:4]}:{parts[2][4:6]}"
                except Exception:
                    pass

            rel_path = os.path.relpath(fpath, base).replace("\\", "/")
            videos.append({
                "filename": fname,
                "path": rel_path,
                "camera_id": camera_id,
                "date": date_str,
                "time": time_str,
                "size_mb": size_mb,
                "timestamp": mtime.isoformat()
            })
    return videos


def build_index(recordings_dir=None) -> dict:
    """Tạo index.json từ danh sách video quét được."""
    base = recordings_dir or RECORDINGS_DIR
    videos = scan_recordings(base)
    index = {
        "generated_at": datetime.now().isoformat(),
        "total": len(videos),
        "recordings_dir": base,
        "videos": videos
    }
    idx_path = os.path.join(base, "index.json")
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return index


def load_index(recordings_dir=None) -> dict:
    """Tải index.json, tự động rebuild nếu chưa có."""
    base = recordings_dir or RECORDINGS_DIR
    idx_path = os.path.join(base, "index.json")
    if not os.path.exists(idx_path):
        return build_index(base)
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return build_index(base)


def generate_html_report(recordings_dir=None):
    """Tạo file index.html tra cứu và phát video."""
    base = recordings_dir or RECORDINGS_DIR
    index = build_index(base)
    videos = index.get("videos", [])

    rows = ""
    for v in videos:
        rows += f"""
        <tr>
          <td><span class="cam-badge">{v['camera_id']}</span></td>
          <td>{v['date']}</td>
          <td>{v['time']}</td>
          <td>{v['size_mb']} MB</td>
          <td>{v['filename']}</td>
          <td>
            <button class="btn-play" onclick="playVideo('{v['path']}','{v['filename']}')">▶ Phát</button>
            <a class="btn-dl" href="{v['path']}" download="{v['filename']}">⬇ Tải</a>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📹 CCTV – Tra cứu Video</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Thai:wght@300;400;600&display=swap');
  :root {{
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --accent: #00b4d8; --accent2: #90e0ef; --text: #e6edf3;
    --muted: #7d8590; --green: #3fb950; --red: #f85149; --orange: #d29922;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'IBM Plex Sans Thai', sans-serif; min-height: 100vh; }}
  header {{
    background: var(--panel); border-bottom: 1px solid var(--border);
    padding: 18px 32px; display: flex; align-items: center; gap: 16px;
  }}
  header h1 {{ font-size: 1.25rem; font-weight: 600; letter-spacing: .03em; }}
  header span {{ color: var(--accent); font-family: 'IBM Plex Mono', monospace; font-size: .85rem; }}
  .stats {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .stat-card {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 22px; min-width: 140px;
  }}
  .stat-card .val {{ font-size: 1.8rem; font-weight: 600; color: var(--accent); font-family: 'IBM Plex Mono', monospace; }}
  .stat-card .lbl {{ font-size: .78rem; color: var(--muted); margin-top: 2px; }}
  .controls {{ padding: 0 32px 16px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
  .controls input {{
    background: var(--panel); border: 1px solid var(--border); color: var(--text);
    padding: 8px 14px; border-radius: 6px; font-size: .9rem; width: 260px;
    font-family: inherit; outline: none;
  }}
  .controls input:focus {{ border-color: var(--accent); }}
  .controls select {{
    background: var(--panel); border: 1px solid var(--border); color: var(--text);
    padding: 8px 12px; border-radius: 6px; font-size: .9rem; cursor: pointer;
    font-family: inherit; outline: none;
  }}
  .btn-rebuild {{
    background: var(--accent); color: #000; font-weight: 600;
    border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: .88rem;
  }}
  .table-wrap {{ padding: 0 32px 40px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  thead tr {{ background: var(--panel); border-bottom: 2px solid var(--border); }}
  th {{ padding: 10px 14px; text-align: left; color: var(--muted); font-weight: 600;
       text-transform: uppercase; letter-spacing: .06em; font-size: .75rem; }}
  tbody tr {{ border-bottom: 1px solid var(--border); transition: background .15s; }}
  tbody tr:hover {{ background: rgba(0,180,216,.05); }}
  td {{ padding: 10px 14px; vertical-align: middle; }}
  .cam-badge {{
    background: rgba(0,180,216,.15); color: var(--accent); border: 1px solid var(--accent);
    padding: 2px 8px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; font-size: .8rem;
  }}
  .btn-play {{
    background: var(--green); color: #000; border: none; padding: 5px 12px;
    border-radius: 5px; cursor: pointer; font-weight: 600; font-size: .82rem; margin-right: 6px;
  }}
  .btn-dl {{
    background: var(--panel); color: var(--accent2); border: 1px solid var(--border);
    padding: 5px 12px; border-radius: 5px; text-decoration: none; font-size: .82rem; font-weight: 600;
  }}
  .btn-dl:hover {{ border-color: var(--accent); }}
  #no-result {{ text-align: center; padding: 40px; color: var(--muted); display: none; }}
  /* Modal player */
  #modal {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.85); z-index:999; align-items:center; justify-content:center; }}
  #modal.open {{ display:flex; }}
  .modal-box {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 24px; max-width: 860px; width: 95%; position: relative;
  }}
  .modal-box h3 {{ font-size: .95rem; margin-bottom: 14px; color: var(--accent2); font-family: 'IBM Plex Mono', monospace; }}
  .modal-box video {{ width: 100%; border-radius: 6px; background: #000; max-height: 480px; }}
  .close-btn {{
    position: absolute; top: 12px; right: 14px; background: var(--red);
    color: #fff; border: none; border-radius: 50%; width: 28px; height: 28px;
    cursor: pointer; font-size: 1rem; font-weight: 700; line-height: 28px; text-align: center;
  }}
  .generated {{ padding: 0 32px 10px; color: var(--muted); font-size: .75rem; font-family: 'IBM Plex Mono', monospace; }}
</style>
</head>
<body>
<header>
  <div>📹</div>
  <div>
    <h1>CCTV AI System – Tra cứu Video</h1>
    <span>recordings / index.html</span>
  </div>
</header>

<div class="stats">
  <div class="stat-card"><div class="val" id="stat-total">{index['total']}</div><div class="lbl">Tổng video</div></div>
  <div class="stat-card"><div class="val" id="stat-filtered">—</div><div class="lbl">Kết quả lọc</div></div>
  <div class="stat-card"><div class="val" id="stat-size">0</div><div class="lbl">Tổng dung lượng</div></div>
</div>

<div class="controls">
  <input type="text" id="search" placeholder="🔍 Tìm camera ID, ngày, tên file..." oninput="filterTable()">
  <select id="filter-cam" onchange="filterTable()">
    <option value="">Tất cả camera</option>
    {''.join(f'<option value="{c}">{c}</option>' for c in sorted(set(v['camera_id'] for v in videos)))}
  </select>
  <input type="date" id="filter-date" onchange="filterTable()">
  <button class="btn-rebuild" onclick="window.location.reload()">🔄 Làm mới</button>
</div>

<div class="table-wrap">
  <table id="vtable">
    <thead>
      <tr>
        <th>Camera</th><th>Ngày</th><th>Giờ</th><th>Dung lượng</th><th>Tên file</th><th>Hành động</th>
      </tr>
    </thead>
    <tbody id="tbody">
      {rows if rows else '<tr><td colspan="6" style="text-align:center;padding:40px;color:#7d8590">Chưa có video nào. Hãy bắt đầu ghi hình.</td></tr>'}
    </tbody>
  </table>
  <div id="no-result">Không tìm thấy video nào phù hợp.</div>
</div>

<div class="generated">Cập nhật lúc: {index['generated_at']}</div>

<!-- Modal video player -->
<div id="modal">
  <div class="modal-box">
    <button class="close-btn" onclick="closeModal()">✕</button>
    <h3 id="modal-title"></h3>
    <video id="modal-video" controls autoplay></video>
  </div>
</div>

<script>
const allRows = Array.from(document.querySelectorAll('#tbody tr'));
let totalSize = {sum(v['size_mb'] for v in videos):.1f};
document.getElementById('stat-size').textContent = totalSize + ' MB';
document.getElementById('stat-filtered').textContent = allRows.length;

function filterTable() {{
  const kw = document.getElementById('search').value.toLowerCase();
  const cam = document.getElementById('filter-cam').value.toLowerCase();
  const date = document.getElementById('filter-date').value;
  let count = 0; let size = 0;
  allRows.forEach(row => {{
    const text = row.textContent.toLowerCase();
    const rowCam = row.querySelector('.cam-badge')?.textContent.toLowerCase() || '';
    const cells = row.querySelectorAll('td');
    const rowDate = cells[1]?.textContent || '';
    const rowSize = parseFloat(cells[3]?.textContent) || 0;
    const show = (!kw || text.includes(kw))
               && (!cam || rowCam === cam)
               && (!date || rowDate === date);
    row.style.display = show ? '' : 'none';
    if (show) {{ count++; size += rowSize; }}
  }});
  document.getElementById('stat-filtered').textContent = count;
  document.getElementById('stat-size').textContent = size.toFixed(1) + ' MB';
  document.getElementById('no-result').style.display = count === 0 ? 'block' : 'none';
}}

function playVideo(path, name) {{
  document.getElementById('modal-title').textContent = '▶ ' + name;
  document.getElementById('modal-video').src = path;
  document.getElementById('modal').classList.add('open');
}}
function closeModal() {{
  document.getElementById('modal').classList.remove('open');
  const v = document.getElementById('modal-video');
  v.pause(); v.src = '';
}}
document.getElementById('modal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});
</script>
</body>
</html>"""

    html_path = os.path.join(base, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


# Alias for compatibility
scan_and_build_index = build_index
