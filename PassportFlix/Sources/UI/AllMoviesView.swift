import SwiftUI

/// Doorzoekbaar raster met alle films, met sorteeropties.
struct AllMoviesView: View {
    enum SortOption: String, CaseIterable, Identifiable {
        case title = "Titel"
        case year = "Jaar"
        case rating = "Waardering"
        case added = "Onlangs toegevoegd"

        var id: String { rawValue }
    }

    @EnvironmentObject private var library: LibraryStore

    @State private var searchText = ""
    @State private var sortOption: SortOption = .title
    @State private var selectedGenre: String?

    private var genres: [String] {
        Array(Set(library.movies.flatMap(\.genres))).sorted()
    }

    private var filteredMovies: [Movie] {
        var result = library.movies

        if let genre = selectedGenre {
            result = result.filter { $0.genres.contains(genre) }
        }
        if !searchText.isEmpty {
            result = result.filter {
                $0.title.localizedCaseInsensitiveContains(searchText)
                    || ($0.originalTitle?.localizedCaseInsensitiveContains(searchText) ?? false)
                    || $0.actors.contains { $0.name.localizedCaseInsensitiveContains(searchText) }
            }
        }

        switch sortOption {
        case .title:
            result.sort { ($0.sortTitle ?? $0.title).localizedCaseInsensitiveCompare($1.sortTitle ?? $1.title) == .orderedAscending }
        case .year:
            result.sort { ($0.year ?? 0) > ($1.year ?? 0) }
        case .rating:
            result.sort { ($0.rating ?? 0) > ($1.rating ?? 0) }
        case .added:
            result.sort { ($0.addedDate ?? .distantPast) > ($1.addedDate ?? .distantPast) }
        }
        return result
    }

    private let columns = [GridItem(.adaptive(minimum: 110, maximum: 160), spacing: 12)]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVGrid(columns: columns, spacing: 16) {
                    ForEach(filteredMovies) { movie in
                        NavigationLink(value: movie) {
                            VStack(spacing: 4) {
                                PosterCard(movie: movie, width: 110)
                                Text(movie.title)
                                    .font(.caption)
                                    .lineLimit(1)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Films (\(filteredMovies.count))")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: Movie.self) { movie in
                MovieDetailView(movie: movie)
            }
            .searchable(text: $searchText, prompt: "Zoek op titel of acteur")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Picker("Sorteren", selection: $sortOption) {
                            ForEach(SortOption.allCases) { option in
                                Text(option.rawValue).tag(option)
                            }
                        }
                        if !genres.isEmpty {
                            Picker("Genre", selection: $selectedGenre) {
                                Text("Alle genres").tag(String?.none)
                                ForEach(genres, id: \.self) { genre in
                                    Text(genre).tag(String?.some(genre))
                                }
                            }
                        }
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                }
            }
        }
    }
}
