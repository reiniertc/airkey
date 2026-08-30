import Foundation

/// Centrale toestand van de filmbibliotheek. Wijzigingen worden gemeld via
/// NotificationCenter (.libraryDidChange); alle mutaties gebeuren op de main queue.
final class LibraryStore {
    static let shared = LibraryStore()

    enum State {
        case idle
        case connecting
        case scanning(String)
        case ready
        case failed(String)
    }

    private(set) var movies: [Movie] = []
    private(set) var state: State = .idle
    private(set) var lastScan: Date?

    private let cacheURL: URL

    private init() {
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
    func refresh() {
        guard !isBusy else { return }
        let settings = SettingsStore.shared.settings
        setState(.connecting)

        SMBService.shared.ensureConnected(settings) { [weak self] error in
            guard let self else { return }
            if let error {
                self.setState(.failed(Self.friendlyMessage(for: error)))
                return
            }
            self.setState(.scanning(""))
            LibraryScanner().scan(rootPath: settings.normalizedRootPath, progress: { path in
                self.setState(.scanning(path), onlyIfScanning: true)
            }, completion: { result in
                DispatchQueue.main.async {
                    switch result {
                    case .success(let movies):
                        self.movies = movies
                        self.lastScan = Date()
                        self.state = .ready
                        self.saveCache()
                    case .failure(let error):
                        self.state = .failed(Self.friendlyMessage(for: error))
                    }
                    NotificationCenter.default.post(name: .libraryDidChange, object: nil)
                }
            })
        }
    }

    /// Zorgt dat er een SMB-verbinding is (voor artwork en afspelen) zonder te
    /// scannen — bijv. na een app-herstart met een gevulde cache.
    func ensureConnection() {
        SMBService.shared.ensureConnected(SettingsStore.shared.settings) { [weak self] error in
            guard let self else { return }
            DispatchQueue.main.async {
                if error == nil, !self.movies.isEmpty {
                    if case .ready = self.state {} else {
                        self.state = .ready
                        NotificationCenter.default.post(name: .libraryDidChange, object: nil)
                    }
                } else if let error, self.movies.isEmpty {
                    self.state = .failed(Self.friendlyMessage(for: error))
                    NotificationCenter.default.post(name: .libraryDidChange, object: nil)
                }
            }
        }
    }

    private func setState(_ newState: State, onlyIfScanning: Bool = false) {
        DispatchQueue.main.async {
            if onlyIfScanning {
                guard case .scanning = self.state else { return }
            }
            self.state = newState
            NotificationCenter.default.post(name: .libraryDidChange, object: nil)
        }
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

    static func friendlyMessage(for error: Error) -> String {
        let ns = error as NSError
        if ns.domain == NSPOSIXErrorDomain {
            switch Int32(ns.code) {
            case ECONNREFUSED, EHOSTUNREACH, ETIMEDOUT, ENETUNREACH:
                return "De My Passport Wireless Pro is niet bereikbaar. Controleer of de iPad met het wifi-netwerk van de WD is verbonden."
            case EACCES, EPERM:
                return "Toegang geweigerd. Controleer gebruikersnaam/wachtwoord in de instellingen."
            default:
                break
            }
        }
        return error.localizedDescription
    }
}
