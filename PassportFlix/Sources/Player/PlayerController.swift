import Foundation
import MobileVLCKit
import UIKit

/// Bestuurt de VLC-mediaspeler: streamt de film rechtstreeks via smb:// van de
/// WD My Passport Wireless Pro en koppelt losse .srt-bestanden als ondertitelsporen.
final class PlayerController: NSObject, ObservableObject, VLCMediaPlayerDelegate {

    struct Track: Identifiable, Equatable {
        let index: Int32
        let name: String
        var id: Int32 { index }
    }

    let player = VLCMediaPlayer()

    @Published var isPlaying = false
    @Published var isBuffering = true
    @Published var position: Float = 0
    @Published var timeText = "0:00"
    @Published var remainingText = "-:--"
    @Published var subtitleTracks: [Track] = []
    @Published var audioTracks: [Track] = []
    @Published var currentSubtitleIndex: Int32 = -1
    @Published var currentAudioIndex: Int32 = -1
    @Published var errorMessage: String?

    /// Wordt periodiek aangeroepen met de kijkpositie (0...1) voor "Verder kijken".
    var onProgress: ((Double) -> Void)?

    private var resumeFraction: Double?
    private var didApplyResume = false
    private var isScrubbing = false

    override init() {
        super.init()
        player.delegate = self
    }

    func start(url: URL, subtitleURLs: [URL], resumeFraction: Double?) {
        self.resumeFraction = resumeFraction
        let media = VLCMedia(url: url)
        // Ruime netwerkbuffer voor streamen over de wifi van de WD.
        media.addOption(":network-caching=3000")
        player.media = media
        for subtitleURL in subtitleURLs {
            player.addPlaybackSlave(subtitleURL, type: .subtitle, enforce: false)
        }
        player.play()
        UIApplication.shared.isIdleTimerDisabled = true
    }

    func stop() {
        onProgress?(Double(player.position))
        player.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func togglePlayPause() {
        if player.isPlaying {
            player.pause()
        } else {
            player.play()
        }
    }

    func jump(seconds: Int32) {
        if seconds >= 0 {
            player.jumpForward(seconds)
        } else {
            player.jumpBackward(-seconds)
        }
    }

    func beginScrubbing() {
        isScrubbing = true
    }

    func endScrubbing(at fraction: Float) {
        player.position = fraction
        isScrubbing = false
    }

    func selectSubtitle(index: Int32) {
        player.currentVideoSubTitleIndex = index
        currentSubtitleIndex = index
    }

    func selectAudio(index: Int32) {
        player.currentAudioTrackIndex = index
        currentAudioIndex = index
    }

    // MARK: - VLCMediaPlayerDelegate

    func mediaPlayerStateChanged(_ aNotification: Notification) {
        switch player.state {
        case .playing:
            isPlaying = true
            isBuffering = false
            applyResumeIfNeeded()
            refreshTracks()
        case .paused, .stopped:
            isPlaying = false
        case .buffering, .opening:
            isBuffering = player.isPlaying == false
        case .error:
            isPlaying = false
            isBuffering = false
            errorMessage = "Afspelen mislukt. Controleer de verbinding met de WD en of het bestandsformaat wordt ondersteund."
        case .ended:
            isPlaying = false
            onProgress?(1.0)
        default:
            break
        }
    }

    func mediaPlayerTimeChanged(_ aNotification: Notification) {
        isBuffering = false
        if !isScrubbing {
            position = player.position
        }
        timeText = format(milliseconds: player.time.intValue)
        if let length = player.media?.length.intValue, length > 0 {
            remainingText = "-" + format(milliseconds: max(0, length - player.time.intValue))
        }
        if subtitleTracks.isEmpty || audioTracks.isEmpty {
            refreshTracks()
        }
        onProgress?(Double(player.position))
    }

    // MARK: - Intern

    private func applyResumeIfNeeded() {
        guard !didApplyResume else { return }
        didApplyResume = true
        if let fraction = resumeFraction, fraction > 0.02, fraction < 0.95 {
            player.position = Float(fraction)
        }
    }

    private func refreshTracks() {
        let subIndexes = (player.videoSubTitlesIndexes as? [NSNumber]) ?? []
        let subNames = (player.videoSubTitlesNames as? [String]) ?? []
        subtitleTracks = zip(subIndexes, subNames).map { Track(index: $0.int32Value, name: $1) }
        currentSubtitleIndex = player.currentVideoSubTitleIndex

        let audioIndexes = (player.audioTrackIndexes as? [NSNumber]) ?? []
        let audioNames = (player.audioTrackNames as? [String]) ?? []
        audioTracks = zip(audioIndexes, audioNames).map { Track(index: $0.int32Value, name: $1) }
        currentAudioIndex = player.currentAudioTrackIndex
    }

    private func format(milliseconds: Int32) -> String {
        let totalSeconds = Int(milliseconds) / 1000
        let hours = totalSeconds / 3600
        let minutes = (totalSeconds % 3600) / 60
        let seconds = totalSeconds % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%d:%02d", minutes, seconds)
    }
}
