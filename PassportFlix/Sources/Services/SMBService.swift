import Foundation
import AMSMB2

/// Dunne async-wrapper rond AMSMB2 voor het browsen en lezen van bestanden
/// op de SMB-share van de WD My Passport Wireless Pro.
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

    private var client: SMB2Manager?
    private var connectedSignature: String?

    private init() {}

    /// Verbindt (of herverbindt) met de share uit de instellingen.
    func ensureConnected(_ settings: ConnectionSettings) async throws {
        let signature = "\(settings.host)|\(settings.share)|\(settings.username)"
        if client != nil, connectedSignature == signature { return }

        disconnect()

        guard let url = URL(string: "smb://\(settings.host)") else {
            throw SMBError.invalidHost(settings.host)
        }
        // De WD staat standaard gastoegang toe; AMSMB2 verwacht dan "guest".
        let user = settings.username.isEmpty ? "guest" : settings.username
        let credential = URLCredential(user: user, password: settings.password, persistence: .forSession)
        guard let manager = SMB2Manager(url: url, credential: credential) else {
            throw SMBError.invalidHost(settings.host)
        }

        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            manager.connectShare(name: settings.share) { error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume()
                }
            }
        }
        client = manager
        connectedSignature = signature
    }

    func disconnect() {
        client?.disconnectShare()
        client = nil
        connectedSignature = nil
    }

    func listDirectory(atPath path: String) async throws -> [Entry] {
        guard let client else { throw SMBError.notConnected }
        let items: [[URLResourceKey: Any]] = try await withCheckedThrowingContinuation { continuation in
            client.contentsOfDirectory(atPath: path) { result in
                continuation.resume(with: result)
            }
        }
        return items.compactMap { item in
            guard let name = item[.nameKey] as? String else { return nil }
            let fullPath = (item[.pathKey] as? String) ?? (path.isEmpty ? name : "\(path)/\(name)")
            let isDirectory = (item[.fileResourceTypeKey] as? URLFileResourceType) == .directory
            let size = (item[.fileSizeKey] as? NSNumber)?.int64Value ?? 0
            let modified = item[.contentModificationDateKey] as? Date
            return Entry(name: name, path: fullPath, isDirectory: isDirectory, size: size, modified: modified)
        }
    }

    /// Leest een volledig bestand (voor .nfo, .srt en artwork; niet voor video).
    func readFile(atPath path: String) async throws -> Data {
        guard let client else { throw SMBError.notConnected }
        return try await withCheckedThrowingContinuation { continuation in
            client.contents(atPath: path, progress: nil) { result in
                continuation.resume(with: result)
            }
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
