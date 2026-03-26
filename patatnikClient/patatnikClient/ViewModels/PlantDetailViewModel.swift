import SwiftUI
import Combine

private nonisolated struct RespondBody: Encodable, Sendable {
    let accepted: Bool
}

private nonisolated struct OpinionBody: Encodable, Sendable {
    let text: String
}

@MainActor
class PlantDetailViewModel: ObservableObject {

    // Recommendation
    @Published var estimatedDisease: String = ""
    @Published var recommendation: String = ""
    @Published var recommendationLoaded: Bool = false
    @Published var isLoadingRecommendation: Bool = true
    @Published var recommendationError: Bool = false

    // Response
    @Published var hasResponded: Bool = false

    // Opinion
    @Published var userOpinion: String = ""
    @Published var isSubmittingOpinion: Bool = false
    @Published var opinionSubmitted: Bool = false

    private var loadingTask: Task<Void, Never>?
    private var currentPlantId: Int?

    func loadRecommendation(for plant: Plant) {
        currentPlantId = plant.id
        isLoadingRecommendation = true
        recommendationLoaded = false
        recommendationError = false
        estimatedDisease = ""
        recommendation = ""
        hasResponded = false
        opinionSubmitted = false
        userOpinion = ""

        // Wire callback — must happen BEFORE any message could arrive
        // Runs on MainActor since PlantWebSocketService is @MainActor
        PlantWebSocketService.shared.onRecommendationReceived = {
            [weak self] disease, text in
            // Already on MainActor because PlantWebSocketService is @MainActor
            guard let self else { return }
            self.recommendationReceived(disease: disease, text: text)
        }

        // 30 second timeout
        loadingTask?.cancel()
        loadingTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 30_000_000_000)
            guard !Task.isCancelled else { return }
            guard let self else { return }
            if !self.recommendationLoaded {
                self.isLoadingRecommendation = false
                self.recommendationError = true
                print("[ViewModel] Recommendation timed out")
            }
        }

        print("[ViewModel] Waiting for recommendation for plant \(plant.id)")
    }

    func recommendationReceived(disease: String, text: String) {
        loadingTask?.cancel()
        estimatedDisease = disease
        recommendation = String(text.prefix(50))
        withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
            recommendationLoaded = true
            isLoadingRecommendation = false
        }
    }

    func respond(accepted: Bool) {
        guard let plantId = currentPlantId else { return }
        hasResponded = true
        Task {
            do {
                try await APIClient.shared.post(
                    endpoint: "/plants/\(plantId)/recommendation/respond",
                    body: RespondBody(accepted: accepted),
                    requiresAuth: true
                )
            } catch {
                print("Failed to save response:", error)
            }
        }
    }

    func submitOpinion(plantId: Int) async {
        let trimmed = userOpinion.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        isSubmittingOpinion = true
        defer { isSubmittingOpinion = false }
        do {
            try await APIClient.shared.post(
                endpoint: "/plants/\(plantId)/opinion",
                body: OpinionBody(text: trimmed),
                requiresAuth: true
            )
            withAnimation { opinionSubmitted = true }
            userOpinion = ""
        } catch {
            print("Failed to submit opinion:", error)
        }
    }

    func cancel() {
        loadingTask?.cancel()
        PlantWebSocketService.shared.onRecommendationReceived = nil
    }
}
