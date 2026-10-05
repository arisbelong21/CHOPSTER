# Audit dan Perbaikan Build EXE — Chopster 8.5.4

Tanggal pemeriksaan: 5 Oktober 2026  
Batas audit: arsip proyek yang diberikan, skrip build/tes, konfigurasi PyInstaller, jalur startup/frozen yang dapat diverifikasi secara statis. Logika produk, fitur, dan alur penggunaan utama tidak diubah.

## Akar penyebab kegagalan build saat ini (terbukti dari log pengguna)

**Gejala:** `build_exe.bat` berhenti dalam hitungan detik dan tidak pernah memproduksi EXE. Log `build_exe.log` pengguna berhenti pada:

```
========================================
Chopster by Aris - Reproducible EXE build
========================================
tidak was unexpected at this time.
```

**Penyebab:** di dalam blok `if errorlevel 1 ( ... )`, baris
`echo [ERROR] Python Launcher (py) tidak ditemukan.` memuat tanda kurung `(py)` pada teks echo.
Pada `cmd.exe`, tanda kurung dalam teks di dalam blok `if (...)` ikut dihitung sebagai pembuka/penutup blok.
Kurung `)` pada `(py)` menutup blok lebih awal, sehingga sisa token `tidak ditemukan.` terlempar ke level teratas
dan CMD memunculkan *parse error* `tidak was unexpected at this time.`. Ini adalah fatal parse error:
build langsung dibatalkan (≈1 detik), tanpa pesan PyInstaller dan tanpa EXE.

**Perbaikan:** teks echo diubah menjadi `Python Launcher 'py' tidak ditemukan.` (tanpa tanda kurung di dalam blok).
Seluruh skrip batch dipindai ulang; ini satu-satunya baris echo bertanda kurung yang ada di semua `*.bat`.

**Bug sekunder yang juga diperbaiki:** pada cabang `:copy_valid_deno`, baris
`echo ... Node >=22 atau Deno >=2.3.` menggunakan `>` yang tidak di-escape. Di `cmd.exe`, `>` berarti
redirect, bukan "lebih besar dari", sehingga baris itu akan menulis output ke file sampah (`=22` / `=2.3`)
dan pesan tampil salah. Telah di-escape menjadi `^>=` (sama seperti `install_dependencies.bat`).
Cabang ini hanya aktif jika `deno.exe` ada di folder dan gagal validasi; sekarang aman.

> Catatan: menahan jendela CMD (`pause`/log) bukanlah perbaikan — log hanya dipakai agar error yang
> sebenarnya terlihat. Perbaikan nyatanya ada di atas, dan build kini dapat berjalan sampai selesai.

## Blokade kedua yang terbukti (Python 3.12 tidak terpasang)

**Gejala** (dari `build_exe.log` pengguna):
```
[INFO] Membuat virtual environment build Python 3.12...
[ERROR] No runtime installed that matches 3.12. Try running "py install 3.12".
The system cannot find the path specified.
[ERROR] .venv-build bukan Python 3.12 64-bit.
```

**Penyebab:** PC pengguna hanya memiliki Python 3.14
(`...\AppData\Local\Python\pythoncore-3.14-64`). Pemeriksaan lama `py -3.12 --version` **tidak
mendeteksi** runtime yang hilang (PyLauncher mengembalikan sukses untuk `--version` walau 3.12 tidak ada),
sehingga build melaju sampai `py -3.12 -m venv`, yang gagal dan menghentikan build.

**Perbaikan (v6):**
1. Pemeriksaan 3.12 sekarang memakai `py -3.12 -c "import sys"` (benar-benar menjalankan Python), bukan `--version`.
2. Bila 3.12 tidak ada, build **memasangnya otomatis** lewat `py install 3.12` (fitur Python Launcher modern:
   per-user, tanpa hak admin), lalu memeriksanya lagi.
3. Bila 3.12 tetap tidak tersedia (offline/launcher lama), build **memakai interpreter default** yang
   terpasang (3.14) sebagai pengganti — build tidak lagi mati di titik ini.
4. Path interpreter build diambil lewat `sys.executable`, dan tetap diverifikasi **64-bit**.
5. Label `:no_python` memberi pesan gagal yang jelas bila tidak ada Python 64-bit sama sekali.

