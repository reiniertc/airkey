import SwiftUI
import MobileVLCKit

/// Volledig scherm met de videospeler en Netflix-achtige besturing.
struct PlayerScreen: View {
    let movie: Movie

    @EnvironmentObject private var settingsStore: SettingsStore
    @EnvironmentObject private var progressStore: ProgressStore
    @Environment(\.dismiss) private var dismiss

    @StateObject private var controller = PlayerController()
    @State private var showControls = true
    @State private var hideControlsTask: Task<Void, Never>?
    @State private var preparing = true
    @State private var prepareError: String?

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VideoSurface(player: controller.player)
                .ignoresSafeArea()

            if preparing || controller.isBuffering {
                ProgressView()
                    .controlSize(.large)
                    .tint(.white)
            }

            if let message = prepareError ?? controller.errorMessage {
                errorOverlay(message)
            } else if showControls {
                controlsOverlay
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            withAnimation { showControls.toggle() }
            scheduleAutoHide()
        }
        .statusBarHidden(true)
        .persistentSystemOverlays(.hidden)
        .task { await prepareAndPlay() }
        .onDisappear {
            controller.stop()
        }
    }

    // MARK: - Voorbereiden

    /// Downloadt de .srt-bestanden van de WD naar een tijdelijke map (VLC kan
    /// lokale bestanden betrouwbaar als ondertitelspoor koppelen) en start de stream.
    private func prepareAndPlay() async {
        guard let url = SMBService.streamURL(for: movie.videoPath, settings: settingsStore.settings) else {
            prepareError = "Kon geen stream-adres opbouwen voor dit bestand."
            preparing = false
            return
        }

        var subtitleURLs: [URL] = []
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("subtitles", isDirectory: true)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)

        for subtitle in movie.subtitles {
            if let data = try? await SMBService.shared.readFile(atPath: subtitle.path) {
                let fileName = (subtitle.path as NSString).lastPathComponent
                let localURL = tempDir.appendingPathComponent("\(abs(subtitle.path.hashValue))-\(fileName)")
                if (try? data.write(to: localURL)) != nil {
                    subtitleURLs.append(localURL)
                }
            }
        }

        controller.onProgress = { fraction in
            progressStore.setFraction(fraction, for: movie)
        }
        controller.start(url: url,
                         subtitleURLs: subtitleURLs,
                         resumeFraction: progressStore.fraction(for: movie))
        preparing = false
        scheduleAutoHide()
    }

    // MARK: - Besturing

    private var controlsOverlay: some View {
        VStack {
            HStack {
                Button {
                    close()
                } label: {
                    Image(systemName: "xmark")
                        .font(.title3.weight(.bold))
                        .padding(10)
                        .background(.black.opacity(0.5), in: Circle())
                }
                Spacer()
                Text(movie.title)
                    .font(.headline)
                    .lineLimit(1)
                Spacer()
                trackMenu
            }
            .padding()

            Spacer()

            HStack(spacing: 44) {
                Button { controller.jump(seconds: -10) } label: {
                    Image(systemName: "gobackward.10").font(.largeTitle)
                }
                Button { controller.togglePlayPause() } label: {
                    Image(systemName: controller.isPlaying ? "pause.fill" : "play.fill")
                        .font(.system(size: 52))
                }
                Button { controller.jump(seconds: 10) } label: {
                    Image(systemName: "goforward.10").font(.largeTitle)
                }
            }

            Spacer()

            HStack(spacing: 12) {
                Text(controller.timeText)
                    .font(.caption.monospacedDigit())
                Slider(
                    value: Binding(
                        get: { controller.position },
                        set: { controller.position = $0 }
                    ),
                    in: 0...1
                ) { editing in
                    if editing {
                        controller.beginScrubbing()
                    } else {
                        controller.endScrubbing(at: controller.position)
                    }
                    scheduleAutoHide()
                }
                .tint(Theme.accent)
                Text(controller.remainingText)
                    .font(.caption.monospacedDigit())
            }
            .padding(.horizontal)
            .padding(.bottom, 24)
        }
        .foregroundStyle(.white)
        .background(
            LinearGradient(colors: [.black.opacity(0.6), .clear, .clear, .black.opacity(0.7)],
                           startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea()
            .allowsHitTesting(false)
        )
        .transition(.opacity)
    }

    private var trackMenu: some View {
        Menu {
            if !controller.subtitleTracks.isEmpty {
                Section("Ondertiteling") {
                    Button {
                        controller.selectSubtitle(index: -1)
                    } label: {
                        labelRow("Uit", selected: controller.currentSubtitleIndex == -1)
                    }
                    ForEach(controller.subtitleTracks) { track in
                        Button {
                            controller.selectSubtitle(index: track.index)
                        } label: {
                            labelRow(track.name, selected: controller.currentSubtitleIndex == track.index)
                        }
                    }
                }
            }
            if controller.audioTracks.count > 1 {
                Section("Audio") {
                    ForEach(controller.audioTracks) { track in
                        Button {
                            controller.selectAudio(index: track.index)
                        } label: {
                            labelRow(track.name, selected: controller.currentAudioIndex == track.index)
                        }
                    }
                }
            }
        } label: {
            Image(systemName: "captions.bubble")
                .font(.title3.weight(.bold))
                .padding(10)
                .background(.black.opacity(0.5), in: Circle())
        }
    }

    private func labelRow(_ text: String, selected: Bool) -> some View {
        HStack {
            Text(text)
            if selected { Image(systemName: "checkmark") }
        }
    }

    private func errorOverlay(_ message: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(Theme.accent)
            Text(message)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white)
                .padding(.horizontal, 40)
            Button("Sluiten") { close() }
                .buttonStyle(.borderedProminent)
        }
    }

    private func close() {
        controller.stop()
        dismiss()
    }

    private func scheduleAutoHide() {
        hideControlsTask?.cancel()
        guard showControls else { return }
        hideControlsTask = Task {
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            guard !Task.isCancelled else { return }
            withAnimation { showControls = false }
        }
    }
}

/// UIKit-oppervlak waar VLC de video op tekent.
private struct VideoSurface: UIViewRepresentable {
    let player: VLCMediaPlayer

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        player.drawable = view
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}
