import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var library: LibraryStore
    @EnvironmentObject private var settingsStore: SettingsStore
    @EnvironmentObject private var progressStore: ProgressStore

    @State private var playerMovie: Movie?

    var body: some View {
        NavigationStack {
            Group {
                if library.movies.isEmpty {
                    emptyState
                } else {
                    content
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationDestination(for: Movie.self) { movie in
                MovieDetailView(movie: movie)
            }
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("PASSPORTFLIX")
                        .font(.headline.weight(.black))
                        .kerning(2)
                        .foregroundStyle(Theme.accent)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    if library.isBusy {
                        ProgressView()
                    } else {
                        Button {
                            Task { await library.refresh(settings: settingsStore.settings) }
                        } label: {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
            }
            .fullScreenCover(item: $playerMovie) { movie in
                PlayerScreen(movie: movie)
            }
        }
    }

    private var content: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 28) {
                if let featured = library.featured {
                    HeroBanner(movie: featured) {
                        playerMovie = featured
                    }
                }

                let continueWatching = library.continueWatching
                if !continueWatching.isEmpty {
                    MovieRow(title: "Verder kijken", movies: continueWatching)
                }

                if !library.recentlyAdded.isEmpty {
                    MovieRow(title: "Onlangs toegevoegd", movies: library.recentlyAdded)
                }

                if !library.highlyRated.isEmpty {
                    MovieRow(title: "Hoog gewaardeerd", movies: library.highlyRated)
                }

                ForEach(library.genreRows, id: \.genre) { row in
                    MovieRow(title: row.genre, movies: row.movies)
                }
            }
            .padding(.vertical)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            switch library.state {
            case .connecting:
                ProgressView()
                Text("Verbinden met de My Passport Wireless Pro…")
                    .foregroundStyle(.secondary)
            case .scanning(let path):
                ProgressView()
                Text("Bibliotheek scannen…")
                    .foregroundStyle(.secondary)
                Text(path)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
            case .failed(let message):
                Image(systemName: "wifi.exclamationmark")
                    .font(.largeTitle)
                    .foregroundStyle(Theme.accent)
                Text("Geen verbinding")
                    .font(.title2.weight(.bold))
                Text(message)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 32)
                Button("Opnieuw proberen") {
                    Task { await library.refresh(settings: settingsStore.settings) }
                }
                .buttonStyle(.borderedProminent)
            default:
                Image(systemName: "film.stack")
                    .font(.largeTitle)
                    .foregroundStyle(.secondary)
                Text("Nog geen films gevonden")
                    .font(.title2.weight(.bold))
                Text("Verbind je iPad of iPhone met het wifi-netwerk van de WD My Passport Wireless Pro en scan de bibliotheek.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 32)
                Button("Bibliotheek scannen") {
                    Task { await library.refresh(settings: settingsStore.settings) }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Grote uitgelichte film bovenaan het homescherm.
struct HeroBanner: View {
    let movie: Movie
    let onPlay: () -> Void

    var body: some View {
        ZStack(alignment: .bottom) {
            SMBArtworkView(path: movie.fanartPath ?? movie.posterPath, maxPixelSize: 1400)
                .frame(height: 420)
                .clipped()

            LinearGradient(colors: [.clear, .clear, Theme.background.opacity(0.85), Theme.background],
                           startPoint: .top, endPoint: .bottom)

            VStack(spacing: 12) {
                Text(movie.title)
                    .font(.largeTitle.weight(.black))
                    .multilineTextAlignment(.center)
                    .shadow(radius: 8)

                HStack(spacing: 8) {
                    if !movie.displayYear.isEmpty { MetadataBadge(text: movie.displayYear) }
                    if let runtime = movie.displayRuntime { MetadataBadge(text: runtime) }
                    if let rating = movie.rating {
                        MetadataBadge(text: String(format: "★ %.1f", rating))
                    }
                }

                if !movie.genres.isEmpty {
                    Text(movie.genres.prefix(3).joined(separator: " • "))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 12) {
                    Button(action: onPlay) {
                        Label("Afspelen", systemImage: "play.fill")
                            .font(.headline)
                            .padding(.horizontal, 22)
                            .padding(.vertical, 8)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.white)
                    .foregroundStyle(.black)

                    NavigationLink(value: movie) {
                        Label("Meer info", systemImage: "info.circle")
                            .font(.headline)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                    }
                    .buttonStyle(.bordered)
                    .tint(.white)
                }
            }
            .padding(.bottom, 20)
            .padding(.horizontal)
        }
    }
}
