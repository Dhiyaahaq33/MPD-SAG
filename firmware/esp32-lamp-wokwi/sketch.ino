/*
  Simulasi Lampu IoT "Fase S" - ESP32 + Relay (untuk Wokwi)
  ==========================================================
  Subscribe ke topic MQTT yang SAMA dengan gesture_s_detection.py:
      MQTT_TOPIC_LAMP = "smartagri/lampu"
      payload         = "ON" / "OFF"

  Cara pakai di Wokwi (wokwi.com/projects/new/esp32):
    1. Ganti isi sketch.ino di project baru dengan file ini.
    2. Ganti diagram.json (tab di sebelah sketch.ino) dengan diagram.json
       di folder ini.
    3. Tambahkan library "PubSubClient" lewat Library Manager (ikon buku
       di sidebar kiri), atau isi libraries.txt sesuai file di folder ini.
    4. Klik Play (segitiga hijau) untuk mulai simulasi.

  PENTING soal jaringan di Wokwi:
    - WiFi memakai jaringan virtual "Wokwi-GUEST" (tanpa password) -
      ini BUKAN wifi asli, cuma untuk simulasi.
    - Broker MQTT harus broker PUBLIK (mis. test.mosquitto.org), karena
      gateway gratis Wokwi tidak bisa menjangkau laptop/jaringan lokal.
    - Supaya bisa dites end-to-end: jalankan gesture_s_detection.py di
      laptop dengan CONNECTION_MODE="MQTT" dan MQTT_BROKER sama dengan
      di bawah ini (test.mosquitto.org). Begitu gesture "S" berhasil dan
      lampu dipilih sebagai aksi, ESP32 virtual ini akan benar-benar
      menerima pesan MQTT asli dan menyalakan relay virtual.

  Begitu pindah ke hardware ESP32/NodeMCU asli:
    - Ganti WIFI_SSID / WIFI_PASS ke WiFi sungguhan.
    - Ganti MQTT_BROKER ke broker lokal (mis. Mosquitto di laptop, atau
      broker publik kalau masih rehearsal) - lihat README.md project ini.
    - Kode & topic MQTT TIDAK perlu diubah sama sekali.
*/

#include <WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_PASS   = "";
const char* MQTT_BROKER = "test.mosquitto.org";
const int   MQTT_PORT   = 1883;
const char* TOPIC_LAMPU = "smartagri/lampu";
const int   RELAY_PIN   = 4;   // GPIO4 -> pin IN relay module

WiFiClient   espClient;
PubSubClient client(espClient);

void onMessage(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  Serial.printf("[MQTT] %s -> %s\n", topic, msg.c_str());

  if (msg == "ON") {
    digitalWrite(RELAY_PIN, HIGH);
    Serial.println("[LAMPU] ON");
  } else if (msg == "OFF") {
    digitalWrite(RELAY_PIN, LOW);
    Serial.println("[LAMPU] OFF");
  }
}

void connectWiFi() {
  Serial.printf("Menghubungkan ke WiFi \"%s\" ...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.print("\nWiFi terhubung, IP: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!client.connected()) {
    Serial.print("Menghubungkan ke broker MQTT ...");
    if (client.connect("ESP32-LampuAgri-Wokwi")) {
      Serial.println(" terhubung.");
      client.subscribe(TOPIC_LAMPU);
      Serial.printf("Subscribe topic: %s\n", TOPIC_LAMPU);
    } else {
      Serial.printf(" gagal (rc=%d), coba lagi 2 detik...\n", client.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  connectWiFi();
  client.setServer(MQTT_BROKER, MQTT_PORT);
  client.setCallback(onMessage);
}

void loop() {
  if (!client.connected()) {
    connectMQTT();
  }
  client.loop();
}
