# Raspberry Pi als brug naar je Sonos Play:1

Een (oude) Raspberry Pi is voor dit doel robuuster dan een ESP32, en
maakt bovendien een mooiere route mogelijk: **AirPlay in plaats van
Bluetooth**. Je iPhone kan namelijk via AirPlay uitzenden naar alles wat
zich als AirPlay-speaker aanmeldt — en met
[AirConnect](https://github.com/philippe44/AirConnect) laat je de Pi je
Play:1 als AirPlay-speaker aanbieden.

```
iPhone ──AirPlay──▶ Pi (AirConnect) ──UPnP──▶ Sonos Play:1
```

Voordelen boven de Bluetooth/ESP-route:

- **Geen Bluetooth nodig** — werkt dus ook op een Pi 1 of 2 zonder
  ingebouwde Bluetooth/WiFi, aan een netwerkkabel.
- **Minder vertraging** (circa 1–2 seconden in plaats van 2–5).
- **Volumeknoppen van je iPhone bedienen de Sonos** — bij de
  Bluetooth-route werkt dat niet.
- Geen pairing: iedereen in huis met een iPhone kan de speaker kiezen
  via het AirPlay-menu.
- AirConnect is één kant-en-klaar programma; niets te solderen of te
  flashen.

## Installatie (AirConnect)

Werkt op elk Raspberry Pi OS. De Pi moet in hetzelfde netwerk zitten
als de Sonos.

1. Download de nieuwste release van
   [AirConnect](https://github.com/philippe44/AirConnect/releases) en
   pak de `airupnp`-binary voor jouw Pi uit (`...linux-arm` voor 32-bit
   Raspberry Pi OS, `...linux-aarch64` voor 64-bit):

   ```sh
   sudo mkdir -p /opt/airconnect
   cd /opt/airconnect
   # controleer op de releases-pagina de exacte bestandsnaam van de
   # nieuwste versie (ten tijde van schrijven 1.11.2):
   sudo wget https://github.com/philippe44/AirConnect/releases/latest/download/AirConnect-1.11.2.zip
   sudo unzip AirConnect-*.zip airupnp-linux-arm
   sudo chmod +x airupnp-linux-arm
   ```

2. Test even handmatig — je Sonos wordt automatisch gevonden:

   ```sh
   /opt/airconnect/airupnp-linux-arm
   ```

   Pak nu je iPhone, open het Bedieningspaneel → audioweergave
   (AirPlay). Er verschijnt een extra speaker met een `+` achter de
   naam, bijvoorbeeld **Woonkamer+**. Selecteer die en alles wat je
   iPhone afspeelt (dus ook Hitster) klinkt uit de Play:1.

3. Werkt het? Zet het dan vast als service, zodat het na een reboot
   vanzelf draait. Maak `/etc/systemd/system/airconnect.service`:

   ```ini
   [Unit]
   Description=AirConnect (AirPlay naar Sonos)
   After=network-online.target
   Wants=network-online.target

   [Service]
   ExecStart=/opt/airconnect/airupnp-linux-arm -Z
   Restart=on-failure
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```

   En activeer:

   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now airconnect
   ```

## Draai je Home Assistant OS?

Dan kan het mogelijk zelfs **zonder Pi**: er bestaat een
community-add-on voor AirConnect, zodat het gewoon op je Home
Assistant-machine meedraait. Zoek in de add-on store (of onder
community-repositories) naar "AirConnect".

## Toch liever Bluetooth op de Pi?

Kan ook (Pi 3, 4 of Zero W hebben Bluetooth aan boord): met
`bluez-alsa` maak je de Pi een Bluetooth-speaker en met `ffmpeg` zet
je de audio door als HTTP-stream die de Sonos afspeelt — hetzelfde
principe als het ESP32-project in `../esp-sonos-bridge/`. Maar de
AirPlay-route hierboven is eenvoudiger, stabieler en sneller; begin
daar. De Bluetooth-route heeft eigenlijk alleen zin voor telefoons
zonder AirPlay (Android-gasten die willen meespelen).
