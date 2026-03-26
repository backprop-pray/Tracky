import Foundation
import CoreLocation
import Combine

@MainActor
final class LocationManager: NSObject, ObservableObject {
    static let shared = LocationManager()

    @Published var location: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined

    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = 10
        authorizationStatus = manager.authorizationStatus
        print("[Location] Init, status: \(authorizationStatus.rawValue)")
    }

    func requestPermission() {
        print("[Location] Requesting when-in-use authorization")
        manager.requestWhenInUseAuthorization()
    }

    func startUpdating() {
        guard authorizationStatus == .authorizedWhenInUse
           || authorizationStatus == .authorizedAlways else {
            print("[Location] Not authorized (status: \(authorizationStatus.rawValue)), requesting permission")
            requestPermission()
            return
        }
        print("[Location] Starting location updates")
        manager.startUpdatingLocation()
    }

    func stopUpdating() {
        manager.stopUpdatingLocation()
    }
}

extension LocationManager: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        print("[Location] Authorization changed: \(status.rawValue)")
        Task { @MainActor in
            self.authorizationStatus = status
            if status == .authorizedWhenInUse || status == .authorizedAlways {
                self.startUpdating()
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        print("[Location] Updated: \(location.coordinate.latitude), \(location.coordinate.longitude)")
        Task { @MainActor in
            self.location = location
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let clError = error as? CLError
        print("[Location] Failed: \(error.localizedDescription) (code: \(clError?.code.rawValue ?? -1))")
        // Don't crash — location is optional, map still works without it
    }
}
