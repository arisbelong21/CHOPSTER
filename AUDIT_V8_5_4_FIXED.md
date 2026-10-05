# Chopster v8.5.4 — Audit & Perbaikan (Master Analysis / Camera Director)

> **Catatan re-audit 2026-10-05:** pemeriksaan lanjutan menemukan bahwa pemeriksaan build terdahulu hanya mengecek sintaks/nama aset, bukan menyelesaikan path sumber relatif yang dipakai PyInstaller. Karena itu, bagian kesiapan EXE di bawah ini superseded oleh `AUDIT_8.5.4_BUILD_FIX_ID.md`; path spec dan pemilihan Python build telah diperbaiki di paket tersebut. Build Windows final belum dijalankan.

Tanggal audit: 2026-10-05
Cakupan: seluruh paket Chopster 8.5.4 — fokus pada fitur **Master Analysis** untuk **Camera Director** plus area lain yang diperiksa.

## Ringkasan Hasil Audit

| Area | Status audit | Kesimpulan |
| --- | --- | --- |
| Master Analysis (clipper/master_analysis.py) | Defensif, semua jalur punya fallback | 1 bug nyata ditemukan & diperbaiki (cache transcript) |
| Camera Director (clipper/camera_director.py) | Logika shot-lock, hysteresis, easing benar | Tidak ditemukan crash; kasus kosong/salah JSON aman |
| Person/Face tracking (clipper/face_tracking.py) | Robust | 1 bug kecil (event progress ganda) diperbaiki |
| Adaptive framing / Visual analyzer / Scene vision | Benar | Tidak ada bug kritis |
| AI Orchestrator & provider (embedded Gemini + Settings AI) | Circuit breaker + fallback lokal OK | Tidak ada bug kritis |
| Downloader / Auto Clip Studio | Sesuai perbaikan audit sebelumnya | Tidak ada regresi baru |
| Script tes `.bat` | **Rusak** (rujuk file tes yang tidak ada) | Diperbaiki |
| Test suite Python | 15 tes lama lulus | +17 tes regresi baru (total 32 lulus) |
| compileall seluruh proyek | LULUS | — |

## Temuan & Perbaikan yang Diterapkan

### 1. [DIPERBAIKI] Cache transcript Master Analysis tidak mengikuti pengaturan model/language/word-timestamp
- **Lokasi:** `clipper/master_analysis.py`, blok Transcript.
- **Gejala:** Artifact transcript proyek hanya dikunci oleh tanda tangan file sumber. Jika pengguna mengganti model Whisper / bahasa / word-timestamp lalu menjalankan “Master Analysis” lagi, transcript lama tetap dipakai tanpa transkripsi ulang, sehingga pilihan model di UI tidak berpengaruh dan word-timestamp bisa basi (mempengaruhi subtitle cues).
- **Bukti:** simulasi run-1 (model tiny) → run-2 (model small). Sebelum perbaikan: `transcribe calls = 1` (transcript lama dipakai). Sesudah perbaikan: `transcribe calls = 2` dan isi transcript berubah sesuai model baru.
- **Perbaikan:** artifact transcript kini menyimpan `_transcribe_provenance` (model, language, word_timestamps, device). Jika provenance tidak cocok dengan pengaturan yang diminta, Master Analysis melewati cache proyek dan memakai cache global per-model; bila kosong, transkripsi ulang. Artifact lama tanpa provenance tetap dipakai (kompatibel mundur).

### 2. [DIPERBAIKI] Event progress ganda di face/body tracking
- **Lokasi:** `clipper/face_tracking.py` (sebelumnya 2 baris `progress_cb(100, ...)` berurutan, sekarang 1).
- **Gejala:** UI menerima event “subject map siap” dua kali di akhir tracking.
- **Perbaikan:** hapus duplikat.

### 3. [DIPERBAIKI] Script tes `.bat` menunjuk file tes yang tidak ada
- **Gejala:** `test_camera_pipeline_v84.bat` dan `test_dual_ai_windows.bat` merujuk `test_v84_camera_ai_move.py`, `test_camera_director.py`, `test_dual_ai_vision_final.py`, `test_ai_vision_integration.py`, `test_ai_failover.py`, `test_full_ai_integration.py` — semuanya tidak ada di paket (hanya `tests/test_audit_regressions.py` yang ada). Script langsung gagal.
- **Perbaikan:** kedua `.bat` kini menjalankan `tests/test_camera_director.py` + `tests/test_audit_regressions.py`.

## Verifikasi

- `python -m unittest discover -s tests`: **32 tes lulus** (15 lama + 17 baru).
- `python -m compileall -q .`: **lulus**.
- Tes baru `tests/test_camera_director.py`: normalize/clamp/dedup, stabilisasi shot-lock, clip-relative, interpolasi, `ai_camera_director_visual` (JSON valid/malformed/kosong), mapping target AI → ID tracker lokal, signature AI, dan regresi provenance transcript (model berubah → transkripsi ulang; pengaturan sama → reuse cache).

## Catatan / batasan lingkungan audit