**Catatan Deno di log pengguna:** file `deno.exe` pada folder `...v5\chopster\deno.exe` berasal dari
ekstraksi lama pengguna — **arsip ZIP v5/v6 tidak memuat `deno.exe`** (sudah diverifikasi). Peringatan itu
nonfatal: installer memakai Node v24.21.0 sebagai pengganti (syarat yt-dlp: Node >=22).

## Temuan lanjutan v7: exit code PyLauncher tidak dapat dipercaya

**Gejala:** pada v6, build berhenti di `Tidak ada interpreter Python 64-bit yang tersedia...` **tanpa ada
satupun baris `[INFO]/[WARN]/[OK]`** sebelumya. Analisis: di mesin pengguna, `py -3.12 <perintah>` dapat
mengembalikan status sukses (exit 0) walau runtime 3.12 tidak terpasang — sama seperti `py -3.12 --version`
yang sempat lolos pada v5 — sehingga langkah deteksi lama `py -3.12 -c "import sys"` dilewati dan probe
path lewat stdout `for /f` tidak menangkap apa pun.

**Perbaikan (v7):**
1. Deteksi 3.12 kini memakai **marker file**: `py -3.12 -c "open(r'...probe','w').write(sys.executable)"`.
   File hanya muncul bila Python 3.12 benar-benar berjalan — tidak bergantung pada exit code launcher.
2. Bila marker tidak ada: coba `py install 3.12` (otomatis, per-user), lalu probe ulang.
3. Bila tetap tidak tersedia: probe interpreter default (`python`, lalu `py`) dengan cara yang sama, dan
   pakai path hasil probe itu. Build tidak lagi macet di titik ini selama ada satu Python 64-bit.
4. Pemeriksaan 64-bit tetap dieksekusi langsung pada `sys.executable` hasil probe.
5. Arsip kini menyertakan **`check_windows_build.ps1`** — diagnostik sekali-jalan (tidak mengubah apa pun)
   untuk melihat di mesin Windows pengguna: daftar runtime `py --list-paths`, perilaku `py` default,
   `python`, dan exit code `py -3.12`. Outputnya wajib dikirim agar status lingkungan PC terverifikasi
   secara nyata, bukan ditebak.

## Kesimpulan singkat

Penyebab kegagalan build yang paling jelas ada di konfigurasi paket, bukan pada alur kerja aplikasi. Berkas yang diunggah **tidak menyertakan EXE atau DLL Windows**, sehingga DLL pada komputer pengguna tidak dapat saya periksa atau ganti secara langsung.

Tangkapan layar menunjukkan aplikasi mencoba memuat `python314.dll` dari direktori `build\...\_internal`. Ini menunjukkan build memakai Python 3.14 dan EXE dijalankan dari direktori kerja/intermediate `build`, bukan lokasi distribusi yang ditetapkan skrip (`dist\Chopster by Aris`). Pesan `LoadLibrary` juga dapat disebabkan dependensi native Windows yang tidak tersedia; penyebab terakhir ini perlu diuji pada PC Windows.

## Temuan kritis yang diperbaiki

