# PassportFlix

Een native iPhone/iPad-app (SwiftUI) die een **Netflix-achtige interface** toont voor de
films op een **WD My Passport Wireless Pro**. De app verbindt via het wifi-netwerk van de
WD, scant de mappen op filmbestanden en gebruikt de bijbehorende `.nfo`-bestanden
(Kodi-XML) voor metadata, `.srt`-bestanden voor ondertiteling en poster/fanart-afbeeldingen
voor de artwork.

## Functies

- **Netflix-achtig homescherm**: uitgelichte film (hero), rijen met *Verder kijken*,
  *Onlangs toegevoegd*, *Hoog gewaardeerd* en per genre.
- **Filmoverzicht**: doorzoekbaar raster (titel of acteur), sorteren op titel, jaar,
  waardering of toevoegdatum, filteren op genre.
- **Detailpagina**: fanart, poster, plot, tagline, genres, regisseur, cast, leeftijdskeuring,
  speelduur, bestandsinfo.
- **Videospeler op basis van VLCKit**: speelt vrijwel elk formaat (ook MKV/AVI) rechtstreeks
  als stream vanaf de WD, met keuze uit ondertitelsporen (losse `.srt`-bestanden én ingebedde
  sporen) en audiosporen, 10 s vooruit/terug, scrubben en automatisch hervatten.
- **Verder kijken**: kijkpositie wordt onthouden per film.
- **Offline-vriendelijk**: de gescande bibliotheek en alle artwork worden lokaal gecachet,
  zodat de app direct opstart; alleen voor het afspelen is de WD nodig.

## Vereisten

- Mac met **Xcode 15** of nieuwer
- [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`)
- [CocoaPods](https://cocoapods.org) (`brew install cocoapods`) — alleen voor MobileVLCKit
- iPhone of iPad met **iOS/iPadOS 16** of nieuwer

Gebruikte bibliotheken:

| Bibliotheek | Doel | Integratie |
|---|---|---|
| [AMSMB2](https://github.com/amosavian/AMSMB2) | SMB-verbinding: mappen scannen, `.nfo`/`.srt`/artwork lezen | Swift Package (automatisch via project.yml) |
| [MobileVLCKit](https://code.videolan.org/videolan/VLCKit) | Videoweergave incl. MKV en ondertitels | CocoaPods |

## Bouwen

```bash
cd PassportFlix
xcodegen generate      # maakt PassportFlix.xcodeproj
pod install            # voegt MobileVLCKit toe
open PassportFlix.xcworkspace
```

Kies in Xcode je eigen team onder *Signing & Capabilities* en draai de app op je iPhone of
iPad. (De simulator werkt ook, maar kan uiteraard alleen bij de WD als de Mac met het
WD-netwerk verbonden is.)

## De WD My Passport Wireless Pro voorbereiden

1. Zet de WD aan en verbind je iPad/iPhone met het wifi-netwerk van de WD
   (standaard heet dat *MyPassport*).
2. De app gebruikt standaard het fabrieks-IP **192.168.60.1** en de SMB-share **Storage**
   met gasttoegang — precies zoals de WD uit de doos werkt. Heb je een wachtwoord op de
   share gezet of een andere naam gebruikt, pas dat dan aan onder *Instellingen* in de app.
3. Tik op **Bibliotheek scannen**.

> Tip: gebruikt de WD "verbinden met thuisnetwerk" (doorgeefmodus), dan heeft hij een ander
> IP-adres gekregen van je router; vul dat adres in bij *Instellingen*.

## Mappenstructuur op de schijf

De scanner ondersteunt de gebruikelijke Kodi/Plex-indelingen, bij voorkeur één map per film:

```
Films/
  De Grote Film (2019)/
    De Grote Film (2019).mkv
    De Grote Film (2019).nfo         ← Kodi-XML met titel, plot, genres, cast, rating …
    De Grote Film (2019).nl.srt      ← ondertiteling (taalcode in de naam wordt herkend)
    De Grote Film (2019).en.srt
    poster.jpg                        (of: <naam>-poster.jpg / folder.jpg / cover.jpg)
    fanart.jpg                        (of: <naam>-fanart.jpg / backdrop.jpg)
```

Losse bestanden in één map werken ook, zolang `.nfo`, `.srt` en artwork dezelfde
basisnaam hebben als het filmbestand. Zonder `.nfo` maakt de app zelf een nette titel en
jaartal uit de bestandsnaam (release-ruis zoals `1080p.BluRay.x264` wordt weggefilterd).

- Herkende video-extensies: `mkv, mp4, m4v, mov, avi, wmv, ts, m2ts, webm, mpg, mpeg`
- Bestanden met *sample*/*trailer* in de naam en bestanden kleiner dan 100 MB worden
  overgeslagen, net als verborgen bestanden en een eventuele `Extras`-map.
- Vul in *Instellingen* bij *Map met films* bijv. `Films` in om alleen die submap te
  scannen (sneller dan de hele share).

## Hoe het technisch werkt

- **AMSMB2** verbindt met de SMB-share van de WD. De scanner loopt (max. 4 niveaus diep)
  door de mappen, en leest per film het `.nfo`-bestand (XML-parser die zowel het oude
  `<rating>` als het nieuwe `<ratings><rating><value>`-formaat begrijpt).
- Artwork wordt via SMB gelezen, verkleind en op schijf gecachet.
- Voor het afspelen bouwt de app een `smb://…`-URL die **MobileVLCKit** rechtstreeks
  streamt — er wordt dus niets eerst gedownload. `.srt`-bestanden worden wél eerst naar een
  tijdelijke map gehaald en als ondertitelspoor aan VLC gekoppeld, samen met eventuele in
  het MKV-bestand ingebedde sporen.
- De bibliotheek wordt als JSON gecachet in *Application Support*; kijkposities staan in
  `UserDefaults`.

## Beperkingen

- De WD transcodeert niet: de video wordt 1-op-1 gestreamd. Zeer hoge bitrates (grote
  4K-remuxen) kunnen haperen op het 2,4/5 GHz-wifi van de WD; 1080p speelt doorgaans vlot.
- Meerdere iPads tegelijk kan, maar ze delen dezelfde wifi-bandbreedte van de WD.
- Alleen films; serie-indelingen (`tvshow.nfo`, seizoensmappen) worden nog niet apart
  gegroepeerd — afleveringen verschijnen dan als losse titels.
