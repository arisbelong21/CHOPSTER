"""Audit runtime Milestone 2 — run with: python audit_m2.py"""
import sys, os, time, json, threading, subprocess, pathlib, traceback
ROOT = pathlib.Path(__file__).resolve().parent
PARENT = ROOT.parent
for p in (str(PARENT), str(ROOT)):
    if p not in sys.path: sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

print("ENV:", sys.executable, sys.version.split()[0])
import importlib
for mod in ["PySide6","yt_dlp"]:
    try:
        m=importlib.import_module(mod)
        v=getattr(getattr(m,"version",""),"__version__",None) or getattr(m,"__version__","?")
        print(mod, v)
    except Exception as e:
        print(mod, "ERR", e)
from chopster.app.paths import app_dir, user_data_dir
print("app_dir", app_dir(), "exists main.py", (app_dir()/"main.py").exists())
from chopster.downloader.validators import valid_url, detect_platform, clean_urls
from chopster.downloader.ffmpeg import find_ffmpeg
print("ffmpeg", find_ffmpeg())

# --- 1. Thread safety test: QTimer.singleShot from worker thread ---
print("\n[TEST 1] QTimer.singleShot thread safety")
try:
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtCore import QTimer
    app = QApplication.instance() or QApplication(sys.argv)
    label = QLabel("awal")
    label.show()
    result={"done":False}
    def worker():
        QTimer.singleShot(0, lambda: (label.setText("dari worker"), result.update(done=True)))
    t=threading.Thread(target=worker, daemon=True)
    t.start()
    # pump events
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
        if result["done"] and label.text()=="dari worker":
            break
    print("label.text()=", label.text(), "result", result, "PASS" if label.text()=="dari worker" else "FAIL")
    app.quit()
except Exception as e:
    print("FAIL", e); traceback.print_exc()

# --- 2. DownloaderPage preview with mocked yt_dlp ---
print("\n[TEST 2] Preview metadata (mocked yt_dlp) — QTimer path")
try:
    os.environ["QT_QPA_PLATFORM"]="offscreen"
    from unittest.mock import MagicMock, patch
    from PySide6.QtWidgets import QApplication
    from chopster.app.application import Application as CoreApp
    from chopster.ui.pages.downloader_page import DownloaderPage
    app_qt = QApplication.instance() or QApplication(sys.argv)
    core = CoreApp()
    # mock yt_dlp.YoutubeDL
    mock_info_success = {"title":"Video Tes","duration":65, "extractor":"youtube"}
    mock_info_fail_exc = Exception("Video unavailable")
    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def extract_info(self, url, download=False):
            if "fail" in url: raise mock_info_fail_exc
            return mock_info_success
    with patch("yt_dlp.YoutubeDL", FakeYDL):
        page = DownloaderPage(core, theme="dark")
        page.url_edit.setPlainText("https://www.youtube.com/watch?v=ok123\nhttps://example.com/fail123")
        page._preview()
        # pump
        for _ in range(40):
            app_qt.processEvents(); time.sleep(0.05)
        # check queue rows appeared via safe path
        rows = page.queue.rowCount()
        print(f"rows after preview: {rows}")
        for r in range(rows):
            vals=[page.queue.item(r,c).text() if page.queue.item(r,c) else "" for c in range(5)]
            print(f" row {r}:", vals)
        print("preview PASS" if rows==2 else "preview FAIL")
        print("status_label", page.status_label.text(), "_running", page._running)
        # also check _safe_* direct call from thread
        page2=DownloaderPage(core, theme="dark")
        def bg():
            page2._safe_add_row(1,"YouTube","Judul BG","0:30","Siap")
            page2._safe_log("log dari bg")
        threading.Thread(target=bg, daemon=True).start()
        for _ in range(20):
            app_qt.processEvents(); time.sleep(0.03)
        print(f"direct _safe_add_row rows={page2.queue.rowCount()} {'PASS' if page2.queue.rowCount()==1 else 'FAIL'}")
    core.shutdown()
    app_qt.quit()
except Exception as e:
    print("FAIL", e); traceback.print_exc()