1. **Path aset pada `Chopster.spec` salah relatif terhadap lokasi spec.** Spec berada di root paket `chopster`, tetapi beberapa sumber ditulis sebagai `chopster/auto_clip_studio/...`; direktori sumber yang benar relatif terhadap root itu adalah `auto_clip_studio/...`. Akibatnya PyInstaller bisa gagal menemukan aset atau membuat paket yang tidak lengkap. Spec kini memakai path absolut yang dibentuk dari lokasi spec, memasukkan parent paket ke `pathex`, dan menghentikan build bila aset wajib tidak ada.
2. **Build tidak mengunci interpreter.** Skrip lama memilih `python`/`pyinstaller` pertama di PATH. Bukti `python314.dll` konsisten dengan build melalui Python 3.14, tanpa pemeriksaan versi/arsitektur. Skrip baru membuat `.venv-build` dengan Python 3.12 **64-bit**, memasang requirements di lingkungan itu, lalu membangun dari sana.
3. **EXE onedir berpotensi dijalankan dari folder yang salah.** Skrip kini memverifikasi dan menunjukkan EXE pada `dist\Chopster by Aris\Chopster by Aris.exe`, serta mengingatkan bahwa folder `_internal` harus tetap bersama EXE. Direktori `build` bukan folder distribusi.
4. **Nama hidden import dotenv tidak tepat.** Nama modul Python yang benar ialah `dotenv`, bukan `python_dotenv`; spec sudah dikoreksi.
5. **Folder ekstensi browser tidak disalin ke lokasi yang diarahkan UI.** Skrip lama menyertakan aset ekstensi di bundle internal, sedangkan panduan UI meminta folder `browser_extension` di folder build. Build baru menyalin dan memverifikasi folder tersebut di samping EXE pada `dist`.
6. **Dua skrip tes memakai `pytest`, padahal dependency dan tes yang ada menggunakan `unittest`.** Skrip tes kini memakai `unittest discover`; dua skrip diagnostik juga mendapat `PYTHONPATH` yang diperlukan agar impor paket tidak gagal saat dijalankan dari folder proyek.
7. **Proteksi kompresi UPX dimatikan untuk build ini.** Pustaka Python/Qt/CTranslate2 native dibiarkan tanpa kompresi UPX untuk mengurangi risiko pemuatan DLL yang tidak stabil.
8. **Peringatan Deno pada log pengguna bersifat nonfatal.** `deno.exe` ditemukan tetapi gagal menjalankan `--version`; installer lalu memakai Node v24.21.0 yang memenuhi syarat yt-dlp (Node >=22). Skrip build sekarang menguji Deno lokal dan tidak menyertakannya jika rusak/tidak didukung.
9. **Output build harus tetap dapat dianalisis jika konsol Windows hilang.** `build_exe.bat` kini menyimpan seluruh output/exit code pada `build_exe.log`; ini untuk mengidentifikasi akar kegagalan, bukan pengganti perbaikan build.
10. **Bug sintaks batch yang menghentikan build (akar penyebab saat ini).** Teks echo `(py)` di dalam blok `if (...)` membuat CMD menutup blok lebih awal dan menghasilkan fatal parse error `tidak was unexpected at this time.`; build dibatalkan tanpa menghasilkan EXE. Diperbaiki, dan `>` yang tidak di-escape pada pesan deny validasi Deno juga di-escape (`^>=`).
11. **Blokade build karena Python 3.12 tidak terpasang.** Pemeriksaan `--version` lama meloloskan launcher padahal runtime 3.12 tidak ada, lalu `py -3.12 -m venv` gagal. Build kini mengecek lewat marker file (`py -3.12 -c ...` yang benar-benar menuliskan `sys.executable`), memasang 3.12 otomatis dengan `py install 3.12` bila hilang, dan jatuh ke interpreter default bila tetap tidak tersedia — build tidak berhenti di titik ini. (Lihat juga "Temuan lanjutan v7" tentang exit code launcher.)
12. **Backend Auto Clip Studio gagal start di EXE: `unable to configure formatter 'default'`.** Penyebab: backend ter-embed (`auto_clip_studio/web_runtime.py`) memakai `uvicorn.Config(...)` tanpa `log_config`, sehingga uvicorn memakai konfigurasi logging default yang me-resolve formatter lewat string `uvicorn.logging.DefaultFormatter` saat runtime. PyInstaller tidak selalu mendeteksi import berbasis string itu, sehingga resolve gagal di EXE (`unable to configure formatter 'default'`); dari source (run_chopster.bat) submodul tersebut ada sehingga fitur jalan normal. **Perbaikan dua lapis (v9):** (a) `Chopster.spec` menambahkan `collect_submodules("uvicorn")`, `"fastapi"`, `"starlette"`, `"python_multipart"` ke hiddenimports; dan (b) yang lebih menentukan — `web_runtime.py` kini meneruskan `log_config` eksplisit yang memakai `logging.Formatter` langsung (tanpa *string factory* `"()"`), sehingga backend **tidak lagi bergantung** pada `uvicorn.logging` sama sekali. Uji `logging.config.dictConfig` atas konfigurasi baru ini lulus dengan stdlib murni. Perlu rebuild EXE.
13. **Jendela konsol muncul berulang (`C:\Windows\system32\curl.exe`) saat Master Analysis.** Penyebab: aplikasi adalah EXE windowed, dan pipeline memanggil ffmpeg + AI/Gemini berkali-kali. Tiap request AI yang gagal di `urllib` (Cloudflare 403/5xx, timeout, atau koneksi ditolak) jatuh ke fallback `_request_via_curl` di `ai/api_provider.py`, yang menjalankan `curl.exe` (aplikasi konsol) sebagai subprocess. Tanpa flag `CREATE_NO_WINDOW`, setiap spawn memunculkan jendela konsol → selama Master Analysis, jendela curl.exe muncul berulang (sekali per panggilan yang gagal). **Perbaikan (v10):** (a) modul baru `app/winconsole.py` — patch tipis dan aman atas `subprocess.Popen` yang, pada Windows, menyuntikkan `CREATE_NO_WINDOW` ke proses anak kecuali pemanggil eksplisit meminta jendela (`CREATE_NEW_CONSOLE` di tool dev-mode tetap dihormati); dipasang di paling atas `main.py` sehingga menutup semua fitur (downloader ffmpeg/yt-dlp, clipper, Auto Clip Studio, npm/pip/powershell); dan (b) cadangan eksplisit `creationflags=CREATE_NO_WINDOW` pada pemanggilan curl di `api_provider.py`. Di Linux patch ini no-op (terverifikasi) — tidak mengubah alur fitur, hanya menghilangkan kedipan jendela konsol.

