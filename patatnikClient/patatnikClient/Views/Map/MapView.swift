import SwiftUI
import MapKit
import CoreLocation

struct MapView: UIViewRepresentable {
    let plants: [Plant]
    let mapType: MKMapType
    @Binding var selectedPlant: Plant?

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.mapType = .hybridFlyover
        mapView.showsCompass = true
        mapView.showsScale = true
        mapView.showsBuildings = true
        mapView.isPitchEnabled = true

        mapView.register(
            PlantAnnotationView.self,
            forAnnotationViewWithReuseIdentifier: MKMapViewDefaultAnnotationViewReuseIdentifier
        )

        // Request location permission and enable user location only if authorized
        let locationManager = LocationManager.shared
        locationManager.requestPermission()

        let status = locationManager.authorizationStatus
        if status == .authorizedWhenInUse || status == .authorizedAlways {
            mapView.showsUserLocation = true
        }

        // Store mapView reference so we can update showsUserLocation later
        context.coordinator.mapViewRef = mapView

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.mapType = mapType

        // Enable user location once authorized
        let status = LocationManager.shared.authorizationStatus
        if status == .authorizedWhenInUse || status == .authorizedAlways {
            mapView.showsUserLocation = true
        }

        // Sync annotations
        let existing = mapView.annotations.filter { !($0 is MKUserLocation) }
        mapView.removeAnnotations(existing)

        let newAnnotations = plants.map { PlantAnnotation(plant: $0) }
        mapView.addAnnotations(newAnnotations)

        // Auto-fit on first load (0 → N)
        let wasEmpty = context.coordinator.previousPlantCount == 0
        context.coordinator.previousPlantCount = plants.count

        if wasEmpty && !plants.isEmpty {
            var rect = MKMapRect.null
            for annotation in newAnnotations {
                let point = MKMapPoint(annotation.coordinate)
                let pointRect = MKMapRect(x: point.x, y: point.y, width: 0.1, height: 0.1)
                rect = rect.union(pointRect)
            }
            mapView.setVisibleMapRect(
                rect,
                edgePadding: UIEdgeInsets(top: 80, left: 40, bottom: 120, right: 40),
                animated: true
            )
        }
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, MKMapViewDelegate {
        let parent: MapView
        var previousPlantCount = 0
        weak var mapViewRef: MKMapView?

        init(parent: MapView) {
            self.parent = parent
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }

            let view = mapView.dequeueReusableAnnotationView(
                withIdentifier: MKMapViewDefaultAnnotationViewReuseIdentifier,
                for: annotation
            )
            return view
        }

        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            guard let plantAnnotation = view.annotation as? PlantAnnotation else { return }
            parent.selectedPlant = plantAnnotation.plant
            print("Selected plant id:", plantAnnotation.plant.id)
        }

        func mapView(_ mapView: MKMapView, didDeselect view: MKAnnotationView) {
            // Do not clear selectedPlant — popup close button handles dismissal
        }
    }
}
