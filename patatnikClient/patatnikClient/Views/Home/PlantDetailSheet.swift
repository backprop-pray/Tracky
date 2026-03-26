import SwiftUI

// MARK: - Color Extensions

extension Color {
    static let appOrange    = Color(red: 1.0,  green: 0.58, blue: 0.0)
    static let appDark      = Color(red: 0.04, green: 0.04, blue: 0.06)
    static let appSurface   = Color(red: 0.11, green: 0.11, blue: 0.12)
    static let appSecondary = Color(red: 0.56, green: 0.56, blue: 0.58)
}

// MARK: - RoundedCorner Shape

struct RoundedCorner: Shape {
    var radius: CGFloat
    var corners: UIRectCorner

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

// MARK: - Plant Detail Sheet

struct PlantDetailSheet: View {
    let plant: Plant
    let onClose: () -> Void

    @StateObject private var viewModel = PlantDetailViewModel()
    @State private var appeared = false
    @State private var shimmerOffset: CGFloat = -300
    @Environment(\.horizontalSizeClass) var sizeClass

    var body: some View {
        GeometryReader { geo in
            Group {
                if sizeClass == .regular {
                    // iPad: floating card
                    sheetContent
                        .frame(width: 380)
                        .frame(maxHeight: geo.size.height * 0.55)
                } else {
                    // iPhone: bottom sheet
                    sheetContent
                        .frame(maxHeight: geo.size.height * 0.55)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
        }
        .background(.regularMaterial)
        .clipShape(RoundedCorner(radius: 24, corners: [.topLeft, .topRight]))
        .shadow(color: .black.opacity(0.15), radius: 20, x: 0, y: -4)
        .offset(y: appeared ? 0 : 500)
        .animation(.spring(response: 0.4, dampingFraction: 0.82), value: appeared)
        .gesture(
            DragGesture()
                .onEnded { value in
                    if value.translation.height > 80 {
                        onClose()
                    }
                }
        )
        .onAppear {
            appeared = true
            viewModel.loadRecommendation(for: plant)
        }
        .onDisappear {
            viewModel.cancel()
        }
    }

    // MARK: - Sheet Content

    private var sheetContent: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 0) {

                // 1. Drag handle
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.gray.opacity(0.4))
                    .frame(width: 36, height: 4)
                    .padding(.top, 12)
                    .padding(.bottom, 8)

                // 2. Plant image
                plantImage

                // 3. Plant header
                plantHeader

                Divider()
                    .padding(.horizontal, 20)

                // 4. Recommendation section
                PlantRecommendationView(viewModel: viewModel)

                // 5. Opinion input
                if viewModel.recommendationLoaded {
                    Divider().padding(.horizontal, 20)
                    OpinionInputView(viewModel: viewModel, plantId: plant.id)
                }

                Spacer().frame(height: 40)
            }
        }
    }

    // MARK: - Plant Image

    private var plantImage: some View {
        AsyncImage(url: plant.safeImageUrl) { phase in
            switch phase {
            case .empty:
                Rectangle()
                    .fill(Color.appSurface)
                    .overlay(shimmerView())
                    .frame(height: 220)
            case .success(let image):
                image
                    .resizable()
                    .scaledToFill()
                    .frame(height: 220)
                    .clipped()
                    .transition(.opacity.animation(.easeIn(duration: 0.3)))
            case .failure:
                ZStack {
                    Rectangle().fill(Color.appSurface).frame(height: 220)
                    VStack(spacing: 8) {
                        Image(systemName: "leaf.fill")
                            .font(.system(size: 40))
                            .foregroundStyle(Color.appOrange)
                        Text("No image available")
                            .font(.caption)
                            .foregroundStyle(Color.appSecondary)
                    }
                }
            @unknown default:
                EmptyView()
            }
        }
        .frame(height: 220)
        .clipped()
    }

    // MARK: - Plant Header

    private var plantHeader: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Plant #\(plant.id)")
                    .font(.title2.bold())
                    .foregroundStyle(Color.appDark)

                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.caption)
                        .foregroundStyle(Color.appSecondary)
                    Text(formattedDate(plant.createdAt))
                        .font(.caption)
                        .foregroundStyle(Color.appSecondary)
                }
            }
            Spacer()
            Button(action: onClose) {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(Color.appSecondary)
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 12)
    }

    // MARK: - Shimmer

    private func shimmerView() -> some View {
        GeometryReader { geo in
            LinearGradient(
                colors: [.clear, Color.white.opacity(0.3), .clear],
                startPoint: .leading,
                endPoint: .trailing
            )
            .frame(width: geo.size.width * 0.6)
            .offset(x: shimmerOffset)
            .onAppear {
                withAnimation(.linear(duration: 1.2).repeatForever(autoreverses: false)) {
                    shimmerOffset = 300
                }
            }
        }
        .clipped()
    }

    // MARK: - Date Formatter

    private func formattedDate(_ isoString: String?) -> String {
        guard let isoString, !isoString.isEmpty else {
            return "Unknown date"
        }

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")

        // Try with fractional seconds first (e.g. "2026-03-26T18:07:19.136")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "'Discovered' MMM d, yyyy"
            return display.string(from: date)
        }

        // Try without fractional seconds (e.g. "2026-03-26T18:07:19")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "'Discovered' MMM d, yyyy"
            return display.string(from: date)
        }

        return "Unknown date"
    }
}

#Preview {
    ZStack {
        Color.gray.opacity(0.3).ignoresSafeArea()
        VStack {
            Spacer()
            PlantDetailSheet(
                plant: Plant(id: 1, latitude: 42.69, longitude: 23.32,
                             imageUrl: nil, userId: 1, createdAt: "2026-03-12T10:00:00Z"),
                onClose: {}
            )
        }
    }
}
