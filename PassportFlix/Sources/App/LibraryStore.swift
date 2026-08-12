import Foundation
import Combine

/// Centrale toestand van de filmbibliotheek: verbinden, scannen, cachen.
@MainActor
final class LibraryStore: ObservableObject {
    enum State: Equatable {
        case idle
        case connecting
        case scanning(String)
        case ready
        case failed(String)
    }

    @Published private(set) var movies: [Movie] = []
    @Published private(set) var state: State = .idle
    @Published private(set) var lastScan: Date?

    private let cacheURL: URL

    init() {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        cacheURL = support.appendingPathComponent("library.json")
        loadCache()
    }

    var isBusy: Bool {
        switch state {
        case .connecting, .scanning: return true
        default: return false
        }
    }

    /// Verbindt met de WD en scant de bibliotheek opnieuw.
    func refresh(settings: ConnectionSettings) async {
        guard !isBusy else { return }
        state = .connecting
        do {
            try await SMBService.shared.ensureConnected(settings)
            state = .scanning("")
            let scanner = LibraryScanner(smb: SMBService.shared)
            let found = try await scanner.scan(rootPath: settings.normalizedRootPath) { [weak self] path in
                Task { @MainActor in
                    if case .scanning = self?.state { self?.state = .scanning(path) }
                }
            }
            movies = found
            lastScan = Date()
            state = .ready
            saveCache()
        } catch {
            state = .failed(friendlyMessage(for: error))
        }
    }

    /// Zorgt dat er een SMB-verbinding is (voor artwork en afspelen)
    /// zonder opnieuw te scannen — bijv. na een app-herstart met cache.
    func ensureConnection(settings: ConnectionSettings) async {
        do {
            try await SMBService.shared.ensureConnected(settings)
            if case .failed = state { state = movies.isEmpty ? .idle : .ready }
            if state == .idle && !movies.isEmpty { state = .ready }
        } catch {
            if movies.isEmpty { state = .failed(friendlyMessage(for: error)) }
        }
    }

    // MARK: - Afgeleide collecties voor de interface

    var continueWatching: [Movie] {
        let fractions = ProgressStore.shared.fractions
        return movies
            .filter { fractions[$0.videoPath] != nil }
            .sorted { (fractions[$0.videoPath] ?? 0) > (fractions[$1.videoPath] ?? 0) }
    }

    var recentlyAdded: [Movie] {
        movies
            .filter { $0.addedDate != nil }
            .sorted { ($0.addedDate ?? .distantPast) > ($1.addedDate ?? .distantPast) }
            .prefix(20)
            .map { $0 }
    }

    var highlyRated: [Movie] {
        movies.filter { ($0.rating ?? 0) >= 7.5 }
            .sorted { ($0.rating ?? 0) > ($1.rating ?? 0) }
    }

    /// De meest voorkomende genres, elk met hun films.
    var genreRows: [(genre: String, movies: [Movie])] {
        var byGenre: [String: [Movie]] = [:]
        for movie in movies {
            for genre in movie.genres {
                byGenre[genre, default: []].append(movie)
            }
        }
        return byGenre
            .filter { $0.value.count >= 2 }
            .sorted { $0.value.count > $1.value.count }
            .prefix(8)
            .map { (genre: $0.key, movies: $0.value) }
    }

    var featured: Movie? {
        let candidates = movies.filter { $0.fanartPath != nil }
        let pool = candidates.isEmpty ? movies : candidates
        guard !pool.isEmpty else { return nil }
        // Stabiel per dag wisselen, zodat de heropende app niet steeds springt.
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        return pool[day % pool.count]
    }

    // MARK: - Cache

    private struct CachePayload: Codable {
        var movies: [Movie]
        var lastScan: Date
    }

    private func loadCache() {
        guard let data = try? Data(contentsOf: cacheURL),
              let payload = try? JSONDecoder().decode(CachePayload.self, from: data) else { return }
        movies = payload.movies
        lastScan = payload.lastScan
        if !movies.isEmpty { state = .ready }
    }

    private func saveCache() {
        guard let data = try? JSONEncoder().encode(CachePayload(movies: movies, lastScan: lastScan ?? Date())) else { return }
        try? data.write(to: cacheURL)
    }

    private func friendlyMessage(for error: Error) -> String {
        let ns = error as NSError
        if ns.domain == NSPOSIXErrorDomain {
            switch Int32(ns.code) {
            case ECONNREFUSED, EHOSTUNREACH, ETIMEDOUT, ENETUNREACH:
                return "De My Passport Wireless Pro is niet bereikbaar. Controleer of je iPad/iPhone met het wifi-netwerk van de WD is verbonden."
            case EACCES, EPERM:
                return "Toegang geweigerd. Controleer gebruikersnaam/wachtwoord in de instellingen."
            default:
                break
            }
        }
        return error.localizedDescription
    }
}
