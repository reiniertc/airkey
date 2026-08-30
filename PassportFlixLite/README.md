# PassportFlix Lite (iOS 12)

Vereenvoudigde UIKit-versie van [PassportFlix](../PassportFlix/) voor oude iPads en
iPhones die niet verder komen dan **iOS 12** (iPad Air 1, iPad mini 2/3, e.d.).
Zelfde SMB-scanner, `.nfo`-metadata, artwork, srt-ondertitels en VLC-speler als de
hoofdapp — alleen de interface is eenvoudiger: een doorzoekbaar posterraster in
plaats van de Netflix-rijen.

## Verschillen met de hoofdapp

| | PassportFlix (iOS 16+) | PassportFlix Lite (iOS 12+) |
|---|---|---|
| Interface | SwiftUI: hero, rijen per genre, tabs | UIKit: posterraster + zoeken + sorteren |
| Verder kijken | Eigen rij op het homescherm | Voortgangsbalkje op de poster, hervatten bij afspelen |
| Detailpagina | Fanart, cast-avatars, genre-chips | Fanart, poster, plot, cast als tekst |
| Speler | VLCKit, ondertitel-/audiomenu | Zelfde, via een actiemenu |
| SMB-bibliotheek | AMSMB2 3.x (SPM) | AMSMB2 2.x (CocoaPods; laatste reeks met iOS 12-ondersteuning) |

## Bouwen

```bash
cd PassportFlixLite
xcodegen generate      # maakt PassportFlixLite.xcodeproj
pod install            # MobileVLCKit + AMSMB2 2.x
open PassportFlixLite.xcworkspace
```

Kies je team onder *Signing & Capabilities*, sluit de oude iPad aan en druk op Run.
Met een betaald developer-account blijft de app een jaar geldig op het apparaat;
daarna eenmalig opnieuw installeren.

> **Let op bij het eerste bouwen:** de AMSMB2 2.x-reeks is een oudere bibliotheek;
> mocht een nieuwe Xcode-versie over de Swift-versie struikelen, pin dan een
> specifieke versie in de Podfile (bijv. `pod 'AMSMB2', '2.6.1'`). De hoofdklasse
> heet in 2.x `AMSMB2` (in 3.x werd dat `SMB2Manager`) — daar gaat
> `Sources/Services/SMBService.swift` al van uit.

De instellingen (standaard `192.168.60.1`, share `Storage`, gasttoegang), de
mappenstructuur op de schijf en de werking zijn identiek aan de hoofdapp — zie de
[README van PassportFlix](../PassportFlix/README.md).

## Beperkingen op oude hardware

- 1 GB werkgeheugen: de artwork-cache is bewust klein gehouden.
- De A7-chip decodeert H.264 tot 1080p prima in hardware; HEVC/x265 gaat via
  software en is boven 720p meestal niet vloeiend. 4K kun je vergeten.
- iOS 12 kent geen SF Symbols; de tab-iconen worden programmatisch getekend en de
  spelerknoppen gebruiken tekstsymbolen.
