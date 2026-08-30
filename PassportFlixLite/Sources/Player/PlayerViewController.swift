import UIKit
import MobileVLCKit

/// Volledig scherm met de VLC-videospeler: streamt rechtstreeks via smb:// van
/// de WD en koppelt losse .srt-bestanden (eerst lokaal opgehaald) als
/// ondertitelsporen, naast eventuele in het bestand ingebedde sporen.
final class PlayerViewController: UIViewController, VLCMediaPlayerDelegate, UIGestureRecognizerDelegate {

    private let movie: Movie
    private let player = VLCMediaPlayer()

    private let videoView = UIView()
    private let overlay = UIView()
    private let closeButton = UIButton(type: .system)
    private let titleLabel = UILabel()
    private let tracksButton = UIButton(type: .system)
    private let backwardButton = UIButton(type: .system)
    private let playPauseButton = UIButton(type: .system)
    private let forwardButton = UIButton(type: .system)
    private let slider = UISlider()
    private let timeLabel = UILabel()
    private let remainingLabel = UILabel()
    private let spinner = UIActivityIndicatorView(style: .whiteLarge)

    private var hideTimer: Timer?
    private var isScrubbing = false
    private var didApplyResume = false
    private var didStart = false

    init(movie: Movie) {
        self.movie = movie
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        buildLayout()

        player.delegate = self
        player.drawable = videoView

        let tap = UITapGestureRecognizer(target: self, action: #selector(toggleOverlay))
        tap.delegate = self
        view.addGestureRecognizer(tap)

        spinner.startAnimating()
        prepareAndPlay()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        saveProgress()
        player.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    // MARK: - Start

    private func prepareAndPlay() {
        guard let url = SMBService.streamURL(for: movie.videoPath,
                                             settings: SettingsStore.shared.settings) else {
            showError("Kon geen stream-adres opbouwen voor dit bestand.")
            return
        }

        // Eerst alle .srt-bestanden lokaal ophalen; kleine bestanden, dus snel.
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("subtitles", isDirectory: true)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)

        let group = DispatchGroup()
        var subtitleURLs: [URL] = []
        let lock = NSLock()

        for subtitle in movie.subtitles {
            group.enter()
            SMBService.shared.readFile(atPath: subtitle.path) { result in
                if case .success(let data) = result {
                    let fileName = (subtitle.path as NSString).lastPathComponent
                    let localURL = tempDir.appendingPathComponent("\(abs(subtitle.path.hashValue))-\(fileName)")
                    if (try? data.write(to: localURL)) != nil {
                        lock.lock()
                        subtitleURLs.append(localURL)
                        lock.unlock()
                    }
                }
                group.leave()
            }
        }

        group.notify(queue: .main) { [weak self] in
            guard let self, !self.didStart else { return }
            self.didStart = true
            let media = VLCMedia(url: url)
            // Ruime netwerkbuffer voor het streamen over de wifi van de WD.
            media.addOption(":network-caching=3000")
            self.player.media = media
            for subtitleURL in subtitleURLs {
                self.player.addPlaybackSlave(subtitleURL, type: .subtitle, enforce: false)
            }
            self.player.play()
            UIApplication.shared.isIdleTimerDisabled = true
            self.scheduleAutoHide()
        }
    }

    // MARK: - VLCMediaPlayerDelegate

    func mediaPlayerStateChanged(_ aNotification: Notification) {
        switch player.state {
        case .playing:
            spinner.stopAnimating()
            playPauseButton.setTitle("❚❚", for: .normal)
            if !didApplyResume {
                didApplyResume = true
                if let fraction = ProgressStore.shared.fraction(for: movie),
                   fraction > 0.02, fraction < 0.95 {
                    player.position = Float(fraction)
                }
            }
        case .paused, .stopped:
            playPauseButton.setTitle("▶", for: .normal)
        case .error:
            spinner.stopAnimating()
            showError("Afspelen mislukt. Controleer de verbinding met de WD en of het bestandsformaat wordt ondersteund.")
        case .ended:
            ProgressStore.shared.setFraction(1.0, for: movie)
            dismiss(animated: true)
        default:
            break
        }
    }

    func mediaPlayerTimeChanged(_ aNotification: Notification) {
        spinner.stopAnimating()
        if !isScrubbing {
            slider.value = player.position
        }
        timeLabel.text = Self.format(milliseconds: player.time.intValue)
        if let length = player.media?.length.intValue, length > 0 {
            remainingLabel.text = "-" + Self.format(milliseconds: max(0, length - player.time.intValue))
        }
    }

    // MARK: - Acties

    @objc private func closeTapped() {
        saveProgress()
        player.stop()
        dismiss(animated: true)
    }

    @objc private func playPauseTapped() {
        if player.isPlaying {
            player.pause()
        } else {
            player.play()
        }
        scheduleAutoHide()
    }

    @objc private func backwardTapped() {
        player.jumpBackward(10)
        scheduleAutoHide()
    }

    @objc private func forwardTapped() {
        player.jumpForward(10)
        scheduleAutoHide()
    }

    @objc private func sliderTouchDown() {
        isScrubbing = true
        hideTimer?.invalidate()
    }

    @objc private func sliderTouchUp() {
        player.position = slider.value
        isScrubbing = false
        scheduleAutoHide()
    }

    @objc private func showTracks() {
        let sheet = UIAlertController(title: "Ondertiteling en audio", message: nil,
                                      preferredStyle: .actionSheet)

        let subIndexes = (player.videoSubTitlesIndexes as? [NSNumber]) ?? []
        let subNames = (player.videoSubTitlesNames as? [String]) ?? []
        let current = player.currentVideoSubTitleIndex
        sheet.addAction(UIAlertAction(title: current == -1 ? "Ondertiteling uit ✓" : "Ondertiteling uit",
                                      style: .default) { [weak self] _ in
            self?.player.currentVideoSubTitleIndex = -1
        })
        for (index, name) in zip(subIndexes, subNames) where index.int32Value != -1 {
            let check = current == index.int32Value ? " ✓" : ""
            sheet.addAction(UIAlertAction(title: name + check, style: .default) { [weak self] _ in
                self?.player.currentVideoSubTitleIndex = index.int32Value
            })
        }

        let audioIndexes = (player.audioTrackIndexes as? [NSNumber]) ?? []
        let audioNames = (player.audioTrackNames as? [String]) ?? []
        if audioIndexes.count > 2 { // -1 ("uit") telt mee
            let currentAudio = player.currentAudioTrackIndex
            for (index, name) in zip(audioIndexes, audioNames) where index.int32Value != -1 {
                let check = currentAudio == index.int32Value ? " ✓" : ""
                sheet.addAction(UIAlertAction(title: "Audio: \(name)\(check)", style: .default) { [weak self] _ in
                    self?.player.currentAudioTrackIndex = index.int32Value
                })
            }
        }

        sheet.addAction(UIAlertAction(title: "Annuleer", style: .cancel))
        sheet.popoverPresentationController?.sourceView = tracksButton
        sheet.popoverPresentationController?.sourceRect = tracksButton.bounds
        present(sheet, animated: true)
    }

    @objc private func toggleOverlay() {
        let hide = !overlay.isHidden
        if hide {
            UIView.animate(withDuration: 0.25, animations: { self.overlay.alpha = 0 }) { _ in
                self.overlay.isHidden = true
            }
        } else {
            overlay.isHidden = false
            UIView.animate(withDuration: 0.25) { self.overlay.alpha = 1 }
            scheduleAutoHide()
        }
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        !(touch.view is UIControl)
    }

    // MARK: - Hulpfuncties

    private func saveProgress() {
        let position = Double(player.position)
        if position > 0 {
            ProgressStore.shared.setFraction(position, for: movie)
        }
    }

    private func scheduleAutoHide() {
        hideTimer?.invalidate()
        guard !overlay.isHidden else { return }
        hideTimer = Timer.scheduledTimer(withTimeInterval: 4, repeats: false) { [weak self] _ in
            guard let self, !self.isScrubbing else { return }
            UIView.animate(withDuration: 0.25, animations: { self.overlay.alpha = 0 }) { _ in
                self.overlay.isHidden = true
            }
        }
    }

    private func showError(_ message: String) {
        let alert = UIAlertController(title: "Kan niet afspelen", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Sluiten", style: .default) { [weak self] _ in
            self?.dismiss(animated: true)
        })
        present(alert, animated: true)
    }

