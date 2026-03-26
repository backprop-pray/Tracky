import Foundation

nonisolated struct Plant: Codable, Identifiable, Sendable {
    let id: Int
    let latitude: Double
    let longitude: Double
    let imageUrl: String?
    let userId: Int?
    let createdAt: String?

    /// Returns the image URL with HTTP upgraded to HTTPS to satisfy ATS policy.
    var safeImageUrl: URL? {
        guard let imageUrl, !imageUrl.isEmpty else { return nil }
        let secured = imageUrl.hasPrefix("http://")
            ? imageUrl.replacingOccurrences(of: "http://", with: "https://")
            : imageUrl
        return URL(string: secured)
    }
}
