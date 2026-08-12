import Foundation

/// Scant de SMB-share op filmbestanden en verzamelt per film de bijbehorende
/// .nfo (metadata), .srt (ondertitels) en artwork (poster/fanart).
///
/// Ondersteunde indelingen:
///   1. Eén map per film:  Films/De Film (2019)/De Film (2019).mkv + .nfo + .srt + poster.jpg
///   2. Losse bestanden:   Films/De Film (2019).mkv + De Film (2019).nfo + ...
struct LibraryScanner {
    let smb: SMBService

    private static let videoExtensions: Set<String> = [
        "mkv", "mp4", "m4v", "mov", "avi", "wmv", "ts", "m2ts", "webm", "mpg", "mpeg"
    ]
    private static let imageExtensions: Set<String> = ["jpg", "jpeg", "png", "webp"]
    private static let maxDepth = 4
    /// Bestanden kleiner dan dit beschouwen we niet als hoofdfilm (trailers, samples).
    private static let minVideoSize: Int64 = 100 * 1024 * 1024

    func scan(rootPath: String, progress: @escaping (String) -> Void) async throws -> [Movie] {
        var movies: [Movie] = []
        try await scanDirectory(path: rootPath, depth: 0, into: &movies, progress: progress)
        return movies.sorted {
            ($0.sortTitle ?? $0.title).localizedCaseInsensitiveCompare($1.sortTitle ?? $1.title) == .orderedAscending
        }
    }

    private func scanDirectory(path: String, depth: Int,
                               into movies: inout [Movie],
                               progress: @escaping (String) -> Void) async throws {
        guard depth <= Self.maxDepth else { return }
        progress(path.isEmpty ? "…" : path)

        let entries = try await smb.listDirectory(atPath: path)
        let files = entries.filter { !$0.isDirectory && !isHidden($0.name) }
        let directories = entries.filter { $0.isDirectory && !isHidden($0.name) }

        let videoFiles = files.filter { entry in
            let ext = fileExtension(of: entry.name)
            guard Self.videoExtensions.contains(ext) else { return false }
            guard entry.size >= Self.minVideoSize else { return false }
            let lower = entry.name.lowercased()
            return !lower.contains("sample") && !lower.contains("trailer")
        }

        for video in videoFiles {
            let movie = await buildMovie(from: video, folderPath: path,
                                         siblings: files, movieCountInFolder: videoFiles.count)
            movies.append(movie)
        }

        for directory in directories {
            try await scanDirectory(path: directory.path, depth: depth + 1,
                                    into: &movies, progress: progress)
        }
    }

    private func buildMovie(from video: SMBService.Entry, folderPath: String,
                            siblings: [SMBService.Entry], movieCountInFolder: Int) async -> Movie {
        let base = baseName(of: video.name)
        let (cleanTitle, cleanYear) = Movie.cleanedTitle(fromFileName: video.name)

        var movie = Movie(
            videoPath: video.path,
            folderPath: folderPath,
            fileName: video.name,
            fileSize: video.size,
            addedDate: video.modified,
            title: cleanTitle,
            year: cleanYear
        )

        // Wanneer de film alleen in zijn eigen map staat, mogen ook generieke
        // bestandsnamen (movie.nfo, poster.jpg, subs.srt) aan hem gekoppeld worden.
        let exclusiveFolder = movieCountInFolder == 1

        // --- .nfo ---
        movie.nfoPath = findSibling(base: base, in: siblings, extensions: ["nfo"])
            ?? (exclusiveFolder ? siblings.first { $0.name.lowercased() == "movie.nfo" }?.path : nil)
            ?? (exclusiveFolder ? siblings.first { fileExtension(of: $0.name) == "nfo" }?.path : nil)

        if let nfoPath = movie.nfoPath, let data = try? await smb.readFile(atPath: nfoPath) {
            NFOParser.apply(nfoData: data, to: &movie)
        }

        // --- artwork ---
        movie.posterPath = findImage(names: ["\(base)-poster", "\(base)"], in: siblings)
            ?? (exclusiveFolder ? findImage(names: ["poster", "folder", "cover", "movie"], in: siblings) : nil)
        movie.fanartPath = findImage(names: ["\(base)-fanart"], in: siblings)
            ?? (exclusiveFolder ? findImage(names: ["fanart", "backdrop", "background"], in: siblings) : nil)

        // --- ondertitels ---
        var subtitles: [Movie.Subtitle] = []
        for file in siblings where fileExtension(of: file.name) == "srt" {
            let subBase = baseName(of: file.name)
            if subBase.lowercased().hasPrefix(base.lowercased()) {
                let suffix = String(subBase.dropFirst(base.count))
                    .trimmingCharacters(in: CharacterSet(charactersIn: "._- "))
                subtitles.append(Movie.Subtitle(path: file.path,
                                                label: languageLabel(from: suffix)))
            } else if exclusiveFolder {
                subtitles.append(Movie.Subtitle(path: file.path,
                                                label: languageLabel(from: subBase)))
            }
        }
        movie.subtitles = subtitles.sorted { $0.label < $1.label }

        return movie
    }

    // MARK: - Helpers

    private func isHidden(_ name: String) -> Bool {
        name.hasPrefix(".") || name.hasPrefix("._") || name == "@eaDir" || name == "#recycle"
            || name.lowercased() == "extras"
    }

    private func fileExtension(of name: String) -> String {
        (name as NSString).pathExtension.lowercased()
    }

    private func baseName(of name: String) -> String {
        (name as NSString).deletingPathExtension
    }

    private func findSibling(base: String, in siblings: [SMBService.Entry],
                             extensions: [String]) -> String? {
        siblings.first {
            extensions.contains(fileExtension(of: $0.name))
                && baseName(of: $0.name).lowercased() == base.lowercased()
        }?.path
    }

    private func findImage(names: [String], in siblings: [SMBService.Entry]) -> String? {
        for name in names {
            if let match = siblings.first(where: {
                Self.imageExtensions.contains(fileExtension(of: $0.name))
                    && baseName(of: $0.name).lowercased() == name.lowercased()
            }) {
                return match.path
            }
        }
        return nil
    }

    private func languageLabel(from token: String) -> String {
        let known: [String: String] = [
            "nl": "Nederlands", "dut": "Nederlands", "nld": "Nederlands", "dutch": "Nederlands",
            "en": "Engels", "eng": "Engels", "english": "Engels",
            "fr": "Frans", "fre": "Frans", "fra": "Frans",
            "de": "Duits", "ger": "Duits", "deu": "Duits",
            "es": "Spaans", "spa": "Spaans",
            "it": "Italiaans", "ita": "Italiaans",
            "forced": "Geforceerd", "sdh": "SDH"
        ]
        let key = token.lowercased()
        if let label = known[key] { return label }
        if token.isEmpty { return "Ondertiteling" }
        return token
    }
}
