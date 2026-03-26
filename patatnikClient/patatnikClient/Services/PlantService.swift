import Foundation

nonisolated enum PlantError: Error, Sendable {
    case notAuthenticated
    case invalidURL
    case networkError
    case serverError(Int, String)
    case noData
    case decodingError(String)

    var errorDescription: String {
        switch self {
        case .notAuthenticated:
            return "You must be logged in."
        case .invalidURL:
            return "Configuration error."
        case .networkError:
            return "Network error. Check your connection."
        case .serverError(let code, let message):
            return message.isEmpty ? "Server error (\(code))" : message
        case .noData:
            return "No data returned from server."
        case .decodingError(let details):
            return "Decoding error: \(details)"
        }
    }
}

struct PlantService {

    // MARK: - GET /plants

    func getPlants(token: String) async throws -> [Plant] {
        let url = URL(string: "\(AppConfig.baseURL)/plants")!

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw PlantError.networkError
        }

        guard let http = response as? HTTPURLResponse else {
            throw PlantError.networkError
        }

        guard (200...299).contains(http.statusCode) else {
            if let body = try? JSONDecoder().decode(ErrorBody.self, from: data) {
                throw PlantError.serverError(http.statusCode, body.message)
            }
            throw PlantError.serverError(http.statusCode, "")
        }

        do {
            let envelope = try JSONDecoder().decode(APIEnvelope<[Plant]>.self, from: data)
            guard let plants = envelope.data else { throw PlantError.noData }
            return plants
        } catch let error as PlantError {
            throw error
        } catch {
            throw PlantError.decodingError(error.localizedDescription)
        }
    }

    // MARK: - POST /plants (multipart)

    func createPlant(token: String, latitude: Double, longitude: Double, image: Data?) async throws -> Plant {
        let url = URL(string: "\(AppConfig.baseURL)/plants")!

        let boundary = "Boundary-\(UUID().uuidString)"

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        var body = Data()

        body.appendMultipart(name: "latitude", value: "\(latitude)", boundary: boundary)
        body.appendMultipart(name: "longitude", value: "\(longitude)", boundary: boundary)

        if let image {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"image\"; filename=\"plant.jpg\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
            body.append(image)
            body.append("\r\n".data(using: .utf8)!)
        }

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw PlantError.networkError
        }

        guard let http = response as? HTTPURLResponse else {
            throw PlantError.networkError
        }

        guard (200...299).contains(http.statusCode) else {
            if let errorBody = try? JSONDecoder().decode(ErrorBody.self, from: data) {
                throw PlantError.serverError(http.statusCode, errorBody.message)
            }
            throw PlantError.serverError(http.statusCode, "")
        }

        do {
            let envelope = try JSONDecoder().decode(APIEnvelope<Plant>.self, from: data)
            guard let plant = envelope.data else { throw PlantError.noData }
            return plant
        } catch let error as PlantError {
            throw error
        } catch {
            throw PlantError.decodingError(error.localizedDescription)
        }
    }
}

private struct ErrorBody: Decodable {
    let message: String
}

private extension Data {
    mutating func appendMultipart(name: String, value: String, boundary: String) {
        append("--\(boundary)\r\n".data(using: .utf8)!)
        append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
        append("\(value)\r\n".data(using: .utf8)!)
    }
}
