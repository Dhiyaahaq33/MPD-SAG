"""
AI Gesture Activation - Deteksi Gesture 'S'
============================================
Sistem deteksi gesture "S" menggunakan MediaPipe Hands.
- Tangan kiri  : membentuk huruf "C"
- Tangan kanan : membentuk huruf "C" terbalik
- Posisi relatif: tangan kanan di atas tangan kiri (membentuk "S" vertikal)

Requirement:
    pip install mediapipe opencv-python numpy paho-mqtt ffpyplayer

Author  : Smart Agriculture Project
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import os
import random

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    from ffpyplayer.player import MediaPlayer
except ImportError:
    MediaPlayer = None

# ─────────────────────────────────────────────
# KONSTANTA SISTEM
# ─────────────────────────────────────────────
VERIFY_DURATION   = 2.0   # detik gesture harus dipertahankan untuk verifikasi
ACTIVATE_DURATION = 5.0   # detik gesture dipertahankan untuk progress 100% (dipercepat dari 10s)
PROGRESS_RESET    = True  # True = reset penuh jika gesture lepas

# ── Konfigurasi "Fase S" (PRD Smart Agriculture IoT) ──
CONNECTION_MODE = "SIMULATED"   # "SIMULATED" (demo aman tanpa hardware) atau "MQTT" (ESP32 nyata)
SIMULATED_CONNECT_DELAY = 1.5   # detik, jeda animasi "Connecting..." saat mode SIMULATED

MQTT_BROKER = "192.168.1.100"   # ganti sesuai IP broker/ESP32 saat mode MQTT
MQTT_PORT   = 1883
MQTT_TOPIC_LAMP = "smartagri/lampu"

PLAN_A_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "assets", "promo.mp4")
PLAN_A_MODE = "fullscreen"      # "fullscreen" (video penuh, tidak transparan) atau "background" (video + data transparan)
PLAN_A_LOOP = False             # False = video berhenti di frame terakhir setelah selesai, tidak mengulang

# ── Pilihan Aksi Lanjutan (sesuai PRD: Plan A ATAU Alternatif, bukan dua-duanya) ──
# Set salah satu sebelum demo. Operator tinggal tekan SATU tombol (ACTION_KEY) di panggung.
ACTION_MODE = "VIDEO"   # "VIDEO" (Plan A) atau "LAMPU" (Alternatif)
ACTION_KEY  = ' '       # tombol tunggal untuk menjalankan aksi lanjutan (default: SPASI)

# ─────────────────────────────────────────────
# INISIALISASI MEDIAPIPE
# ─────────────────────────────────────────────
mp_hands    = mp.solutions.hands
mp_drawing  = mp.solutions.drawing_utils
mp_styles   = mp.solutions.drawing_styles

hands_model = mp_hands.Hands(
    static_image_mode       = False,
    max_num_hands           = 2,
    min_detection_confidence= 0.7,
    min_tracking_confidence = 0.6,
)

# ─────────────────────────────────────────────
# FUNGSI ANALISIS LANDMARK
# ─────────────────────────────────────────────

def get_finger_states(landmarks):
    """
    Mengembalikan dict status jari (True = menekuk / tertutup).
    Menggunakan perbandingan posisi y tip vs pip untuk jari 2-5,
    dan posisi x untuk ibu jari.
    
    Landmark index:
        0=WRIST, 1=THUMB_CMC, 2=THUMB_MCP, 3=THUMB_IP, 4=THUMB_TIP
        5=INDEX_MCP, 6=INDEX_PIP, 7=INDEX_DIP, 8=INDEX_TIP
        9=MIDDLE_MCP,10=MIDDLE_PIP,11=MIDDLE_DIP,12=MIDDLE_TIP
        13=RING_MCP, 14=RING_PIP, 15=RING_DIP, 16=RING_TIP
        17=PINKY_MCP,18=PINKY_PIP,19=PINKY_DIP,20=PINKY_TIP
    """
    lm = landmarks.landmark
    states = {}

    # Ibu jari: bandingkan x tip vs x MCP (tangan kanan: tip < mcp = menekuk)
    states['thumb']  = lm[4].x < lm[2].x   # akan dioverride per tangan jika perlu
    # Jari lain: tip y > pip y berarti menekuk (koordinat y membesar ke bawah)
    states['index']  = lm[8].y  > lm[6].y
    states['middle'] = lm[12].y > lm[10].y
    states['ring']   = lm[16].y > lm[14].y
    states['pinky']  = lm[20].y > lm[18].y

    return states


def is_c_shape(landmarks, hand_label):
    """
    Deteksi bentuk "C" (tangan kiri) atau "C terbalik" (tangan kanan).

    Pola "C" tangan kiri:
      - Semua jari (index, middle, ring, pinky) sedikit melengkung/terbuka
        ke kanan (tidak menekuk penuh, tidak lurus penuh).
      - Ibu jari mengarah ke atas / terbuka.
      - Secara keseluruhan membentuk busur terbuka ke kanan.

    Pola "C terbalik" tangan kanan:
      - Sama seperti di atas tapi busur terbuka ke kiri.
      
    Pendekatan:
      Kita gunakan jarak antara ujung jari telunjuk (tip) dan kelingking (tip)
      relatif terhadap lebar telapak tangan, serta memastikan jari-jari
      tidak menekuk penuh dan tidak lurus penuh.
    """
    lm = landmarks.landmark

    # ── Landmark penting ──
    wrist       = np.array([lm[0].x,  lm[0].y])
    index_tip   = np.array([lm[8].x,  lm[8].y])
    index_pip   = np.array([lm[6].x,  lm[6].y])
    middle_tip  = np.array([lm[12].x, lm[12].y])
    ring_tip    = np.array([lm[16].x, lm[16].y])
    pinky_tip   = np.array([lm[20].x, lm[20].y])
    pinky_mcp   = np.array([lm[17].x, lm[17].y])
    index_mcp   = np.array([lm[5].x,  lm[5].y])
    thumb_tip   = np.array([lm[4].x,  lm[4].y])
    thumb_ip    = np.array([lm[3].x,  lm[3].y])

    # ── Ukuran referensi: lebar telapak (MCP telunjuk ke MCP kelingking) ──
    palm_width = np.linalg.norm(index_mcp - pinky_mcp)
    if palm_width < 1e-5:
        return False, 0.0

    # ── Cek 1: Jari-jari semi-menekuk (tidak lurus total, tidak digenggam) ──
    # Menekuk "cukup" = tip lebih dekat ke wrist dari pip
    def curl_ratio(tip, pip):
        """Rasio pelengkungan: 0=lurus, 1=menekuk penuh"""
        d_tip_wrist = np.linalg.norm(tip - wrist)
        d_pip_wrist = np.linalg.norm(pip - wrist)
        if d_pip_wrist < 1e-5:
            return 0.0
        return 1.0 - (d_tip_wrist / (d_pip_wrist + d_tip_wrist)) * 2

    index_curl  = curl_ratio(index_tip,  np.array([lm[6].x, lm[6].y]))
    middle_curl = curl_ratio(middle_tip, np.array([lm[10].x,lm[10].y]))
    ring_curl   = curl_ratio(ring_tip,   np.array([lm[14].x,lm[14].y]))

    # ── Cek 2: Jarak ujung telunjuk ke ujung kelingking (busur terbuka) ──
    tip_span = np.linalg.norm(index_tip - pinky_tip)
    span_ratio = tip_span / palm_width  # C shape: span harus cukup besar

    # ── Cek 3: Ibu jari terbuka (tidak digenggam ke dalam) ──
    thumb_open = np.linalg.norm(thumb_tip - index_tip) / palm_width

    # ── Cek 4: Orientasi busur (kanan vs kiri) ──
    # Tengah jari-jari (middle tip) harus lebih ke kanan (C) atau kiri (C inv)
    # dibanding garis wrist-index_mcp
    palm_center_x = (index_mcp[0] + pinky_mcp[0]) / 2

    # ── Scoring ──
    score = 0.0
    reasons = []

    # Jari melengkung sedang: curl antara -0.3 dan 0.5
    if -0.3 < index_curl < 0.5:
        score += 0.25
    if -0.3 < middle_curl < 0.5:
        score += 0.25
    if -0.3 < ring_curl < 0.5:
        score += 0.15

    # Busur terbuka: span cukup lebar
    if span_ratio > 0.6:
        score += 0.2

    # Ibu jari tidak menutup
    if thumb_open > 0.3:
        score += 0.15

    return score >= 0.6, round(score, 2)


def get_hand_center_y(landmarks):
    """Rata-rata posisi y seluruh landmark (untuk posisi relatif tangan)."""
    lm = landmarks.landmark
    return np.mean([l.y for l in lm])


def detect_s_gesture(multi_hand_landmarks, multi_handedness):
    """
    Mendeteksi gesture 'S' dari hasil deteksi MediaPipe.
    
    Returns:
        (bool, float, dict) : (valid, confidence_score, debug_info)
    """
    if multi_hand_landmarks is None or len(multi_hand_landmarks) < 2:
        return False, 0.0, {"error": "Kurang dari 2 tangan terdeteksi"}

    # ── Pisahkan tangan kiri dan kanan ──
    left_hand  = None
    right_hand = None

    for idx, handedness in enumerate(multi_handedness):
        label = handedness.classification[0].label  # "Left" atau "Right"
        # MediaPipe melabeli berdasarkan mirror: "Left" = tangan kiri pengguna
        if label == "Left":
            left_hand  = multi_hand_landmarks[idx]
        elif label == "Right":
            right_hand = multi_hand_landmarks[idx]

    if left_hand is None or right_hand is None:
        return False, 0.0, {"error": "Salah satu tangan tidak teridentifikasi"}

    # ── Cek bentuk C dan C terbalik ──
    left_c,  left_score  = is_c_shape(left_hand,  "Left")
    right_c, right_score = is_c_shape(right_hand, "Right")

    # ── Cek posisi relatif: tangan kanan di ATAS tangan kiri ──
    left_y  = get_hand_center_y(left_hand)
    right_y = get_hand_center_y(right_hand)

    # y lebih kecil = lebih tinggi di layar
    right_above_left = right_y < left_y
    vertical_gap     = abs(right_y - left_y)  # minimal ada jarak vertikal

    # ── Skor gabungan ──
    total_score = (left_score + right_score) / 2

    debug = {
        "left_c"        : left_c,
        "left_score"    : left_score,
        "right_c"       : right_c,
        "right_score"   : right_score,
        "right_above"   : right_above_left,
        "vertical_gap"  : round(vertical_gap, 3),
        "total_score"   : round(total_score, 2),
    }

    is_valid = left_c and right_c and right_above_left and vertical_gap > 0.05
    return is_valid, total_score, debug


# ─────────────────────────────────────────────
# STATE MACHINE SISTEM
# ─────────────────────────────────────────────

class GestureState:
    IDLE     = "IDLE"       # Menunggu gesture
    VERIFY   = "VERIFY"     # Gesture terdeteksi, sedang verifikasi 2 detik
    ACTIVATE = "ACTIVATE"   # Gesture valid, progress berjalan
    DONE     = "DONE"       # Progress 100%


class GestureActivationSystem:
    def __init__(self):
        self.state          = GestureState.IDLE
        self.gesture_start  = None   # Waktu gesture pertama kali valid
        self.activate_start = None   # Waktu mulai progress bar
        self.progress       = 0.0    # 0.0 – 100.0

    def update(self, gesture_valid: bool) -> dict:
        """
        Update state machine berdasarkan status gesture saat ini.
        
        Returns dict berisi state, progress, dan pesan status.
        """
        now = time.time()

        if self.state == GestureState.IDLE:
            if gesture_valid:
                self.gesture_start = now
                self.state = GestureState.VERIFY

        elif self.state == GestureState.VERIFY:
            if not gesture_valid:
                # Gesture hilang, kembali idle
                self.gesture_start = None
                self.state = GestureState.IDLE
            else:
                elapsed = now - self.gesture_start
                if elapsed >= VERIFY_DURATION:
                    # Verifikasi berhasil → mulai aktivasi
                    self.activate_start = now
                    self.state = GestureState.ACTIVATE

        elif self.state == GestureState.ACTIVATE:
            if not gesture_valid:
                if PROGRESS_RESET:
                    self.progress       = 0.0
                    self.activate_start = None
                    self.state          = GestureState.IDLE
                # else: bisa tambah logika pengurangan bertahap
            else:
                elapsed       = now - self.activate_start
                self.progress = min((elapsed / ACTIVATE_DURATION) * 100, 100.0)
                if self.progress >= 100.0:
                    self.state = GestureState.DONE

        elif self.state == GestureState.DONE:
            pass  # Bisa tambah logika reset manual di sini

        # LED mapping
        led = self._get_led_state()

        return {
            "state"   : self.state,
            "progress": round(self.progress, 1),
            "led"     : led,
            "message" : self._get_message(),
        }

    def _get_led_state(self):
        """Mengembalikan LED aktif berdasarkan progress (sesuai spesifikasi)."""
        p = self.progress
        if p == 0:
            return "OFF"
        elif p <= 25:
            return "GREEN"    # 0-25%
        elif p <= 50:
            return "BLUE"     # 25-50%
        elif p <= 75:
            return "YELLOW"   # 50-75%
        else:
            return "RED"      # 75-100%

    def _get_message(self):
        messages = {
            GestureState.IDLE    : "Bentuk gesture 'S' dengan kedua tangan",
            GestureState.VERIFY  : "Tahan gesture... verifikasi...",
            GestureState.ACTIVATE: f"Tahan! Progress: {self.progress:.1f}%",
            GestureState.DONE    : "AKTIVASI BERHASIL!",
        }
        return messages[self.state]

    def reset(self):
        self.__init__()


# ─────────────────────────────────────────────
# MODUL "FASE S" — NDVI, KONEKSI, VIDEO, LAMPU IoT
# (sesuai PRD_Smart_Agriculture_IoT.md)
# ─────────────────────────────────────────────

class NDVISimulator:
    """Simulasi pembacaan sensor NDVI (random walk 0.2 - 0.9)."""

    def __init__(self):
        self.value = 0.55

    def update(self):
        self.value += random.uniform(-0.02, 0.02)
        self.value = min(max(self.value, 0.2), 0.9)
        return self.value

    def label(self):
        if self.value < 0.35:
            return "Kritis", (0, 60, 255)
        elif self.value < 0.55:
            return "Perlu Perhatian", (0, 200, 255)
        else:
            return "Optimal", (0, 220, 100)


class ConnectionManager:
    """
    Mengelola status koneksi (FR-03: isConnected).
    Mode SIMULATED: connected otomatis setelah jeda singkat (aman untuk demo panggung).
    Mode MQTT     : connect ke broker/ESP32 sungguhan.
    """

    def __init__(self, mode=CONNECTION_MODE):
        self.mode = mode
        self.is_connected = False
        self.trigger_time = None
        self.client = None

        if self.mode == "MQTT" and mqtt is not None:
            try:
                self.client = mqtt.Client()
                self.client.on_connect = lambda c, u, f, rc: setattr(self, "is_connected", rc == 0)
                self.client.connect_async(MQTT_BROKER, MQTT_PORT)
                self.client.loop_start()
            except Exception as e:
                print(f"[MQTT] Gagal konek ke broker: {e}. Fallback ke mode simulasi.")
                self.mode = "SIMULATED"

    def start(self, now):
        if self.trigger_time is None:
            self.trigger_time = now

    def update(self, now):
        if self.trigger_time is None:
            return self.is_connected
        if self.mode == "SIMULATED":
            if now - self.trigger_time >= SIMULATED_CONNECT_DELAY:
                self.is_connected = True
        return self.is_connected

    def reset(self):
        self.is_connected = False
        self.trigger_time = None

    def send_lamp_command(self, state: bool):
        """Alternatif (FR-05): kirim ON/OFF ke node lampu/relay IoT."""
        payload = "ON" if state else "OFF"
        if self.mode == "MQTT" and self.client is not None:
            self.client.publish(MQTT_TOPIC_LAMP, payload)
        else:
            print(f"[LAMPU-SIMULASI] Perintah lampu: {payload}")


class VideoPlanA:
    """
    Plan A (FR-04): pemutaran video otomatis dengan audio, background atau fullscreen.
    Pakai ffpyplayer (bukan cv2.VideoCapture) supaya audio ikut diputar & sinkron dengan video.
    Setelah video habis: berhenti di frame terakhir (freeze), tidak mengulang, kecuali PLAN_A_LOOP=True.
    """

    def __init__(self, path=PLAN_A_VIDEO_PATH, loop=PLAN_A_LOOP):
        self.path = path
        self.loop = loop
        self.available = os.path.isfile(path) and MediaPlayer is not None
        self.player = None
        self.playing = False   # True selama video aktif diputar (belum selesai)
        self.started = False   # True begitu start() pernah dipanggil (mencegah start ulang)
        self._last_frame = None

    def start(self):
        if not self.available or self.started:
            return
        self.player = MediaPlayer(self.path, ff_opts={"out_fmt": "bgr24"})
        self.playing = True
        self.started = True
        self._last_frame = None

    def next_frame(self, target_w, target_h):
        if self.player is None:
            return self._last_frame
        if not self.playing:
            return self._last_frame  # video sudah selesai -> tetap tampilkan frame terakhir

        frame, val = self.player.get_frame()
        if val == "eof":
            if self.loop:
                self.player.seek(0, relative=False, accurate=False)
            else:
                # Tutup player SEGERA begitu eof -> mencegah decoder terus
                # mengirim frame sisa/rusak di ujung video (efek "ngulang sendiri").
                self.playing = False
                self.player.close_player()
                self.player = None
            return self._last_frame

        if frame is not None:
            img, pts = frame
            w, h = img.get_size()
            buf = img.to_bytearray()[0]
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
            self._last_frame = cv2.resize(arr, (target_w, target_h))

        return self._last_frame

    def stop(self):
        if self.player is not None:
            self.player.close_player()
        self.player = None
        self.playing = False
        self.started = False
        self._last_frame = None


# ─────────────────────────────────────────────
# VISUALISASI OVERLAY
# ─────────────────────────────────────────────

LED_COLORS = {
    "OFF"   : (80, 80, 80),
    "GREEN" : (0, 255, 80),
    "BLUE"  : (255, 100, 0),
    "YELLOW": (0, 220, 255),
    "RED"   : (0, 50, 255),
}

STATE_COLORS = {
    GestureState.IDLE    : (150, 150, 150),
    GestureState.VERIFY  : (0, 200, 255),
    GestureState.ACTIVATE: (0, 255, 100),
    GestureState.DONE    : (0, 255, 255),
}


def draw_overlay(frame, system_output, debug_info):
    h, w = frame.shape[:2]

    # ── Panel background ──
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    state    = system_output["state"]
    progress = system_output["progress"]
    led      = system_output["led"]
    message  = system_output["message"]
    color    = STATE_COLORS.get(state, (255, 255, 255))

    # ── Status teks ──
    cv2.putText(frame, f"STATE: {state}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(frame, message, (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)

    # ── Progress Bar ──
    bar_x, bar_y, bar_w, bar_h = 10, 65, w - 20, 14
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
    fill = int(bar_w * progress / 100)
    if fill > 0:
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), color, -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (200, 200, 200), 1)
    cv2.putText(frame, f"{progress:.1f}%", (bar_x + bar_w + 5, bar_y + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    # ── LED Indikator (4 lingkaran) ──
    led_labels  = ["GREEN\n0-25%", "BLUE\n25-50%", "YELLOW\n50-75%", "RED\n75-100%"]
    led_keys    = ["GREEN", "BLUE", "YELLOW", "RED"]
    led_cx_start = w - 180
    for i, (key, lbl) in enumerate(zip(led_keys, led_labels)):
        cx  = led_cx_start + i * 45
        cy  = 40
        col = LED_COLORS[key] if led == key else (40, 40, 40)
        cv2.circle(frame, (cx, cy), 15, col, -1)
        cv2.circle(frame, (cx, cy), 15, (200, 200, 200), 1)

    # ── Debug info gesture ──
    if debug_info and "total_score" in debug_info:
        y0 = h - 100
        cv2.putText(frame, f"L-C: {'OK' if debug_info['left_c'] else 'X'} ({debug_info['left_score']})",
                    (10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1)
        cv2.putText(frame, f"R-C: {'OK' if debug_info['right_c'] else 'X'} ({debug_info['right_score']})",
                    (10, y0 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 255), 1)
        cv2.putText(frame, f"R>L: {'OK' if debug_info['right_above'] else 'X'}  Gap:{debug_info['vertical_gap']}",
                    (10, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 180), 1)
        cv2.putText(frame, f"Score: {debug_info['total_score']}",
                    (10, y0 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 100), 1)

    # ── Petunjuk gesture ──
    cv2.putText(frame, "Gesture S: Tangan Kanan [C-inv] di atas | Tangan Kiri [C] di bawah",
                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)

    return frame


def draw_smart_agri_panel(frame, ndvi_value, ndvi_label, ndvi_color, is_connected,
                           video_status, lamp_on):
    """UI Smart Agriculture: NDVI + status koneksi + status Plan A/Alternatif (FR-02, FR-03)."""
    h, w = frame.shape[:2]
    panel_w, panel_h = 230, 155
    px, py = w - panel_w - 10, 100

    overlay = frame.copy()
    cv2.rectangle(overlay, (px, py), (px + panel_w, py + panel_h), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (px, py), (px + panel_w, py + panel_h), (200, 200, 200), 1)

    cv2.putText(frame, "SYSTEM STATUS", (px + 10, py + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    # Skor status (data teknisnya tetap NDVI simulasi, wording generik)
    cv2.putText(frame, f"SKOR: {ndvi_value:.2f}", (px + 10, py + 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, ndvi_color, 2)
    cv2.putText(frame, ndvi_label, (px + 10, py + 63),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, ndvi_color, 1)

    # Status koneksi
    conn_col = (0, 220, 100) if is_connected else (0, 180, 255)
    conn_txt = "Connected" if is_connected else "Connecting..."
    cv2.circle(frame, (px + 15, py + 80), 5, conn_col, -1)
    cv2.putText(frame, f"IoT: {conn_txt}", (px + 28, py + 84),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, conn_col, 1)

    # Plan A (video)
    video_col = (0, 220, 100) if video_status == "ON" else (
        (0, 200, 255) if video_status == "SELESAI" else (120, 120, 120))
    cv2.putText(frame, f"Plan A Video: {video_status}", (px + 10, py + 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, video_col, 1)

    # Alternatif (lampu) — digambar sebagai bohlam biar keliatan jelas nyala/mati
    bulb_cx, bulb_cy = px + 18, py + 122
    if lamp_on:
        cv2.circle(frame, (bulb_cx, bulb_cy), 12, (0, 220, 255), -1)   # glow luar
        cv2.circle(frame, (bulb_cx, bulb_cy), 7,  (255, 255, 255), -1)  # inti terang
    else:
        cv2.circle(frame, (bulb_cx, bulb_cy), 7, (60, 60, 60), -1)
        cv2.circle(frame, (bulb_cx, bulb_cy), 7, (150, 150, 150), 1)
    cv2.putText(frame, f"Alt. Lampu: {'ON' if lamp_on else 'OFF'}", (px + 35, py + 127),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 255) if lamp_on else (150, 150, 150), 1)

    return frame


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def choose_action_mode():
    """Tanya lewat console aksi apa yang mau dites sesi ini: VIDEO atau LAMPU."""
    print()
    print("Pilih aksi lanjutan untuk sesi demo ini (satu tombol SPASI akan menjalankan ini):")
    print("  1. VIDEO  (Plan A - putar video promo)")
    print("  2. LAMPU  (Alternatif - kirim ON ke lampu IoT)")
    choice = input(f"Pilihan [1/2] (Enter = default '{ACTION_MODE}'): ").strip()
    if choice == "1":
        return "VIDEO"
    elif choice == "2":
        return "LAMPU"
    return ACTION_MODE


def main():
    action_mode = choose_action_mode()

    # Ganti index kamera sesuai device (0=webcam default, atau DroidCam index)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  2000)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1040)

    system  = GestureActivationSystem()
    ndvi    = NDVISimulator()
    conn    = ConnectionManager()
    video   = VideoPlanA()
    debug_info      = {}
    phase_s_seen    = False   # FR-01: "Fase S" trigger sudah terdeteksi sekali
    lamp_on         = False
    action_done     = False   # True setelah tombol aksi ditekan (video mulai / lampu nyala)
    video_manual_stop = False  # True kalau video dihentikan manual lewat 's' (jangan auto-play lagi)

    print("=== AI Gesture Activation System (Smart Agriculture) ===")
    print(f"Mode aksi lanjutan sesi ini: {action_mode}  (tekan 'm' kapan saja untuk ganti mode)")
    print(f"Tekan [{ACTION_KEY.upper() if ACTION_KEY != ' ' else 'SPASI'}] untuk jalankan aksi setelah verifikasi 100% & terhubung")
    print("Tombol lain: 'q' keluar | 'r' reset | 'm' ganti mode Video/Lampu | 's' stop video | 'v' putar ulang video")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Mirror frame agar lebih natural (seperti cermin)
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # ── Proses MediaPipe ──
        results = hands_model.process(rgb)

        gesture_valid = False

        if results.multi_hand_landmarks:
            # Gambar landmark tangan
            for hand_lm in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame, hand_lm, mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )

            # Deteksi gesture S
            gesture_valid, score, debug_info = detect_s_gesture(
                results.multi_hand_landmarks,
                results.multi_handedness,
            )

        # ── Update state machine ──
        output = system.update(gesture_valid)
        now    = time.time()

        # ── FR-01: Trigger "Fase S" — begitu VERIFY berhasil (masuk ACTIVATE/DONE) ──
        if output["state"] in (GestureState.ACTIVATE, GestureState.DONE) and not phase_s_seen:
            phase_s_seen = True
            conn.start(now)
            print("[FASE S] Terdeteksi -> menampilkan UI Smart Agriculture (NDVI).")

        if phase_s_seen:
            if output["state"] == GestureState.DONE:
                ndvi.value = 1.0  # verifikasi sudah 100% selesai -> skor dikunci, tidak drop lagi
            else:
                ndvi.update()
            is_connected = conn.update(now)
        else:
            is_connected = False

        # ── FR-03: aksi lanjutan (Plan A / Alternatif) baru boleh ditekan setelah connected & DONE ──
        action_ready = is_connected and output["state"] == GestureState.DONE and not action_done

        # ── Overlay: video Plan A (background transparan atau fullscreen penuh) ──
        if video.started:
            h, w = frame.shape[:2]
            vframe = video.next_frame(w, h)
            if vframe is not None:
                if PLAN_A_MODE == "fullscreen":
                    frame = vframe
                else:  # "background": video + data transparan
                    frame = cv2.addWeighted(frame, 0.35, vframe, 0.65, 0)

        # ── Overlay visual utama (state/progress/LED) ──
        frame = draw_overlay(frame, output, debug_info)

        # ── Panel Smart Agriculture (NDVI, koneksi, Plan A/Alternatif) ──
        if phase_s_seen:
            label, ndvi_col = ndvi.label()
            if video.started and video.playing:
                video_status = "ON"
            elif video_manual_stop:
                video_status = "DIHENTIKAN"
            elif video.started and not video.playing:
                video_status = "SELESAI"
            else:
                video_status = "-"
            frame = draw_smart_agri_panel(
                frame, ndvi.value, label, ndvi_col,
                is_connected, video_status, lamp_on,
            )

        # ── Prompt tombol aksi tunggal (Video ATAU Lampu, sesuai action_mode saat ini) ──
        action_label = "VIDEO (Plan A)" if action_mode == "VIDEO" else "LAMPU (Alternatif)"
        if action_ready:
            key_label = "SPASI" if ACTION_KEY == " " else ACTION_KEY.upper()
            prompt = f"Tekan [{key_label}] untuk jalankan: {action_label}   ( 'm' = ganti mode )"
            hh, ww = frame.shape[:2]
            cv2.putText(frame, prompt, (ww // 2 - 280, hh // 2 + 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("AI Gesture Activation - Gesture S", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            system.reset()
            conn.reset()
            video.stop()
            phase_s_seen = False
            lamp_on = False
            action_done = False
            video_manual_stop = False
            print("[RESET] Sistem direset.")
        elif key == ord('m') and not action_done:
            action_mode = "LAMPU" if action_mode == "VIDEO" else "VIDEO"
            print(f"[MODE] Aksi lanjutan diganti ke: {action_mode}")
        elif key == ord(ACTION_KEY) and action_ready:
            # ── Tombol tunggal: jalankan Plan A (video) ATAU Alternatif (lampu), sesuai action_mode ──
            action_done = True
            if action_mode == "VIDEO":
                video.start()
                print("[AKSI] Plan A dijalankan -> video promo autoplay (dengan audio).")
            else:
                lamp_on = True
                conn.send_lamp_command(True)  # Alternatif (FR-05)
                print("[AKSI] Alternatif dijalankan -> perintah lampu ON dikirim.")
        elif key == ord('s') and video.started:
            video.stop()
            video_manual_stop = True
            action_done = False  # buka lagi aksi lanjutan -> bisa 'm' ganti mode atau tekan aksi ulang
            print("[VIDEO] Dihentikan manual. Tekan 'm' ganti mode, 'v' putar ulang, atau [SPASI] ulang aksi.")
        elif key == ord('v') and video.available:
            video.stop()
            video.start()
            video_manual_stop = False
            print("[VIDEO] Diputar ulang dari awal.")

    video.stop()
    cap.release()
    cv2.destroyAllWindows()
    hands_model.close()


if __name__ == "__main__":
    main()
