import AppKit
import Foundation
import Vision

let arguments = CommandLine.arguments
guard arguments.count > 1 else {
    fputs("Usage: macos_vision_ocr.swift <image-path>\n", stderr)
    exit(1)
}

let imagePath = arguments[1]
let imageUrl = URL(fileURLWithPath: imagePath)

guard let image = NSImage(contentsOf: imageUrl) else {
    fputs("Failed to load image at \(imagePath)\n", stderr)
    exit(2)
}

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let cgImage = bitmap.cgImage
else {
    fputs("Failed to create CGImage for \(imagePath)\n", stderr)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

do {
    try handler.perform([request])
} catch {
    fputs("Vision OCR failed: \(error.localizedDescription)\n", stderr)
    exit(4)
}

let observations = request.results ?? []
let lines = observations.compactMap { observation in
    observation.topCandidates(1).first?.string.trimmingCharacters(in: .whitespacesAndNewlines)
}.filter { !$0.isEmpty }

let payload: [String: Any] = [
    "path": imagePath,
    "lines": lines,
]

let data = try JSONSerialization.data(withJSONObject: payload, options: [])
FileHandle.standardOutput.write(data)
