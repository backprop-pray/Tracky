import SwiftUI

struct RobotLoadingView: View {
    var body: some View {
        TimelineView(.animation) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate

            // Track oscillation: sine wave, 0.4s period
            let trackOff = CGFloat(sin(time * .pi / 0.4)) * 3.0

            // Eye pulse: sine wave, 0.8s period → maps to opacity
            let eyeOpa = 0.4 + 0.6 * (sin(time * .pi / 0.8) + 1) / 2

            // Dot rotation: full circle every 2.5s
            let dotAngle = (time.truncatingRemainder(dividingBy: 2.5))
                           / 2.5 * 360.0

            ZStack {
                // Robot Canvas
                Canvas { context, size in
                    let cx = size.width / 2
                    let cy = size.height / 2 + 10  // shift down slightly

                    // ── TRACKS ──────────────────────────────────
                    // Left track (moves up when right moves down)
                    let leftTrack = CGRect(
                        x: cx - 50, y: cy + 18 + trackOff,
                        width: 44, height: 13)
                    context.fill(
                        Path(roundedRect: leftTrack, cornerRadius: 6),
                        with: .color(Color(white: 0.15))
                    )

                    // Right track (opposite phase)
                    let rightTrack = CGRect(
                        x: cx + 6, y: cy + 18 - trackOff,
                        width: 44, height: 13)
                    context.fill(
                        Path(roundedRect: rightTrack, cornerRadius: 6),
                        with: .color(Color(white: 0.15))
                    )

                    // Track wheel circles (left side)
                    let leftWheelL = CGRect(x: cx - 52, y: cy + 14 + trackOff,
                                            width: 14, height: 14)
                    let leftWheelR = CGRect(x: cx - 18, y: cy + 14 + trackOff,
                                            width: 14, height: 14)
                    context.fill(Path(ellipseIn: leftWheelL),
                                 with: .color(Color(white: 0.25)))
                    context.fill(Path(ellipseIn: leftWheelR),
                                 with: .color(Color(white: 0.25)))

                    // Track wheel circles (right side)
                    let rightWheelL = CGRect(x: cx + 4, y: cy + 14 - trackOff,
                                             width: 14, height: 14)
                    let rightWheelR = CGRect(x: cx + 38, y: cy + 14 - trackOff,
                                             width: 14, height: 14)
                    context.fill(Path(ellipseIn: rightWheelL),
                                 with: .color(Color(white: 0.25)))
                    context.fill(Path(ellipseIn: rightWheelR),
                                 with: .color(Color(white: 0.25)))

                    // ── CHASSIS ──────────────────────────────────
                    let chassis = CGRect(x: cx - 36, y: cy - 2,
                                         width: 72, height: 20)
                    context.fill(
                        Path(roundedRect: chassis, cornerRadius: 5),
                        with: .color(Color(red: 0.75, green: 0.75, blue: 0.77))
                    )

                    // ── RASPBERRY PI MODULE ───────────────────────
                    let rpi = CGRect(x: cx - 14, y: cy - 10,
                                     width: 28, height: 8)
                    context.fill(
                        Path(roundedRect: rpi, cornerRadius: 3),
                        with: .color(Color(red: 0.06, green: 0.28, blue: 0.10))
                    )

                    // Small gold GPIO pins on RPi
                    for i in 0..<4 {
                        let pin = CGRect(x: cx - 12 + CGFloat(i) * 7,
                                         y: cy - 13, width: 2, height: 4)
                        context.fill(Path(roundedRect: pin, cornerRadius: 1),
                                     with: .color(Color(red: 0.83,
                                                        green: 0.68,
                                                        blue: 0.21)))
                    }

                    // ── WEBCAM POLE ───────────────────────────────
                    var pole = Path()
                    pole.move(to: CGPoint(x: cx + 16, y: cy - 2))
                    pole.addLine(to: CGPoint(x: cx + 16, y: cy - 46))
                    context.stroke(pole,
                        with: .color(Color(white: 0.5)),
                        lineWidth: 3)

                    // ── WEBCAM HEAD ───────────────────────────────
                    let head = CGRect(x: cx + 4, y: cy - 60,
                                      width: 24, height: 24)
                    context.fill(
                        Path(ellipseIn: head),
                        with: .color(Color(white: 0.55))
                    )
                    // Lens
                    let lens = CGRect(x: cx + 10, y: cy - 54,
                                      width: 12, height: 12)
                    context.fill(
                        Path(ellipseIn: lens),
                        with: .color(.black)
                    )
                    // Lens shine
                    let shine = CGRect(x: cx + 12, y: cy - 52,
                                       width: 4, height: 4)
                    context.fill(
                        Path(ellipseIn: shine),
                        with: .color(Color.white.opacity(0.6))
                    )

                    // ── SENSOR EYES ───────────────────────────────
                    // Glow ring behind eyes
                    let leftGlow = CGRect(x: cx - 37, y: cy + 3,
                                          width: 13, height: 13)
                    context.fill(
                        Path(ellipseIn: leftGlow),
                        with: .color(Color(red: 1.0, green: 0.58, blue: 0.0)
                            .opacity(eyeOpa * 0.3))
                    )
                    let rightGlow = CGRect(x: cx - 23, y: cy + 3,
                                           width: 13, height: 13)
                    context.fill(
                        Path(ellipseIn: rightGlow),
                        with: .color(Color(red: 1.0, green: 0.58, blue: 0.0)
                            .opacity(eyeOpa * 0.3))
                    )

                    // Eye cores
                    let leftEye = CGRect(x: cx - 34, y: cy + 6,
                                         width: 7, height: 7)
                    context.fill(
                        Path(ellipseIn: leftEye),
                        with: .color(Color(red: 1.0, green: 0.58, blue: 0.0)
                            .opacity(eyeOpa))
                    )
                    let rightEye = CGRect(x: cx - 20, y: cy + 6,
                                          width: 7, height: 7)
                    context.fill(
                        Path(ellipseIn: rightEye),
                        with: .color(Color(red: 1.0, green: 0.58, blue: 0.0)
                            .opacity(eyeOpa))
                    )

                    // ── ULTRASONIC SENSOR FRONT ───────────────────
                    let sensorL = CGRect(x: cx - 38, y: cy + 8,
                                         width: 5, height: 5)
                    let sensorR = CGRect(x: cx + 33, y: cy + 8,
                                         width: 5, height: 5)
                    context.fill(Path(ellipseIn: sensorL),
                                 with: .color(Color(white: 0.3)))
                    context.fill(Path(ellipseIn: sensorR),
                                 with: .color(Color(white: 0.3)))
                }
                .frame(width: 140, height: 160)

                // ── ORBIT DOTS ────────────────────────────────────
                ForEach(0..<3, id: \.self) { i in
                    let angle = (dotAngle + Double(i) * 120)
                                * .pi / 180
                    Circle()
                        .fill(Color(red: 1.0, green: 0.58, blue: 0.0)
                            .opacity(0.4))
                        .frame(width: 6, height: 6)
                        .offset(
                            x: CGFloat(cos(angle)) * 58,
                            y: CGFloat(sin(angle)) * 58
                        )
                }
            }
        }
        .frame(width: 140, height: 160)
    }
}

#Preview {
    RobotLoadingView()
        .frame(width: 140, height: 160)
        .background(Color.white)
}
