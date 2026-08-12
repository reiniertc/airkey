import SwiftUI

/// Toont een afbeelding die via SMB van de WD wordt geladen (met cache).
struct SMBArtworkView: View {
    let path: String?
    var maxPixelSize: CGFloat = 800

    @State private var image: UIImage?

    var body: some View {
        ZStack {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                Rectangle().fill(Theme.card)
            }
        }
        .task(id: path) {
            image = nil
            guard let path else { return }
            image = await ArtworkCache.shared.image(forSMBPath: path, maxPixelSize: maxPixelSize)
        }
    }
}

/// Posterkaart zoals in een Netflix-rij. Valt terug op een titelkaart
/// wanneer er geen poster bij de film gevonden is.
struct PosterCard: View {
    let movie: Movie
    var width: CGFloat = 120

    @EnvironmentObject private var progressStore: ProgressStore

    var body: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .bottom) {
                if movie.posterPath != nil {
                    SMBArtworkView(path: movie.posterPath, maxPixelSize: 500)
                } else {
                    fallback
                }
                if let fraction = progressStore.fraction(for: movie) {
                    ProgressBar(fraction: fraction)
                }
            }
        }
        .frame(width: width, height: width * 1.5)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(Color.white.opacity(0.08))
        )
    }

    private var fallback: some View {
        ZStack {
            LinearGradient(colors: [Theme.card, Color(white: 0.05)],
                           startPoint: .top, endPoint: .bottom)
            VStack(spacing: 6) {
                Image(systemName: "film")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                Text(movie.title)
                    .font(.caption.weight(.semibold))
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
                if !movie.displayYear.isEmpty {
                    Text(movie.displayYear)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(8)
        }
    }
}

struct ProgressBar: View {
    let fraction: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Rectangle().fill(Color.white.opacity(0.3))
                Rectangle().fill(Theme.accent)
                    .frame(width: geo.size.width * min(max(fraction, 0), 1))
            }
        }
        .frame(height: 4)
    }
}

/// Horizontale rij met posters, met een titel erboven.
struct MovieRow: View {
    let title: String
    let movies: [Movie]
    var cardWidth: CGFloat = 120

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.title3.weight(.bold))
                .padding(.horizontal)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 10) {
                    ForEach(movies) { movie in
                        NavigationLink(value: movie) {
                            PosterCard(movie: movie, width: cardWidth)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal)
            }
        }
    }
}

struct MetadataBadge: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Color.white.opacity(0.12), in: Capsule())
    }
}
