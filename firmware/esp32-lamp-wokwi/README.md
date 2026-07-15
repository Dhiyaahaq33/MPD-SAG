# Simulasi Lampu IoT (ESP32 + Relay) via Wokwi

Folder ini berisi firmware ESP32 + skema rangkaian untuk **mensimulasikan** Alternatif (FR-05, kontrol lampu IoT) dari `gesture_s_detection.py` **sebelum** punya hardware asli — pakai [Wokwi](https://wokwi.com), simulator ESP32 berbasis browser, gratis, tanpa install apa pun.

Rangkaian: ESP32 DevKit V1 → relay module → LED (mewakili lampu). ESP32 subscribe ke topic MQTT yang **sama persis** dengan yang dipakai script Python (`smartagri/lampu`, payload `"ON"`/`"OFF"`), jadi bisa dites end-to-end dengan sistem gesture yang asli.

## Cara Menjalankan Simulasi

1. Buka [wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32) (perlu akun gratis).
2. Klik tab **sketch.ino** di editor, hapus isinya, replace dengan isi [`sketch.ino`](./sketch.ino) di folder ini.
3. Klik tab **diagram.json**, replace isinya dengan isi [`diagram.json`](./diagram.json) di folder ini.
4. Buka **Library Manager** (ikon buku di sidebar kiri), cari **PubSubClient** (by Nick O'Leary), klik install. (Isi [`libraries.txt`](./libraries.txt) kalau editor kamu mendukung file itu langsung.)
5. Klik tombol **Play** (▶ hijau) di kanan atas. Tunggu sampai log Serial Monitor menunjukkan `WiFi terhubung` dan `Menghubungkan ke broker MQTT ... terhubung.`

## Tes End-to-End dengan Sistem Gesture Asli

Karena Wokwi bisa akses internet asli (lewat gateway publik mereka) ke **broker MQTT publik**, kamu bisa benar-benar mengetes seluruh alur nyata:

1. Di laptop, buka `gesture_s_detection.py`, set:
   ```python
   CONNECTION_MODE = "MQTT"
   MQTT_BROKER = "test.mosquitto.org"
   ```
2. Jalankan script Python seperti biasa, pilih mode **LAMPU** saat prompt awal (atau tekan `m` di tengah jalan untuk ganti mode).
3. Pastikan simulasi Wokwi di atas sedang berjalan (status "terhubung" di Serial Monitor).
4. Lakukan gesture "S" sampai 100%, tekan tombol aksi (spasi).
5. LED di simulasi Wokwi akan **benar-benar menyala** — pesan MQTT asli dari laptop kamu diterima oleh ESP32 virtual di browser.

> **Kenapa harus broker publik, bukan broker di laptop sendiri?** Wokwi versi gratis cuma bisa akses internet publik, tidak bisa menjangkau jaringan lokal/laptop kamu (itu API privat, butuh fitur "Private Gateway" berbayar). `test.mosquitto.org` publik dan gratis, cukup untuk tahap simulasi ini — nanti pas pakai hardware asli baru pindah ke broker lokal (lihat README utama, bagian "Dari Simulasi ke Hardware Nyata").

## Pindah ke Hardware Asli

Begitu simulasi ini berhasil dan kamu sudah punya ESP32/NodeMCU + relay + lampu asli:

1. Flash `sketch.ino` yang sama ke board asli lewat Arduino IDE.
2. Ganti `WIFI_SSID`/`WIFI_PASS` ke WiFi sungguhan (WiFi venue, hotspot laptop, dll).
3. Ganti `MQTT_BROKER` ke broker lokal (Mosquitto di laptop) atau tetap broker publik kalau masih rehearsal.
4. Tidak ada perubahan lain — topic, payload, dan logika relay identik dengan yang sudah dites di simulasi.

## Catatan Penting

- Simulasi ini **cuma untuk membuktikan konsep** (gesture → MQTT → aksi lampu berhasil tersambung end-to-end). Untuk lampu aula yang sesungguhnya (AC 220V, sirkuit besar), **jangan** langsung tempel hardware DIY ke instalasi listrik gedung — itu perlu koordinasi dengan pihak pengelola gedung/teknisi listrik, di luar cakupan simulasi ini.
- Rekomendasi realistis untuk demo panggung: bawa lampu/fixture sendiri (LED spotlight kecil, lampu dekorasi) yang dikontrol lewat relay/smart-plug ini, ditaruh mencolok di panggung — bukan menyambung ke lampu utama aula.
