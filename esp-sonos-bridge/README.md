# ESP32 Bluetooth → Sonos bridge

Maakt van een ESP32 een Bluetooth-speaker waar je je iPhone mee verbindt,
en serveert de ontvangen audio als HTTP-stream die je Sonos afspeelt.
Bedoeld voor speakers zonder AirPlay en zonder line-in (zoals de Play:1),
bijvoorbeeld om Hitster via je Sonos te spelen.

```
iPhone ──Bluetooth (A2DP)──▶ ESP32 ──WiFi (HTTP WAV-stream)──▶ Sonos
```

> **Tip:** heb je een (oude) Raspberry Pi liggen? Dan is de
> AirPlay-route via AirConnect eenvoudiger en robuuster — zie
> [`../rpi-bridge/`](../rpi-bridge/README.md).

## Benodigdheden

- Een **klassieke ESP32** (WROOM-32 of WROVER). Let op: de ESP32-S2, S3,
  C3 en C6 hebben alleen Bluetooth LE en kunnen géén A2DP-audio
  ontvangen — die zijn dus ongeschikt. Een WROVER (met PSRAM) geeft wat
  meer bufferruimte en dus minder kans op haperingen.
- [PlatformIO](https://platformio.org/) (als VS Code-extensie of CLI).
- WiFi-netwerk (2,4 GHz) waar ook je Sonos op zit.

## Flashen

1. Vul in `src/config.h` je WiFi-gegevens in en eventueel een andere
   Bluetooth-naam.
2. Sluit de ESP32 aan via USB en flash:

   ```sh
   cd esp-sonos-bridge
   pio run -t upload
   pio device monitor
   ```

3. In de seriële monitor verschijnt na het opstarten de stream-URL,
   bijvoorbeeld `http://192.168.1.50/`. Geef de ESP bij voorkeur een
   vast IP-adres (DHCP-reservering in je router), anders verandert de
   URL af en toe.

## Gebruik

1. Verbind je iPhone via Instellingen → Bluetooth met **Hitster Bridge**
   (of de naam die je koos) en start muziek — bijvoorbeeld een
   Hitster-kaartje scannen en afspelen.
2. Laat de Sonos de stream afspelen. Met Home Assistant is dat één
   service-aanroep — zie `homeassistant/hitster.yaml` voor een
   kant-en-klaar start/stop-script dat je aan een dashboardknop kunt
   hangen.

   Zonder Home Assistant kan het ook met Python en
   [soco](https://github.com/SoCo/SoCo):

   ```python
   import soco
   speaker = soco.discovery.by_name("Woonkamer")
   speaker.play_uri("http://192.168.1.50/")
   ```

3. Klaar met spelen? Stop de stream op de Sonos (of gebruik het
   stop-script).

## Beperkingen en tips

- **Vertraging:** Sonos buffert netwerkstreams. Reken op 2 tot 5
  seconden tussen actie op je telefoon en geluid uit de speaker. Voor
  Hitster is dat geen probleem, maar pauzeren en doorspoelen voelt
  traag.
- **Volume:** het volume van je iPhone werkt niet door in de stream.
  Regel het volume op de Sonos zelf (of via Home Assistant).
- **Start de muziek vóór (of vlak na) het starten van de stream** op de
  Sonos. Als er langere tijd geen audio binnenkomt via Bluetooth, kan de
  Sonos de stilgevallen stream loslaten; start hem dan gewoon opnieuw.
- **Haperingen:** WiFi en Bluetooth delen op de ESP32 één radio; dit is
  het zwaarste scenario voor die combinatie. Helpt het plaatsen dichter
  bij het accesspoint niet, vergroot dan de audiobuffer met build-flags
  in `platformio.ini`, bijvoorbeeld `-DA2DP_BUFFER_SIZE=1024
  -DA2DP_BUFFER_COUNT=10`.
- De stream is ongecomprimeerde 16-bit stereo WAV op 44,1 kHz
  (~1,4 Mbit/s). Dat is bewust: MP3-encoding is te zwaar voor de ESP32,
  en de Sonos speelt WAV-streams prima af.
