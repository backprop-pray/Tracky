import SwiftUI

struct PlantRecommendationView: View {
    @ObservedObject var viewModel: PlantDetailViewModel
    @State private var pulseOpacity: Double = 1.0

    var body: some View {
        Group {
            if viewModel.isLoadingRecommendation && !viewModel.recommendationError {
                loadingState
            } else if viewModel.recommendationLoaded {
                loadedState
            } else if viewModel.recommendationError {
                errorState
            }
        }
    }

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: 24) {
            RobotLoadingView()
                .frame(width: 120, height: 100)

            VStack(spacing: 6) {
                Text("Analyzing plant health...")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.appDark)
                Text("AI recommendation incoming...")
                    .font(.caption)
                    .foregroundStyle(Color.appSecondary)
                    .opacity(pulseOpacity)
                    .onAppear {
                        withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                            pulseOpacity = 0.4
                        }
                    }
            }
        }
        .padding(.vertical, 28)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Loaded State

    private var loadedState: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Section header
            HStack(spacing: 6) {
                Image(systemName: "sparkles")
                    .foregroundStyle(Color.appOrange)
                Text("AI Analysis")
                    .font(.headline)
                    .foregroundStyle(Color.appDark)
            }

            // Disease badge
            HStack(spacing: 6) {
                Image(systemName: "staroflife.fill")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                Text(viewModel.estimatedDisease)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(
                Capsule()
                    .fill(
                        LinearGradient(
                            colors: [Color.red, Color.red.opacity(0.75)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .shadow(color: Color.red.opacity(0.35), radius: 8, y: 4)
            )
            .transition(.scale(scale: 0.8).combined(with: .opacity))

            // Recommendation card
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 4) {
                    Image(systemName: "cross.circle.fill")
                        .font(.caption)
                        .foregroundStyle(Color.appOrange)
                    Text("Recommended Care")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.appOrange)
                }
                Text(viewModel.recommendation)
                    .font(.body)
                    .foregroundStyle(Color.appDark)
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.appOrange.opacity(0.07))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(Color.appOrange.opacity(0.22), lineWidth: 1)
                    )
            )
            .transition(.move(edge: .bottom).combined(with: .opacity))

            // Action buttons
            HStack(spacing: 12) {
                // REJECT
                Button { viewModel.respond(accepted: false) } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "xmark")
                        Text("Reject")
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(
                        RoundedRectangle(cornerRadius: 13)
                            .fill(Color.red.opacity(0.07))
                            .overlay(
                                RoundedRectangle(cornerRadius: 13)
                                    .stroke(Color.red.opacity(0.25), lineWidth: 1)
                            )
                    )
                }

                // ACCEPT
                Button { viewModel.respond(accepted: true) } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark")
                        Text("Accept")
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(
                        RoundedRectangle(cornerRadius: 13)
                            .fill(Color.appOrange)
                            .shadow(color: Color.appOrange.opacity(0.4),
                                    radius: 10, y: 4)
                    )
                }
            }
            .disabled(viewModel.hasResponded)
            .opacity(viewModel.hasResponded ? 0.5 : 1.0)
            .animation(.easeInOut(duration: 0.2), value: viewModel.hasResponded)

            // Response confirmation
            if viewModel.hasResponded {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(Color.appOrange)
                    Text("Response recorded")
                        .font(.caption)
                        .foregroundStyle(Color.appSecondary)
                }
                .transition(.opacity.animation(.easeIn))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }

    // MARK: - Error State

    private var errorState: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 2) {
                Text("Analysis unavailable")
                    .font(.subheadline.weight(.medium))
                Text("Could not load recommendation")
                    .font(.caption)
                    .foregroundStyle(Color.appSecondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.orange.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.orange.opacity(0.2), lineWidth: 1)
                )
        )
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }
}

// MARK: - Opinion Input View

struct OpinionInputView: View {
    @ObservedObject var viewModel: PlantDetailViewModel
    let plantId: Int
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Your Opinion")
                .font(.headline)
                .foregroundStyle(Color.appDark)
            Text("How would you treat this plant?")
                .font(.caption)
                .foregroundStyle(Color.appSecondary)

            // Text input
            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.appSurface.opacity(0.06))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(
                                isFocused
                                    ? Color.appOrange.opacity(0.6)
                                    : Color.appSecondary.opacity(0.2),
                                lineWidth: 1
                            )
                            .animation(.easeInOut(duration: 0.2), value: isFocused)
                    )
                    .frame(height: 90)

                TextEditor(text: $viewModel.userOpinion)
                    .font(.body)
                    .foregroundStyle(Color.appDark)
                    .padding(10)
                    .frame(height: 90)
                    .background(.clear)
                    .scrollContentBackground(.hidden)
                    .focused($isFocused)

                if viewModel.userOpinion.isEmpty {
                    Text("e.g. Apply fungicide spray weekly...")
                        .font(.body)
                        .foregroundStyle(Color.appSecondary.opacity(0.55))
                        .padding(14)
                        .allowsHitTesting(false)
                }
            }

            // Submit button
            Button {
                isFocused = false
                Task { await viewModel.submitOpinion(plantId: plantId) }
            } label: {
                Group {
                    if viewModel.isSubmittingOpinion {
                        ProgressView().tint(.white)
                    } else {
                        HStack(spacing: 8) {
                            Image(systemName: "paperplane.fill")
                            Text("Submit Opinion")
                        }
                    }
                }
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(
                    RoundedRectangle(cornerRadius: 13)
                        .fill(
                            viewModel.userOpinion.trimmingCharacters(
                                in: .whitespaces).isEmpty
                                ? Color.appSecondary
                                : Color.appDark
                        )
                )
            }
            .disabled(
                viewModel.userOpinion.trimmingCharacters(in: .whitespaces).isEmpty
                || viewModel.isSubmittingOpinion
                || viewModel.opinionSubmitted
            )
            .animation(.easeInOut(duration: 0.2), value: viewModel.userOpinion)

            if viewModel.opinionSubmitted {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text("Opinion saved successfully")
                        .font(.caption)
                        .foregroundStyle(Color.appSecondary)
                }
                .transition(.opacity.animation(.easeIn(duration: 0.3)))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }
}