    private static func format(milliseconds: Int32) -> String {
        let totalSeconds = Int(milliseconds) / 1000
        let hours = totalSeconds / 3600
        let minutes = (totalSeconds % 3600) / 60
        let seconds = totalSeconds % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%d:%02d", minutes, seconds)
    }

    // MARK: - Layout

    private func buildLayout() {
        videoView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(videoView)

        overlay.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(overlay)

        spinner.hidesWhenStopped = true
        spinner.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(spinner)

        closeButton.setTitle("✕", for: .normal)
        style(button: closeButton, size: 20)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)

        titleLabel.text = movie.title
        titleLabel.textColor = .white
        titleLabel.font = UIFont.systemFont(ofSize: 16, weight: .semibold)
        titleLabel.textAlignment = .center
        titleLabel.translatesAutoresizingMaskIntoConstraints = false

        tracksButton.setTitle("CC", for: .normal)
        style(button: tracksButton, size: 15)
        tracksButton.titleLabel?.font = UIFont.systemFont(ofSize: 15, weight: .bold)
        tracksButton.addTarget(self, action: #selector(showTracks), for: .touchUpInside)

        backwardButton.setTitle("↺10", for: .normal)
        style(button: backwardButton, size: 26, background: false)
        backwardButton.addTarget(self, action: #selector(backwardTapped), for: .touchUpInside)

        playPauseButton.setTitle("▶", for: .normal)
        style(button: playPauseButton, size: 44, background: false)
        playPauseButton.addTarget(self, action: #selector(playPauseTapped), for: .touchUpInside)

        forwardButton.setTitle("↻10", for: .normal)
        style(button: forwardButton, size: 26, background: false)
        forwardButton.addTarget(self, action: #selector(forwardTapped), for: .touchUpInside)

        slider.minimumTrackTintColor = Theme.accent
        slider.maximumTrackTintColor = UIColor(white: 1, alpha: 0.3)
        slider.translatesAutoresizingMaskIntoConstraints = false
        slider.addTarget(self, action: #selector(sliderTouchDown), for: .touchDown)
        slider.addTarget(self, action: #selector(sliderTouchUp), for: [.touchUpInside, .touchUpOutside, .touchCancel])

        timeLabel.text = "0:00"
        remainingLabel.text = "-:--"
        for label in [timeLabel, remainingLabel] {
            label.textColor = .white
            label.font = UIFont.monospacedDigitSystemFont(ofSize: 12, weight: .regular)
            label.translatesAutoresizingMaskIntoConstraints = false
        }

        for control in [closeButton, tracksButton, backwardButton, playPauseButton, forwardButton] {
            control.translatesAutoresizingMaskIntoConstraints = false
            overlay.addSubview(control)
        }
        overlay.addSubview(titleLabel)
        overlay.addSubview(slider)
        overlay.addSubview(timeLabel)
        overlay.addSubview(remainingLabel)

        let safe = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            videoView.topAnchor.constraint(equalTo: view.topAnchor),
            videoView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            videoView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            videoView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            overlay.topAnchor.constraint(equalTo: view.topAnchor),
            overlay.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            overlay.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            overlay.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            spinner.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: view.centerYAnchor),

            closeButton.topAnchor.constraint(equalTo: safe.topAnchor, constant: 12),
            closeButton.leadingAnchor.constraint(equalTo: safe.leadingAnchor, constant: 16),
            closeButton.widthAnchor.constraint(equalToConstant: 40),
            closeButton.heightAnchor.constraint(equalToConstant: 40),

            tracksButton.topAnchor.constraint(equalTo: safe.topAnchor, constant: 12),
            tracksButton.trailingAnchor.constraint(equalTo: safe.trailingAnchor, constant: -16),
            tracksButton.widthAnchor.constraint(equalToConstant: 40),
            tracksButton.heightAnchor.constraint(equalToConstant: 40),

            titleLabel.centerYAnchor.constraint(equalTo: closeButton.centerYAnchor),
            titleLabel.leadingAnchor.constraint(equalTo: closeButton.trailingAnchor, constant: 12),
            titleLabel.trailingAnchor.constraint(equalTo: tracksButton.leadingAnchor, constant: -12),

            playPauseButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            playPauseButton.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            backwardButton.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            backwardButton.trailingAnchor.constraint(equalTo: playPauseButton.leadingAnchor, constant: -56),
            forwardButton.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            forwardButton.leadingAnchor.constraint(equalTo: playPauseButton.trailingAnchor, constant: 56),

            timeLabel.leadingAnchor.constraint(equalTo: safe.leadingAnchor, constant: 16),
            timeLabel.bottomAnchor.constraint(equalTo: safe.bottomAnchor, constant: -18),
            remainingLabel.trailingAnchor.constraint(equalTo: safe.trailingAnchor, constant: -16),
            remainingLabel.centerYAnchor.constraint(equalTo: timeLabel.centerYAnchor),
            slider.leadingAnchor.constraint(equalTo: timeLabel.trailingAnchor, constant: 12),
            slider.trailingAnchor.constraint(equalTo: remainingLabel.leadingAnchor, constant: -12),
            slider.centerYAnchor.constraint(equalTo: timeLabel.centerYAnchor)
        ])
    }

    private func style(button: UIButton, size: CGFloat, background: Bool = true) {
        button.setTitleColor(.white, for: .normal)
        button.titleLabel?.font = UIFont.systemFont(ofSize: size, weight: .semibold)
        if background {
            button.backgroundColor = UIColor(white: 0, alpha: 0.55)
            button.layer.cornerRadius = 20
        }
    }
}
