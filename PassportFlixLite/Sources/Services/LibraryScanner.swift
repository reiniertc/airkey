import Foundation

/// Scant de SMB-share op filmbestanden en verzamelt per film de bijbehorende
/// .nfo (metadata), .srt (ondertitels) en artwork (poster/fanart).
/// Draait volledig op een achtergrondqueue; de SMB-aanroepen worden daar met
/// semaforen synchroon gemaakt zodat de recursie leesbaar blijft.
final class LibraryScanner {

    private static let videoExtensions: Set<String> = [
        "mkv", "mp4", "m4v", "mov", "avi", "wmv", "ts", "m2ts", "webm", "mpg", "mpeg"
    ]
    private static let imageExtensions: Set<String> = ["jpg", "jpeg", "png", "webp"]
    private static let maxDepth = 4
    private static let minVideoSize: Int64 = 100 * 1024 * 1024

    func scan(rootPath: String,
              progress: @escaping (String) -> Void,
              completion: @escaping (Result<[Movie], Error>) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                var movies: [Movie] = []
                try self.scanDirectory(path: rootPath, depth: 0, into: &movies, progress: progress)
                movies.sort {
                    ($0.sortTitle ?? $0.title).localizedCaseInsensitiveCompare($1.sortTitle ?? $1.title) == .orderedAscending
                }
                completion(.success(movies))
            } catch {
                completion(.failure(error))
            }
        }
    }

    // MARK: - Synchronisatiehulpjes (alleen op de achtergrondqueue gebruiken)

    private func listSync(_ path: String) throws -> [SMBService.Entry] {
        var result: Result<[SMBService.Entry], Error> = .failure(SMBService.SMBError.notConnected)
        let semaphore = DispatchSemaphore(value: 0)
        SMBService.shared.listDirectory(atPath: path) { r in
            result = r
            semaphore.signal()
        }
        semaphore.wait()
        return try result.get()
    }

    private func readSync(_ path: String) -> Data? {
        var data: Data?
        let semaphore = DispatchSemaphore(value: 0)
        SMBService.shared.readFile(atPath: path) { r in
            if case .success(let d) = r { data = d }
            semaphore.signal()
        }
        semaphore.wait()
        return data
    }

    // MARK: - Scannen

    private func scanDirectory(path: String, depth: Int,
                               into movies: inout [Movie],
                               progress: @escaping (String) -> Void) throws {
        guard depth <= Self.maxDepth else { return }
        progress(path.isEmpty ? "…" : path)

        let entries = try listSync(path)
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
            movies.append(buildMovie(from: video, folderPath: path,
                                     siblings: files, movieCountInFolder: videoFiles.count))
        }

        for directory in directories {
            try scanDirectory(path: directory.path, depth: depth + 1,
                              into: &movies, progress: progress)
        }
    }

    private func buildMovie(from video: SMBService.Entry, folderPath: String,
                            siblings: [SMBService.Entry], movieCountInFolder: Int) -> Movie {
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

        let exclusiveFolder = movieCountInFolder == 1

        movie.nfoPath = findSibling(base: base, in: siblings, extensions: ["nfo"])
            ?? (exclusiveFolder ? siblings.first { $0.name.lowercased() == "movie.nfo" }?.path : nil)
            ?? (exclusiveFolder ? siblings.first { fileExtension(of: $0.name) == "nfo" }?.path : nil)

        if let nfoPath = movie.nfoPath, let data = readSync(nfoPath) {
            NFOParser.apply(nfoData: data, to: &movie)
        }

        movie.posterPath = findImage(names: ["\(base)-poster", "\(base)"], in: siblings)
            ?? (exclusiveFolder ? findImage(names: ["poster", "folder", "cover", "movie"], in: siblings) : nil)
        movie.fanartPath = findImage(names: ["\(base)-fanart"], in: siblings)
            ?? (exclusiveFolder ? findImage(names: ["fanart", "backdrop", "background"], in: siblings) : nil)

        var subtitles: [Movie.Subtitle] = []
        for file in siblings where fileExtension(of: file.name) == "srt" {
            let subBase = baseName(of: file.name)
            if subBase.lowercased().hasPrefix(base.lowercased()) {
                let suffix = String(subBase.dropFirst(base.count))
                    .trimmingCharacters(in: CharacterSet(charactersIn: "._- "))
                subtitles.append(Movie.Subtitle(path: file.path, label: languageLabel(from: suffix)))
            } else if exclusiveFolder {
                subtitles.append(Movie.Subtitle(path: file.path, label: languageLabel(from: subBase)))
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
