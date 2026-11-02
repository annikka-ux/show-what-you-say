// Where the face is and where the eyes point, frame by frame, with the Mac's built-in Vision framework
// (free, on-device). usage: swift eyes.swift DIR_OF_JPGS   (lookaway.py runs it for you)
// Prints one line per frame: name, face box (x y w h, fractions from top-left) and the pupil offset inside
// each eye (-1..1, x then y). Pupils far off-center = looking away from the camera; low y = a blink.
import Foundation
import Vision
import AppKit

func offset(_ eye: VNFaceLandmarkRegion2D?, _ pupil: VNFaceLandmarkRegion2D?) -> (Double, Double) {
    guard let e = eye?.normalizedPoints, let p = pupil?.normalizedPoints.first, !e.isEmpty else { return (.nan, .nan) }
    let xs = e.map { Double($0.x) }, ys = e.map { Double($0.y) }
    let cx = (xs.min()! + xs.max()!) / 2, cy = (ys.min()! + ys.max()!) / 2
    let hw = (xs.max()! - xs.min()!) / 2, hh = max((ys.max()! - ys.min()!) / 2, 1e-6)
    return ((Double(p.x) - cx) / hw, (Double(p.y) - cy) / hh)
}

let dir = CommandLine.arguments[1]
for f in (try FileManager.default.contentsOfDirectory(atPath: dir)).filter({ $0.hasSuffix(".jpg") }).sorted() {
    guard let img = NSImage(contentsOfFile: "\(dir)/\(f)"),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNDetectFaceLandmarksRequest()
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    guard let face = req.results?.first, let lm = face.landmarks else { print("\(f) noface"); continue }
    let b = face.boundingBox
    let l = offset(lm.leftEye, lm.leftPupil), r = offset(lm.rightEye, lm.rightPupil)
    print(String(format: "%@ face %.3f %.3f %.3f %.3f eyes %.2f %.2f %.2f %.2f", f,
                 b.minX, 1 - b.maxY, b.width, b.height, l.0, r.0, l.1, r.1))
}