# --- 3. Download batch + cancel + partial fail (mocked download_one) ---
print("\n[TEST 3] Download batch parallel + cancel + partial fail (mock)")
try:
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication
    from chopster.app.application import Application as CoreApp
    from chopster.ui.pages.downloader_page import DownloaderPage
    import chopster.downloader.engine as eng
    app_qt = QApplication.instance() or QApplication(sys.argv)
    core = CoreApp()
    # Patch eng.download_one to simulate delay and failure
    orig_download_one = eng.download_one
    def fake_download_one(idx, url, config, progress_hook=None, retry_mode=False):
        time.sleep(0.3)
        if "fail" in url:
            raise RuntimeError("Simulated network fail")
        # simulate progress hook calls
        if progress_hook:
            progress_hook({"status":"downloading","_percent_str":" 50.0%"})
            progress_hook({"status":"finished","filename":f"/tmp/clip{idx}.mp4"})
        return {"idx":idx,"url":url,"title":f"Title {idx}","filepath":f"/tmp/out{idx}.mp4","platform":"YouTube"}
    with patch.object(eng, "download_one", side_effect=fake_download_one):
        page = DownloaderPage(core, theme="dark")
        urls=["https://a.com/v1","https://a.com/fail2","https://a.com/v3"]
        page.url_edit.setPlainText("\n".join(urls))
        page._download()
        # let it run a bit then cancel
        time.sleep(0.2)
        # do NOT cancel first — let partial fail test run fully
        for _ in range(40):
            app_qt.processEvents(); time.sleep(0.05)
            if not page._running:
                break
        print("after batch _running", page._running, "progress", page.progress.value())
        print("rows", page.queue.rowCount())
        for r in range(page.queue.rowCount()):
            vals=[page.queue.item(r,c).text() if page.queue.item(r,c) else "" for c in range(5)]
            print(" ", vals)
        # history should have 3 entries
        hist = core.db.list_history(limit=10)
        print("history count", len(hist), "statuses", [h["status"] for h in hist[:3]])
        print("partial fail PASS" if page.queue.rowCount()==3 else "FAIL")
    # cancel test
    with patch.object(eng, "download_one", side_effect=fake_download_one):
        page2 = DownloaderPage(core, theme="dark")
        page2.url_edit.setPlainText("https://a.com/v1\nhttps://a.com/v2\nhttps://a.com/v3")
        page2._download()
        time.sleep(0.05)
        page2._cancel()
        print("after _cancel _cancel_flag", getattr(page2,"_cancel_flag",None), "cancel_btn enabled", page2.cancel_btn.isEnabled(), "status", page2.status_label.text())
        for _ in range(30):
            app_qt.processEvents(); time.sleep(0.05)
        print("after cancel pump _running", page2._running, "cancel still?", getattr(page2,"_cancel_flag",None))
    core.shutdown()
    app_qt.quit()
except Exception as e:
    print("FAIL", e); traceback.print_exc()

# --- 4. Browser bridge end-to-end to queue ---
print("\n[TEST 4] Browser bridge -> MainWindow -> DownloaderPage queue")
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from chopster.app.application import Application as CoreApp
    from chopster.ui.main_window import MainWindow
    import urllib.request, json as js
    app_qt = QApplication.instance() or QApplication(sys.argv)
    core = CoreApp()
    win = MainWindow(core)
    core.window = win
    win.show()
    port = core.ensure_bridge()
    print("bridge port", port)
    # give event loop a tick
    for _ in range(5):
        app_qt.processEvents(); time.sleep(0.05)
    # POST via urllib
    url_to_send = "https://www.youtube.com/watch?v=bridge_test_123"
    data = js.dumps({"url": url_to_send}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/add", data=data, headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as r:
        body=r.read().decode()
        print("POST /add status", r.status, body[:100])
    # pump QTimer dispatch
    for _ in range(20):
        app_qt.processEvents(); time.sleep(0.05)
    # check downloader page url_edit and queue
    dl = win.page_downloader
    print("url_edit contains bridge url?", url_to_send in dl.url_edit.toPlainText())
    print("url_count", dl.url_count.text())
    print("active workspace", core.config.get("last_workspace"))
    # send duplicate
    with urllib.request.urlopen(req, timeout=3) as r2:
        print("duplicate POST", r2.status)
    for _ in range(10):
        app_qt.processEvents(); time.sleep(0.03)
    # count occurrences in url_edit
    cnt = dl.url_edit.toPlainText().count(url_to_send)
    print(f"duplicate dedup count={cnt} {'PASS' if cnt==1 else 'FAIL'}")
    # GET /add?url= variant
    import urllib.parse
    q = urllib.parse.quote(url_to_send+"2", safe="")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/add?url={q}", timeout=3) as r3:
        print("GET /add?url status", r3.status)
    for _ in range(10):
        app_qt.processEvents(); time.sleep(0.03)
    print("after GET url_edit has second?", (url_to_send+"2") in dl.url_edit.toPlainText())
    # invalid URL
    bad = js.dumps({"url":"notaurl"}).encode()
    req_bad = urllib.request.Request(f"http://127.0.0.1:{port}/add", data=bad, headers={"Content-Type":"application/json"}, method="POST")
    try:
        urllib.request.urlopen(req_bad, timeout=3)
        print("bad url POST should have failed but got 200 FAIL")
    except urllib.error.HTTPError as he:
        print("bad url POST correctly 400", he.code, "PASS" if he.code==400 else "FAIL")
    win.close()
    core.shutdown()
    app_qt.quit()
except Exception as e:
    print("FAIL", e); traceback.print_exc()

print("\nAUDIT DONE")
