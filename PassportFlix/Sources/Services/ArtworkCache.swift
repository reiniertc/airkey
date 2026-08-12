import UIKit

/// Laadt posters/fanart via SMB en cachet ze op schijf en in het geheugen,
/// zodat de interface na de eerste keer direct vlot laadt.
actor ArtworkCache {
    static let shared = ArtworkCache()

    private let memoryCache = NSCache<NSString, UIImage>()
    private let directory: URL
    private var inFlight: [String: Task<UIImage?, Never>] = [:]

    private init() {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        directory = caches.appendingPathComponent("artwork", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        memoryCache.countLimit = 300
    }

    func image(forSMBPath path: String, maxPixelSize: CGFloat = 800) async -> UIImage? {
        let key = cacheKey(for: path)

        if let cached = memoryCache.object(forKey: key as NSString) {
            return cached
        }
        let fileURL = directory.appendingPathComponent(key)
        if let data = try? Data(contentsOf: fileURL), let image = UIImage(data: data) {
            memoryCache.setObject(image, forKey: key as NSString)
            return image
        }

        if let existing = inFlight[path] {
            return await existing.value
        }

        let task = Task<UIImage?, Never> {
            guard let data = try? await SMBService.shared.readFile(atPath: path),
                  let original = UIImage(data: data) else { return nil }
            let image = Self.downscale(original, maxPixelSize: maxPixelSize)
            if let jpeg = image.jpegData(compressionQuality: 0.85) {
                try? jpeg.write(to: fileURL)
            }
            return image
        }
        inFlight[path] = task
        let image = await task.value
        inFlight[path] = nil
        if let image {
            memoryCache.setObject(image, forKey: key as NSString)
        }
        return image
    }

    func clear() {
        memoryCache.removeAllObjects()
        try? FileManager.default.removeItem(at: directory)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    private func cacheKey(for path: String) -> String {
        var hash: UInt64 = 5381
        for byte in path.utf8 {
            hash = (hash &* 33) &+ UInt64(byte)
        }
        return String(hash, radix: 16) + ".jpg"
    }

    private static func downscale(_ image: UIImage, maxPixelSize: CGFloat) -> UIImage {
        let largest = max(image.size.width, image.size.height) * image.scale
        guard largest > maxPixelSize else { return image }
        let ratio = maxPixelSize / largest
        let newSize = CGSize(width: image.size.width * image.scale * ratio,
                             height: image.size.height * image.scale * ratio)
        let renderer = UIGraphicsImageRenderer(size: newSize, format: .init())
        return renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: newSize))
        }
    }
}
