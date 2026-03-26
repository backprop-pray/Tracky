import Foundation

nonisolated enum StompFrame {

    static func connect(host: String, token: String) -> String {
        var frame = "CONNECT\n"
        frame += "accept-version:1.2\n"
        frame += "host:\(host)\n"
        frame += "heart-beat:10000,10000\n"
        frame += "Authorization:Bearer \(token)\n"
        frame += "\n\0"
        return frame
    }

    static func subscribe(destination: String, id: String) -> String {
        var frame = "SUBSCRIBE\n"
        frame += "destination:\(destination)\n"
        frame += "id:\(id)\n"
        frame += "ack:auto\n"
        frame += "\n\0"
        return frame
    }

    static func disconnect() -> String {
        "DISCONNECT\nreceipt:disconnect-receipt\n\n\0"
    }

    static func command(from raw: String) -> String? {
        let trimmed = raw.drop(while: { $0 == "\n" || $0 == "\r" })
        return String(trimmed).components(separatedBy: "\n").first
    }

    static func body(from raw: String) -> String? {
        guard let range = raw.range(of: "\n\n") else { return nil }
        var body = String(raw[range.upperBound...])
        while body.hasSuffix("\0") { body = String(body.dropLast()) }
        body = body.trimmingCharacters(in: .whitespacesAndNewlines)
        return body.isEmpty ? nil : body
    }

    static func header(_ key: String, from raw: String) -> String? {
        let lines = raw.components(separatedBy: "\n")
        for i in 1..<lines.count {
            let line = lines[i]
            if line.isEmpty { break }
            if let colonIndex = line.firstIndex(of: ":") {
                let headerKey = String(line[line.startIndex..<colonIndex])
                if headerKey == key {
                    let valueStart = line.index(after: colonIndex)
                    return String(line[valueStart...])
                }
            }
        }
        return nil
    }

    static func isHeartbeat(_ raw: String) -> Bool {
        raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
