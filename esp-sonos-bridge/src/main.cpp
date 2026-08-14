/**
 * ESP32 Bluetooth -> Sonos bridge
 *
 * De ESP32 gedraagt zich als Bluetooth-speaker (A2DP-sink) waar je je
 * iPhone mee verbindt. De ontvangen audio wordt via WiFi aangeboden als
 * HTTP WAV-stream, die je Sonos als "radiostation" kan afspelen.
 *
 * Gebouwd op de bibliotheken van Phil Schatzmann:
 *   - https://github.com/pschatzmann/ESP32-A2DP
 *   - https://github.com/pschatzmann/arduino-audio-tools
 */

#include <WiFi.h>

#include "AudioTools.h"
#include "AudioTools/Communication/A2DPStream.h"
#include "AudioTools/Communication/AudioHttp.h"

#include "config.h"

// A2DP-sink als leesbare stream: levert 16 bit stereo op 44100 Hz
A2DPStream a2dp;

// HTTP-server die de audio als WAV-stream serveert (poort 80, pad "/")
AudioWAVServer server(WIFI_SSID, WIFI_PASSWORD);

void setup() {
  Serial.begin(115200);
  AudioToolsLogger.begin(Serial, AudioToolsLogLevel::Warning);

  Serial.println("Bluetooth A2DP-sink starten...");
  auto cfg = a2dp.defaultConfig(RX_MODE);
  cfg.name = BLUETOOTH_NAME;
  a2dp.begin(cfg);

  // WiFi-verbinding wordt door de server zelf opgezet
  server.begin(a2dp, 44100, 2, 16);

  Serial.print("Klaar. Stream-URL voor Sonos: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");
}

void loop() {
  // Bedient de verbonden client (Sonos) en kopieert de audio
  server.copy();
}
