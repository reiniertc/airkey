import Foundation

/// Parser voor Kodi-stijl .nfo-bestanden (XML met een <movie>-root).
/// Vult een bestaande `Movie` aan met metadata.
enum NFOParser {

    static func apply(nfoData: Data, to movie: inout Movie) {
        guard let xmlData = extractMovieXML(from: nfoData) else { return }
        let delegate = MovieNFODelegate()
        let parser = XMLParser(data: xmlData)
        parser.delegate = delegate
        parser.parse()
        guard delegate.sawMovieElement else { return }

        if let title = delegate.title, !title.isEmpty { movie.title = title }
        movie.sortTitle = delegate.sortTitle ?? movie.sortTitle
        movie.originalTitle = delegate.originalTitle ?? movie.originalTitle
        movie.tagline = delegate.tagline ?? movie.tagline
        movie.plot = delegate.plot ?? delegate.outline ?? movie.plot
        movie.year = delegate.year ?? movie.year
        movie.runtimeMinutes = delegate.runtime ?? movie.runtimeMinutes
        movie.mpaa = delegate.mpaa ?? movie.mpaa
        movie.studio = delegate.studio ?? movie.studio
        movie.rating = delegate.bestRating ?? movie.rating
        if !delegate.genres.isEmpty { movie.genres = delegate.genres }
        if !delegate.directors.isEmpty { movie.directors = delegate.directors }
        if !delegate.actors.isEmpty { movie.actors = delegate.actors }
    }

    /// Sommige nfo-bestanden bevatten na de XML nog een losse URL-regel
    /// (of beginnen met een BOM); knip daarom strikt het <movie>-blok eruit.
    private static func extractMovieXML(from data: Data) -> Data? {
        guard var text = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1) else { return nil }
        text = text.replacingOccurrences(of: "\u{FEFF}", with: "")
        guard let start = text.range(of: "<movie", options: .caseInsensitive) else { return nil }
        guard let end = text.range(of: "</movie>", options: [.caseInsensitive, .backwards]) else { return nil }
        guard start.lowerBound < end.upperBound else { return nil }
        let xml = String(text[start.lowerBound..<end.upperBound])
        return xml.data(using: .utf8)
    }
}

private final class MovieNFODelegate: NSObject, XMLParserDelegate {
    var sawMovieElement = false

    var title: String?
    var sortTitle: String?
    var originalTitle: String?
    var tagline: String?
    var plot: String?
    var outline: String?
    var year: Int?
    var runtime: Int?
    var mpaa: String?
    var studio: String?
    var genres: [String] = []
    var directors: [String] = []
    var actors: [Movie.Actor] = []

    // <rating> (oud) of <ratings><rating name="imdb"><value> (nieuw)
    private var legacyRating: Double?
    private var ratingValues: [Double] = []

    var bestRating: Double? { ratingValues.first ?? legacyRating }

    private var elementStack: [String] = []
    private var text = ""
    private var currentActorName: String?
    private var currentActorRole: String?

    func parser(_ parser: XMLParser, didStartElement elementName: String,
                namespaceURI: String?, qualifiedName qName: String?,
                attributes attributeDict: [String: String] = [:]) {
        let element = elementName.lowercased()
        elementStack.append(element)
        text = ""
        if element == "movie" { sawMovieElement = true }
        if element == "actor" {
            currentActorName = nil
            currentActorRole = nil
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        text += string
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String,
                namespaceURI: String?, qualifiedName qName: String?) {
        let element = elementName.lowercased()
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let parent = elementStack.count >= 2 ? elementStack[elementStack.count - 2] : ""
        elementStack.removeLast()

        // Alleen directe kinderen van <movie> als platte velden lezen,
        // zodat bijv. <set><name> de titel niet overschrijft.
        let isTopLevel = parent == "movie"

        switch element {
        case "title" where isTopLevel: title = value
        case "sorttitle" where isTopLevel: sortTitle = value
        case "originaltitle" where isTopLevel: originalTitle = value
        case "tagline" where isTopLevel: tagline = value
        case "plot" where isTopLevel: plot = value
        case "outline" where isTopLevel: outline = value
        case "year" where isTopLevel: year = Int(value)
        case "runtime" where isTopLevel:
            runtime = Int(value.components(separatedBy: CharacterSet.decimalDigits.inverted).joined())
        case "mpaa" where isTopLevel: mpaa = value
        case "studio" where isTopLevel:
            if studio == nil { studio = value }
        case "genre" where isTopLevel:
            // Kan één element met scheidingstekens zijn, of meerdere elementen.
            let parts = value.components(separatedBy: CharacterSet(charactersIn: "/,"))
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }
            genres.append(contentsOf: parts)
        case "director" where isTopLevel:
            if !value.isEmpty { directors.append(value) }
        case "rating" where isTopLevel:
            legacyRating = Double(value.replacingOccurrences(of: ",", with: "."))
        case "value" where parent == "rating":
            if let v = Double(value.replacingOccurrences(of: ",", with: ".")) {
                ratingValues.append(v)
            }
        case "name" where parent == "actor":
            currentActorName = value
        case "role" where parent == "actor":
            currentActorRole = value
        case "actor":
            if let name = currentActorName, !name.isEmpty {
                actors.append(Movie.Actor(name: name, role: currentActorRole))
            }
        default:
            break
        }
        text = ""
    }
}
