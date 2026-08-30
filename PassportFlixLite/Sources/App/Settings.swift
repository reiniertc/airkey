import Foundation

/// Verbindingsinstellingen voor de WD My Passport Wireless Pro.
/// Standaardwaarden komen overeen met de fabrieksinstellingen:
/// hotspot-IP 192.168.60.1 en een gastvrije SMB-share "Storage".
struct ConnectionSettings: Equatable {
    var host: String = "192.168.60.1"
    var share: String = "Storage"
    var username: String = ""
    var password: String = ""
    /// Optionele submap binnen de share waar de films staan, bijv. "Films".
    var rootPath: String = ""

    var normalizedRootPath: String {
        rootPath.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
    }
}

final class SettingsStore {
    static let shared = SettingsStore()

    var settings: ConnectionSettings {
        didSet { persist() }
    }

    private let defaults = UserDefaults.standard

    private init() {
        var s = ConnectionSettings()
        if let host = defaults.string(forKey: "smb.host"), !host.isEmpty { s.host = host }
        if let share = defaults.string(forKey: "smb.share"), !share.isEmpty { s.share = share }
        s.username = defaults.string(forKey: "smb.username") ?? ""
        s.password = defaults.string(forKey: "smb.password") ?? ""
        s.rootPath = defaults.string(forKey: "smb.rootPath") ?? ""
        settings = s
    }

    private func persist() {
        defaults.set(settings.host, forKey: "smb.host")
        defaults.set(settings.share, forKey: "smb.share")
        defaults.set(settings.username, forKey: "smb.username")
        defaults.set(settings.password, forKey: "smb.password")
        defaults.set(settings.rootPath, forKey: "smb.rootPath")
    }
}

/// Houdt per film bij hoe ver de gebruiker gekeken heeft ("Verder kijken").
final class ProgressStore {
    static let shared = ProgressStore()

    private let key = "playback.progress"
    private(set) var fractions: [String: Double]

    private init() {
        fractions = UserDefaults.standard.dictionary(forKey: key) as? [String: Double] ?? [:]
    }

    func fraction(for movie: Movie) -> Double? {
        fractions[movie.videoPath]
    }

    func setFraction(_ fraction: Double, for movie: Movie) {
        if fraction >= 0.95 {
            fractions.removeValue(forKey: movie.videoPath)
        } else if fraction > 0.01 {
            fractions[movie.videoPath] = fraction
        } else {
            return
        }
        UserDefaults.standard.set(fractions, forKey: key)
        NotificationCenter.default.post(name: .progressDidChange, object: nil)
    }

    func clear(for movie: Movie) {
        fractions.removeValue(forKey: movie.videoPath)
        UserDefaults.standard.set(fractions, forKey: key)
        NotificationCenter.default.post(name: .progressDidChange, object: nil)
    }
}

extension Notification.Name {
    static let progressDidChange = Notification.Name("progressDidChange")
    static let libraryDidChange = Notification.Name("libraryDidChange")
}
