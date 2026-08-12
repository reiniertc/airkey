import Foundation

/// Een film zoals gevonden op de WD My Passport Wireless Pro.
/// Alle paden zijn relatief ten opzichte van de root van de SMB-share.
struct Movie: Identifiable, Codable, Hashable {
    var id: String { videoPath }

    let videoPath: String
    let folderPath: String
    let fileName: String
    let fileSize: Int64
    let addedDate: Date?

    var title: String
    var sortTitle: String?
    var originalTitle: String?
    var tagline: String?
    var plot: String?
    var year: Int?
    var runtimeMinutes: Int?
    var mpaa: String?
    var studio: String?
    var rating: Double?
    var genres: [String] = []
    var directors: [String] = []
    var actors: [Actor] = []

    var nfoPath: String?
    var posterPath: String?
    var fanartPath: String?
    var subtitles: [Subtitle] = []

    struct Actor: Codable, Hashable {
        var name: String
        var role: String?
    }

    struct Subtitle: Codable, Hashable, Identifiable {
        var id: String { path }
        var path: String
        var label: String
    }

    var displayYear: String { year.map(String.init) ?? "" }

    var displayRuntime: String? {
        guard let minutes = runtimeMinutes, minutes > 0 else { return nil }
        let h = minutes / 60, m = minutes % 60
        return h > 0 ? "\(h) u \(m) min" : "\(m) min"
    }
}

extension Movie {
    /// Maakt van een bestandsnaam als "Some.Movie.2019.1080p.BluRay.x264.mkv"
    /// een nette titel ("Some Movie") en een jaartal (2019).
    static func cleanedTitle(fromFileName fileName: String) -> (title: String, year: Int?) {
        var name = (fileName as NSString).deletingPathExtension
        name = name.replacingOccurrences(of: ".", with: " ")
            .replacingOccurrences(of: "_", with: " ")

        var year: Int?
        if let regex = try? NSRegularExpression(pattern: #"\b(19|20)\d{2}\b"#),
           let match = regex.firstMatch(in: name, range: NSRange(name.startIndex..., in: name)),
           let range = Range(match.range, in: name) {
            year = Int(name[range])
            // Alles vanaf het jaartal is meestal release-ruis (kwaliteit, codec, groep).
            name = String(name[..<range.lowerBound])
        }

        let noiseTokens = ["1080p", "2160p", "720p", "480p", "4k", "uhd", "bluray", "blu-ray",
                           "brrip", "bdrip", "webrip", "web-dl", "webdl", "hdrip", "dvdrip",
                           "x264", "x265", "h264", "h265", "hevc", "aac", "ac3", "dts",
                           "remux", "extended", "unrated", "proper", "repack"]
        let words = name.split(separator: " ").prefix { word in
            !noiseTokens.contains(word.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]()")))
        }
        var title = words.joined(separator: " ")
            .trimmingCharacters(in: CharacterSet(charactersIn: " -([").union(.whitespaces))
        if title.isEmpty {
            title = (fileName as NSString).deletingPathExtension
        }
        return (title, year)
    }
}
