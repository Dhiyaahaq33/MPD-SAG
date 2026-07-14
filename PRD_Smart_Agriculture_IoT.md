# Product Requirements Document (PRD) - Smart Agriculture IoT System

## 1. Ringkasan Proyek (Executive Summary)
Proyek ini bertujuan untuk membangun sebuah sistem antarmuka (interface) dan logika kontrol berbasis Internet of Things (IoT) untuk sektor pertanian cerdas (Smart Agriculture). Sistem ini dirancang untuk mendeteksi status tertentu (dinamakan "Fase S") dan memberikan respons otomatis berupa visualisasi data secara real-time (seperti NDVI) dan aksi lanjutan berupa pemutaran media atau kontrol perangkat keras (lampu).

## 2. Tujuan dan Sasaran (Objectives & Goals)
- **Visualisasi Real-time:** Memberikan representasi data pertanian yang informatif (terutama indeks NDVI) secara instan saat kondisi spesifik ("Fase S") terpenuhi.
- **Fleksibilitas Output:** Menyediakan percabangan alur respons sistem yang dinamis, memungkinkan sistem untuk beradaptasi dengan memberikan output multimedia (video) atau aksi fisik (menyalakan lampu).
- **Dokumentasi & Perencanaan:** Menjadi landasan kuat untuk penyusunan COPM dan Project Definition Document (PDD).

## 3. Alur Logika Sistem & Pengalaman Pengguna (System Flow & UX)
Sistem merespons berdasarkan *trigger* (pemicu) tunggal dan dilanjutkan dengan cabang logika sebagai berikut:

### 3.1. Pemicu (Trigger) Utama
- **Deteksi "Fase S":** Sistem backend atau sensor harus mendeteksi bahwa sistem atau tanaman telah memasuki tahap "Fase S". Trigger ini bertindak sebagai *command* awal untuk seluruh rangkaian logika berikutnya.

### 3.2. Aksi Pertama (Output Visual Langsung)
- **Menampilkan UI Smart Agriculture:** Segera setelah "Fase S" terdeteksi, antarmuka pengguna (UI) harus beralih atau menampilkan elemen-elemen IoT.
- **Indikator NDVI:** Elemen utama yang wajib dirender pada layar adalah data atau metrik terkait **NDVI** (Normalized Difference Vegetation Index).

### 3.3. Aksi Lanjutan (Conditional Output)
Setelah visualisasi awal (NDVI) berjalan dan sistem memverifikasi bahwa koneksi telah terhubung (connected), sistem akan mengeksekusi salah satu dari dua skenario berikut (tergantung konfigurasi final atau preferensi user):

*   **Plan A (Integrasi Multimedia):** 
    Sistem memicu pemutaran video secara otomatis. Pengaturan UI dapat berupa:
    - Menjadikan video sebagai *background* di belakang data/grafik NDVI.
    - Melakukan transisi (cut/fade) untuk beralih secara penuh ke tayangan video presentasi.
    
*   **Alternatif (Kontrol Hardware IoT):**
    Sebagai ganti video, sistem akan mengirimkan instruksi IoT ke aktuator di lapangan untuk **mengaktifkan sensor/relay yang menyalakan lampu** (misalnya lampu pertumbuhan/grow light, lampu indikator, atau penerangan greenhouse).

## 4. Kebutuhan Fungsional (Functional Requirements)
- **FR-01 (Detection Module):** Sistem harus dapat menerima payload atau sinyal status "Fase S" dengan latensi seminimal mungkin.
- **FR-02 (Dashboard & UI):** Frontend harus memiliki komponen UI yang siap merender metrik grafis NDVI (bisa berupa angka, chart, atau heatmap).
- **FR-03 (Connection State Management):** Sistem harus memantau status koneksi perangkat secara terus-menerus. Aksi Lanjutan (Plan A / Alternatif) hanya boleh di-trigger (dipicu) setelah status `isConnected == true` tercapai.
- **FR-04 (Video Module):** Modul pemutar media harus mendukung *autoplay* dan penyesuaian z-index untuk keperluan render di *background*.
- **FR-05 (IoT Hardware Control):** Backend IoT (misal: via protokol MQTT atau HTTP POST) harus dapat meneruskan instruksi ON/OFF ke node lampu/sensor di area agrikultur secara nirkabel.

## 6. Status Proyek Saat Ini
- **Fase Saat Ini:** FR-01 s.d. FR-05 sudah diimplementasikan sebagai prototipe di `gesture_s_detection.py`:
  - Trigger "Fase S" = gesture tangan "S" berhasil diverifikasi (state ACTIVATE/DONE pada state machine).
  - UI NDVI (simulasi random-walk) tampil di overlay OpenCV begitu Fase S terdeteksi (FR-01, FR-02).
  - Status koneksi `isConnected` dipantau lewat `ConnectionManager` — mode `SIMULATED` (default, aman untuk demo tanpa hardware) atau `MQTT` (ke broker/ESP32 nyata) (FR-03).
  - Setelah `isConnected == true`: Plan A (video autoplay background/fullscreen) berjalan otomatis, dan tombol `l` mengirim perintah Alternatif (ON/OFF lampu via MQTT/simulasi) (FR-04, FR-05).
  - Catatan: UI masih berupa overlay OpenCV (bukan dashboard web terpisah) — cukup untuk demo OSPEK, belum sesuai arsitektur dashboard web penuh.
- **Langkah Berikutnya (Next Steps):**
  1. Pembuatan dan finalisasi **COPM** oleh tim terkait.
  2. Integrasi spesifikasi ini ke dalam dokumen **PDD** (Project Definition Document) yang lebih komprehensif.
  3. Jika dibutuhkan tampilan web/dashboard sungguhan (bukan overlay OpenCV), rancang backend WebSocket/HTTP terpisah dari script deteksi gesture ini.
  4. Sebelum hari-H: pastikan `CONNECTION_MODE`, `MQTT_BROKER`, dan file `assets/promo.mp4` (Plan A) sudah disiapkan sesuai kebutuhan acara.

---
*Dokumen ini digenerate berdasarkan referensi audio PTT-20260714-WA0022.opus.*
