import UIKit

/// Laadt posters/fanart via SMB en cachet ze in het geheugen en op schijf.
/// Completion wordt altijd op de main queue aangeroepen.
final class ArtworkCache {
    static let shared = ArtworkCache()

    private let memoryCache = NSCache<NSString, UIImage>()
    private let directory: URL
    private let workQueue = DispatchQueue(label: "artwork.queue")
    private var waiters: [String: [(UIImage?) -> Void]] = [:]

    private init() {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        directory = caches.appendingPathComponent("artwork", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        // De oude iPads hebben maar 1 GB werkgeheugen; houd de cache bescheiden.
        memoryCache.countLimit = 120
    }

    func image(forSMBPath path: String, maxPixelSize: CGFloat = 600,
               completion: @escaping (UIImage?) -> Void) {
        let key = cacheKey(for: path)

        if let cached = memoryCache.object(forKey: key as NSString) {
            completion(cached)
            return
        }

        workQueue.async {
            // Al een download onderweg voor dit pad? Sluit dan aan in de rij.
            if self.waiters[path] != nil {
                self.waiters[path]?.append(completion)
                return
            }

            let fileURL = self.directory.appendingPathComponent(key)
            if let data = try? Data(contentsOf: fileURL), let image = UIImage(data: data) {
                self.memoryCache.setObject(image, forKey: key as NSString)
                DispatchQueue.main.async { completion(image) }
                return
            }

            self.waiters[path] = [completion]
            SMBService.shared.readFile(atPath: path) { result in
                self.workQueue.async {
                    var image: UIImage?
                    if case .success(let data) = result, let original = UIImage(data: data) {
                        image = Self.downscale(original, maxPixelSize: maxPixelSize)
                        if let image, let jpeg = image.jpegData(compressionQuality: 0.85) {
                            try? jpeg.write(to: fileURL)
                        }
                    }
                    if let image {
                        self.memoryCache.setObject(image, forKey: key as NSString)
                    }
                    let callbacks = self.waiters.removeValue(forKey: path) ?? []
                    DispatchQueue.main.async {
                        callbacks.forEach { $0(image) }
                    }
                }
            }
        }
    }

    func clear() {
        memoryCache.removeAllObjects()
        workQueue.async {
            try? FileManager.default.removeItem(at: self.directory)
            try? FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
        }
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
        let renderer = UIGraphicsImageRenderer(size: newSize)
        return renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: newSize))
        }
    }
}
