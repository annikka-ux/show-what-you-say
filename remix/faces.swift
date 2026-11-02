// Finds faces in photos with the Mac's built-in Vision framework (free, on-device, nothing downloaded).
// usage: swift faces.swift photo1.jpg photo2.png ...
// Prints one JSON line per photo: {"file": ..., "w": px, "h": px, "faces": [[x, y, w, h], ...]}
// with each box as fractions of the picture, measured from the top-left corner. remix.py uses it to keep
// faces in frame when a photo is cropped to 9:16, to zoom toward the face, and to keep words off it.
import Foundation
import Vision
import ImageIO

for path in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: path)
    var w = 0, h = 0
    var boxes: [[Double]] = []
    if let src = CGImageSourceCreateWithURL(url as CFURL, nil),
       let img = CGImageSourceCreateImageAtIndex(src, 0, nil) {
        w = img.width; h = img.height
        let req = VNDetectFaceRectanglesRequest()
        try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
        for f in req.results ?? [] {
            let b = f.boundingBox          // Vision measures from the bottom-left corner
            boxes.append([Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height)].map { ($0 * 1000).rounded() / 1000 })
        }
    }
    let line: [String: Any] = ["file": path, "w": w, "h": h, "faces": boxes]
    if let data = try? JSONSerialization.data(withJSONObject: line), let s = String(data: data, encoding: .utf8) { print(s) }
}
