import SwiftUI

struct MovieDetailView: View {
    let movie: Movie

    @EnvironmentObject private var progressStore: ProgressStore
    @State private var showPlayer = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                header

                VStack(alignment: .leading, spacing: 16) {
                    playButtons

                    if let tagline = movie.tagline, !tagline.isEmpty {
                        Text(tagline)
                            .font(.subheadline.italic())
                            .foregroundStyle(.secondary)
                    }

                    if let plot = movie.plot, !plot.isEmpty {
                        Text(plot)
                            .font(.body)
                            .foregroundStyle(.primary.opacity(0.9))
                    }

                    detailsGrid

                    if !movie.actors.isEmpty {
                        castSection
                    }
                }
                .padding()
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .fullScreenCover(isPresented: $showPlayer) {
            PlayerScreen(movie: movie)
        }
    }

    private var header: some View {
        ZStack(alignment: .bottomLeading) {
            SMBArtworkView(path: movie.fanartPath ?? movie.posterPath, maxPixelSize: 1400)
                .frame(height: 260)
                .clipped()
            LinearGradient(colors: [.clear, Theme.background.opacity(0.7), Theme.background],
                           startPoint: .top, endPoint: .bottom)

            HStack(alignment: .bottom, spacing: 14) {
                PosterCard(movie: movie, width: 110)
                    .shadow(radius: 10)

                VStack(alignment: .leading, spacing: 6) {
                    Text(movie.title)
                        .font(.title.weight(.black))
                        .lineLimit(3)
                    HStack(spacing: 8) {
                        if !movie.displayYear.isEmpty { MetadataBadge(text: movie.displayYear) }
                        if let runtime = movie.displayRuntime { MetadataBadge(text: runtime) }
                        if let mpaa = movie.mpaa, !mpaa.isEmpty { MetadataBadge(text: mpaa) }
                        if let rating = movie.rating {
                            MetadataBadge(text: String(format: "★ %.1f", rating))
                        }
                    }
                    if !movie.genres.isEmpty {
                        Text(movie.genres.joined(separator: " • "))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.bottom, 4)
            }
            .padding()
        }
    }

    private var playButtons: some View {
        VStack(spacing: 10) {
            Button {
                showPlayer = true
            } label: {
                Label(progressStore.fraction(for: movie) != nil ? "Verder kijken" : "Afspelen",
                      systemImage: "play.fill")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
            }
            .buttonStyle(.borderedProminent)
            .tint(.white)
            .foregroundStyle(.black)

            if let fraction = progressStore.fraction(for: movie) {
                HStack {
                    ProgressBar(fraction: fraction)
                        .clipShape(Capsule())
                    Button("Opnieuw beginnen") {
                        progressStore.clear(for: movie)
                        showPlayer = true
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }

            if !movie.subtitles.isEmpty {
                Label("Ondertiteling: \(movie.subtitles.map(\.label).joined(separator: ", "))",
                      systemImage: "captions.bubble")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var detailsGrid: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !movie.directors.isEmpty {
                detailRow("Regie", movie.directors.joined(separator: ", "))
            }
            if let studio = movie.studio, !studio.isEmpty {
                detailRow("Studio", studio)
            }
            detailRow("Bestand", movie.fileName)
            detailRow("Grootte", ByteCountFormatter.string(fromByteCount: movie.fileSize, countStyle: .file))
        }
        .padding(.top, 4)
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .frame(width: 70, alignment: .leading)
            Text(value)
                .font(.caption)
                .foregroundStyle(.primary.opacity(0.85))
        }
    }

    private var castSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Cast")
                .font(.title3.weight(.bold))
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 14) {
                    ForEach(movie.actors.prefix(15), id: \.self) { actor in
                        VStack(spacing: 2) {
                            Circle()
                                .fill(Theme.card)
                                .frame(width: 56, height: 56)
                                .overlay(
                                    Text(initials(of: actor.name))
                                        .font(.headline)
                                        .foregroundStyle(.secondary)
                                )
                            Text(actor.name)
                                .font(.caption2.weight(.semibold))
                                .lineLimit(1)
                            if let role = actor.role, !role.isEmpty {
                                Text(role)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .frame(width: 84)
                    }
                }
            }
        }
    }

    private func initials(of name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined()
    }
}
