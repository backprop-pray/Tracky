import SwiftUI
import Combine

private nonisolated struct RespondBody: Encodable, Sendable {
    let accepted: Bool
}

private nonisolated struct UpdateRecommendationBody: Encodable, Sendable {
    let processedPlantId: Int
    let text: String
    
    enum CodingKeys: String, CodingKey {
        case processedPlantId = "processed_plant_id"
        case text
    }
}

private nonisolated struct UpdateRecommendationResponse: Decodable, Sendable {
    let processedPlantId: Int
    let plantId: Int
    let disease: String
    let text: String
    
    enum CodingKeys: String, CodingKey {
        case processedPlantId = "processed_plant_id"
        case plantId = "plant_id"
        case disease
        case text
    }
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
    @Published var responseAccepted: Bool = false

    // Opinion
    @Published var userOpinion: String = ""
    @Published var isSubmittingOpinion: Bool = false
    @Published var opinionSubmitted: Bool = false
    
    // Processed plant ID for PATCH endpoint
    private var processedPlantId: Int?

    private var loadingTask: Task<Void, Never>?
    private var currentPlantId: Int?

    func loadRecommendation(for plant: Plant) {
        currentPlantId = plant.id
        
        // Load persisted user response state
        let responseKey = "plant_\(plant.id)_responded"
        let acceptedKey = "plant_\(plant.id)_accepted"
        let opinionKey = "plant_\(plant.id)_opinion_submitted"
        
        hasResponded = UserDefaults.standard.bool(forKey: responseKey)
        responseAccepted = UserDefaults.standard.bool(forKey: acceptedKey)
        opinionSubmitted = UserDefaults.standard.bool(forKey: opinionKey)
        
        // Try to load cached recommendation data
        let diseaseKey = "plant_\(plant.id)_disease"
        let recommendationKey = "plant_\(plant.id)_recommendation"
        let processedPlantIdKey = "plant_\(plant.id)_processed_plant_id"
        
        // Load processed plant ID if available
        let cachedProcessedPlantId = UserDefaults.standard.integer(forKey: processedPlantIdKey)
        if cachedProcessedPlantId != 0 {
            processedPlantId = cachedProcessedPlantId
        }
        
        if let cachedDisease = UserDefaults.standard.string(forKey: diseaseKey),
           let cachedRecommendation = UserDefaults.standard.string(forKey: recommendationKey),
           !cachedDisease.isEmpty,
           !cachedRecommendation.isEmpty {
            // We have cached data - use it immediately
            estimatedDisease = cachedDisease
            recommendation = cachedRecommendation
            recommendationLoaded = true
            isLoadingRecommendation = false
            recommendationError = false
            userOpinion = ""
            print("[ViewModel] Loaded cached recommendation for plant \(plant.id)")
            return
        }
        
        // No cached data - start loading from WebSocket
        isLoadingRecommendation = true
        recommendationLoaded = false
        recommendationError = false
        estimatedDisease = ""
        recommendation = ""
        userOpinion = ""

        // Wire callback — must happen BEFORE any message could arrive
        // The callback now filters by plantId to avoid cross-plant contamination
        PlantWebSocketService.shared.onRecommendationReceived = {
            [weak self] plantId, processedPlantIdParam, disease, text in
            guard let self else { return }
            
            // Only process if this recommendation is for the current plant
            guard plantId == self.currentPlantId else {
                print("[ViewModel] Ignoring recommendation for plant \(plantId), waiting for \(self.currentPlantId ?? -1)")
                return
            }
            
            self.recommendationReceived(disease: disease, text: text, processedPlantId: processedPlantIdParam)
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

    func recommendationReceived(disease: String, text: String, processedPlantId: Int?) {
        guard let plantId = currentPlantId else { return }
        
        loadingTask?.cancel()
        estimatedDisease = disease
        recommendation = text
        self.processedPlantId = processedPlantId
        
        // Persist recommendation data
        UserDefaults.standard.set(disease, forKey: "plant_\(plantId)_disease")
        UserDefaults.standard.set(text, forKey: "plant_\(plantId)_recommendation")
        if let processedPlantId = processedPlantId {
            UserDefaults.standard.set(processedPlantId, forKey: "plant_\(plantId)_processed_plant_id")
        }
        
        withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
            recommendationLoaded = true
            isLoadingRecommendation = false
        }
        
        print("[ViewModel] Recommendation received and cached for plant \(plantId)")
    }

    func respond(accepted: Bool) {
        guard let plantId = currentPlantId else { return }
        hasResponded = true
        responseAccepted = accepted
        
        // Persist response state
        UserDefaults.standard.set(true, forKey: "plant_\(plantId)_responded")
        UserDefaults.standard.set(accepted, forKey: "plant_\(plantId)_accepted")
        
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
        
        guard let processedPlantId = self.processedPlantId else {
            print("Failed to submit opinion: processed_plant_id is missing")
            return
        }
        
        isSubmittingOpinion = true
        defer { isSubmittingOpinion = false }
        
        do {
            let response: UpdateRecommendationResponse = try await APIClient.shared.patch(
                endpoint: "/processed-plants/recommendation",
                body: UpdateRecommendationBody(processedPlantId: processedPlantId, text: trimmed),
                requiresAuth: true,
                baseURL: AppConfig.microserviceURL
            )
            
            // Update the recommendation with the new text and disease
            estimatedDisease = response.disease
            recommendation = response.text
            
            // Update cached values
            UserDefaults.standard.set(response.disease, forKey: "plant_\(plantId)_disease")
            UserDefaults.standard.set(response.text, forKey: "plant_\(plantId)_recommendation")
            
            withAnimation { 
                opinionSubmitted = true 
                // Persist opinion submission state
                UserDefaults.standard.set(true, forKey: "plant_\(plantId)_opinion_submitted")
            }
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