Perubahan dibatasi pada packaging/build, skrip pemeriksaan, dokumentasi build, dan label diagnostik. Pipeline download, AI, analisis, editing, render, dan antarmuka tidak diubah.

## Hasil verifikasi

- Arsip input lolos pemeriksaan integritas ZIP.
- **35/35 tes `unittest` lulus** setelah perbaikan.
- `python -m compileall -q .`: lulus untuk seluruh sumber Python.
- `Chopster.spec`: sintaks dan evaluasi statis lulus; 7 kelompok aset sumber wajib ditemukan.
- Bundle frontend, font, model cascade, dan folder ekstensi ada pada paket sumber.
- Pemeriksaan versi proyek dan bundle frontend tetap konsisten pada 8.5.4. ID protokol browser bridge/ekstensi memakai label 8.5.5 di beberapa tempat; saat ini ID aplikasi dan ekstensi saling cocok sehingga ini **bukan penyebab error DLL**, tetapi merupakan ketidakkonsistenan label versi.

## Batasan yang belum dapat dipastikan

Lingkungan pemeriksaan ini Linux dan paket unggahan tidak memuat EXE, `python314.dll`, maupun dependensi Windows. Karena itu saya **tidak dapat membangun atau menjalankan EXE Windows di sini**, dan tidak dapat membuktikan apakah PC masih kekurangan Microsoft Visual C++ runtime atau dependensi DLL lainnya. Build Windows akhir harus dibuat dan diuji di PC Windows.

Jika pesan yang sama tetap muncul setelah memakai hasil di `dist`, instal **Microsoft Visual C++ 2015–2022 Redistributable x64**. Jalankan EXE dari folder `dist\Chopster by Aris` dan jangan memindahkan EXE sendirian dari folder `_internal`.

## Cara menghasilkan EXE yang telah diperbaiki

1. Ekstrak seluruh ZIP perbaikan ke folder baru.
2. Jalankan `build_exe.bat` dari root folder `chopster`. Skrip memakai Python 3.12 64-bit bila ada,
   atau **memasangnya otomatis** dengan `py install 3.12` bila belum ada, atau memakai Python default
   (3.14) sebagai cadangan terakhir; lalu membuat `.venv-build`, memasang dependency, dan menjalankan
   PyInstaller. Output lengkap dan exit code disimpan pada `build_exe.log` di folder yang sama.
3. Jalankan `dist\Chopster by Aris\Chopster by Aris.exe`. Untuk berbagi, kirim seluruh folder `dist\Chopster by Aris`, bukan EXE saja.
4. Bila EXE tetap melaporkan DLL hilang, pasang Microsoft Visual C++ 2015–2022 Redistributable x64 dan
   pastikan seluruh folder `_internal` ikut dipindahkan bersama EXE.
5. Bila build masih berhenti, jalankan `check_windows_build.ps1` (klik kanan → Run with PowerShell)
   dan kirim seluruh outputnya — itu memperlihatkan runtime Python mana yang benar-benar terpasang
   dan bagaimana perilaku `py`/`python` di PC tersebut.

## Ringkasan cakupan

Paket sumber berisi 101 file Python dan 35 tes otomatis. Pemeriksaan ini mencakup startup, jalur frozen EXE, konfigurasi PyInstaller dan aset, skrip batch build/tes, versi, serta beberapa kontrol keamanan yang sudah memiliki tes regresi (TLS, validasi URL lokal/SSRF, dan pembatasan backend localhost). UI Qt, integrasi AI nyata, codec/GPU, dan hasil render video tidak dapat diuji end-to-end pada lingkungan ini.
