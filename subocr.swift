// Reads the subtitle band of one window and prints it as a JSON line whenever it changes.
// usage: subocr <window match> <x0> <y0> <x1> <y1> [interval]
//   window match: substring of the owning app name or window title (e.g. "PS Remote Play")
//   x0..y1: subtitle band as fractions of the window (0,0 = top-left)
import AppKit
import CoreGraphics
import Vision

let a = CommandLine.arguments
guard a.count >= 6 else { FileHandle.standardError.write("usage: subocr MATCH x0 y0 x1 y1 [interval]\n".data(using: .utf8)!); exit(2) }
let match = a[1].lowercased()
let band = (Double(a[2])!, Double(a[3])!, Double(a[4])!, Double(a[5])!)
let interval = a.count > 6 ? Double(a[6])! : 0.4

func findWindow() -> CGWindowID? {
    let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    var best: (CGWindowID, Double)? = nil
    for w in info {
        let owner = (w[kCGWindowOwnerName as String] as? String ?? "").lowercased()
        let title = (w[kCGWindowName as String] as? String ?? "").lowercased()
        guard owner.contains(match) || title.contains(match), (w[kCGWindowLayer as String] as? Int ?? 1) == 0 else { continue }
        let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
        let area = (b["Width"] ?? 0) * (b["Height"] ?? 0)
        if area > (best?.1 ?? 40000) { best = (w[kCGWindowNumber as String] as! CGWindowID, area) }
    }
    return best?.0
}

func read(_ id: CGWindowID) -> String? {
    guard let img = CGWindowListCreateImage(.null, .optionIncludingWindow, id, [.boundsIgnoreFraming, .bestResolution]) else { return nil }
    let W = Double(img.width), H = Double(img.height)
    let r = CGRect(x: band.0 * W, y: band.1 * H, width: (band.2 - band.0) * W, height: (band.3 - band.1) * H).integral
    guard let crop = img.cropping(to: r) else { return nil }
    return ocr(crop)
}

func ocr(_ crop: CGImage) -> String {
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["en-US"]
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: crop).perform([req])
    let obs = (req.results ?? []).filter { ($0.topCandidates(1).first?.confidence ?? 0) > 0.4 }
    // top-to-bottom reading order (Vision's y grows upward)
    return obs.sorted { $0.boundingBox.midY > $1.boundingBox.midY }
              .compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
              .trimmingCharacters(in: .whitespaces)
}

// test mode: subocr file:<image> x0 y0 x1 y1 → reads the band of one image and exits
if match.hasPrefix("file:"), let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: String(a[1].dropFirst(5))) as CFURL, nil),
   let img = CGImageSourceCreateImageAtIndex(src, 0, nil) {
    let W = Double(img.width), H = Double(img.height)
    let r = CGRect(x: band.0 * W, y: band.1 * H, width: (band.2 - band.0) * W, height: (band.3 - band.1) * H).integral
    print(ocr(img.cropping(to: r)!)); exit(0)
}

var shown = "", candidate = "", seen = 0, missing = 0
setvbuf(stdout, nil, _IOLBF, 0)
while true {
    if let id = findWindow(), let text = read(id) {
        missing = 0
        // a line must read the same twice in a row before it is shown (skips half-faded frames)
        if text == candidate { seen += 1 } else { candidate = text; seen = 1 }
        if seen == 2 && text != shown {
            shown = text
            let d = try! JSONSerialization.data(withJSONObject: ["text": text])
            print(String(data: d, encoding: .utf8)!)
        }
    } else {
        missing += 1
        if missing == 10 { print("{\"error\": \"window not found: \(match)\"}") }
    }
    Thread.sleep(forTimeInterval: interval)
}