- `PySide6`, `OpenCV`, `FFmpeg`/`FFprobe` dan model Whisper tidak tersedia di lingkungan audit ini, jadi UI Qt, tracking nyata, dan render nyata tidak dapat dijalankan langsung. Audit UI/worker dilakukan statis (semua modul berhasil diimpor, compileall lulus). Uji nyata di Windows tetap disarankan: `install_dependencies.bat` lalu `run_chopster.bat`.
- **Cache kamera sengaja tidak memakai AI signature** (hanya target_aspect/mode/version) untuk menghindari komputasi ulang murah. Efek sampingnya: mengubah pengaturan AI (model/vision) antara dua Master Analysis tidak memaksa Camera Director AI berjalan ulang; gunakan ubah aspek/mode atau hapus `analysis/camera.json` (via force) bila ingin memaksa. Ini keputusan desain yang dipertahankan.
- **Urutan jalur Master Analysis:** Camera Director visual berjalan sebelum `visual_review` tersedia pada run pertama (karena tracking terjadi lebih dulu). Akibatnya `visual_context` belum dikonsumsi pada run yang sama, sementara pada run cache berikutnya ia dilewati karena `ai_shots` sudah ada. Tidak menyebabkan crash/kesalahan output; dicatat untuk penyempurnaan di versi berikutnya agar penghematan panggilan vision dipertimbangkan.

## Audit Kesiapan Build EXE (Chopster.spec / build_exe.bat / path frozen)

### Verifikasi yang lulus

- `Chopster.spec`: sintaks Python valid; aset yang dicek `build_exe.bat` semua tersedia — `web_dist/index.html` + `assets`, `engine/fonts/Anton.ttf`, `engine/cascades/face_detection_yunet.onnx`, `engine/haarcascade_frontalface_default.xml`, `resources/icons/app.ico`, `VERSION.txt`.
- `main.py` menyiapkan `sys.path` sebelum import, `crash_guard` dijalankan, crash log ditulis ke berkas (aman untuk `console=False`).
- `app/paths.py` sudah benar-benar frozen-aware: `app_dir()` = folder EXE, `resource_path()` memakai `sys._MEIPASS`.
- Backend Auto Clip Studio dijalankan **in-process** (uvicorn dalam daemon thread / FastAPI route langsung), bukan subprocess — aman untuk EXE.
- Downloader utama (yt-dlp) memakai **Python API**, bukan `python -m` — aman untuk EXE.
- `build_exe.bat` sudah siap untuk tata letak onedir PyInstaller 6 (`_internal` maupun tanpa), memverifikasi EXE + bundle web/font/model, dan menyalin `deno.exe` di samping EXE bila ada.

### 4. [DIPERBAIKI] `sys.executable` sebagai Python pada build EXE (potensi meluncurkan jendela kedua)
- **Gejala:** di EXE, `sys.executable` adalah aplikasi itu sendiri, bukan `python.exe`. Panggilan `[sys.executable, "-c/-m ...]` akan membuka instansi GUI kedua (window hantu) dan gagal.
- **Lokasi & perbaikan:**
  1. `clipper/transcript_manager.py` — `_cuda_preflight()` kini mendeteksi frozen dan **tidak** menjalankan probe anak `-c`; Device Auto memakai CPU dengan pesan jelas. (mode dev tidak berubah; tes membuktikan subprocess tetap dipanggil saat tidak frozen)
  2. `auto_clip_studio/engine/video_engine.py` — `get_yt_dlp_base_cmd()` di EXE tidak lagi memakai `python -m yt_dlp`; ia mencari `yt-dlp.exe` di samping EXE, dan jika tidak ada memberi error jelas (bukan diam-diam meluncurkan GUI).
  3. `auto_clip_studio/engine/services/youtube_service.py` — fallback CLI `youtube_transcript_api` dilewati pada EXE (jalur in-process API/yt-dlp tetap jalan).
  4. `auto_clip_studio/engine/routers/system.py` — `pip install` (dev-only) dilewati pada EXE.
  5. `auto_clip_studio/engine/services/system_service.py` — `trigger_detached_restart()` (dev-only) dilewati pada EXE.

### 5. [DIPERBAIKI] `python-multipart` tidak ikut ter-bundle (upload file di Auto Clip Studio)
- **Gejala:** engine memakai FastAPI `UploadFile`/`File(...)` di `routers/media.py`. FastAPI memuat `python-multipart` secara lazy, jadi PyInstaller tidak otomatis menyertakannya → endpoint upload bisa error “Form data requires python-multipart” di EXE.
- **Perbaikan:** tambah `'python_multipart'` (plus `'uvicorn'`, `'dotenv'`) ke `hiddenimports` di `Chopster.spec`.

### Verifikasi tambahan (EXE)
- `python -m unittest discover -s tests`: **35 tes lulus** (termasuk tes regresi frozen: CUDA preflight tidak memanggil subprocess saat frozen, guard frozen ada di 4 lokasi risiko).
- `python -m compileall -q .`: **lulus**.
- Simulasi frozen langsung: `_cuda_preflight()` → `(False, "Build EXE: ...")` tanpa `subprocess.run`; `fetch_transcript_cli()` → `[]` tanpa subprocess; `trigger_detached_restart()` → return tanpa `Popen`; `get_yt_dlp_base_cmd()` → error jelas tanpa `-m`.
- **Catatan:** build PyInstaller sendiri tidak dapat dijalankan di lingkungan audit ini (Windows + PyInstaller 6.22.3 diperlukan). Jalankan `build_exe.bat` di PC Windows Anda.
