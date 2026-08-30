import Foundation
import AMSMB2

/// Wrapper rond AMSMB2 2.x (de laatste reeks met iOS 12-ondersteuning; de
/// hoofdklasse heet daar `AMSMB2`, in 3.x werd dat `SMB2Manager`).
/// Alles werkt met completion handlers — Swift concurrency bestaat pas op iOS 13+.
final class SMBService {
    static let shared = SMBService()

    struct Entry {
        let name: String
        let path: String
        let isDirectory: Bool
        let size: Int64
        let modified: Date?
    }

    enum SMBError: LocalizedError {
        case invalidHost(String)
        case notConnected

        var errorDescription: String? {
            switch self {
            case .invalidHost(let host):
                return "Ongeldig adres: \(host)"
            case .notConnected:
                return "Geen verbinding met de My Passport Wireless Pro."
            }
        }
    }

    private var client: AMSMB2?
    private var connectedSignature: String?

    private init() {}

    /// Verbindt (of herverbindt) met de share uit de instellingen.
    func ensureConnected(_ settings: ConnectionSettings, completion: @escaping (Error?) -> Void) {
        let signature = "\(settings.host)|\(settings.share)|\(settings.username)"
        if client != nil, connectedSignature == signature {
            completion(nil)
            return
        }

        client?.disconnectShare()
        client = nil
        connectedSignature = nil

        guard let url = URL(string: "smb://\(settings.host)") else {
            completion(SMBError.invalidHost(settings.host))
            return
        }
        let user = settings.username.isEmpty ? "guest" : settings.username
        let credential = URLCredential(user: user, password: settings.password, persistence: .forSession)
        guard let manager = AMSMB2(url: url, credential: credential) else {
            completion(SMBError.invalidHost(settings.host))
            return
        }

        manager.connectShare(name: settings.share) { [weak self] error in
            if error == nil {
                self?.client = manager
                self?.connectedSignature = signature
            }
            completion(error)
        }
    }

    func listDirectory(atPath path: String,
                       completion: @escaping (Result<[Entry], Error>) -> Void) {
        guard let client else {
            completion(.failure(SMBError.notConnected))
            return
        }
        client.contentsOfDirectory(atPath: path) { result in
            switch result {
            case .failure(let error):
                completion(.failure(error))
            case .success(let items):
                let entries: [Entry] = items.compactMap { item in
                    guard let name = item[.nameKey] as? String else { return nil }
                    let fullPath = (item[.pathKey] as? String) ?? (path.isEmpty ? name : "\(path)/\(name)")
                    let isDirectory = (item[.fileResourceTypeKey] as? URLFileResourceType) == .directory
                    let size = (item[.fileSizeKey] as? NSNumber)?.int64Value ?? 0
                    let modified = item[.contentModificationDateKey] as? Date
                    return Entry(name: name, path: fullPath, isDirectory: isDirectory,
                                 size: size, modified: modified)
                }
                completion(.success(entries))
            }
        }
    }

    /// Leest een volledig bestand (voor .nfo, .srt en artwork; niet voor video).
    func readFile(atPath path: String,
                  completion: @escaping (Result<Data, Error>) -> Void) {
        guard let client else {
            completion(.failure(SMBError.notConnected))
            return
        }
        client.contents(atPath: path, progress: nil) { result in
            completion(result)
        }
    }

    /// Bouwt een smb://-URL die VLC rechtstreeks kan streamen.
    static func streamURL(for path: String, settings: ConnectionSettings) -> URL? {
        var components = URLComponents()
        components.scheme = "smb"
        components.host = settings.host
        if settings.username.isEmpty {
            components.user = "guest"
        } else {
            components.user = settings.username
            components.password = settings.password.isEmpty ? nil : settings.password
        }
        let cleanPath = path.hasPrefix("/") ? String(path.dropFirst()) : path
        components.path = "/\(settings.share)/\(cleanPath)"
        return components.url
    }
}
