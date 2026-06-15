import Foundation
import Vision
import ImageIO

if CommandLine.arguments.count < 2 {
    fputs("usage: vision_ocr.swift IMAGE_PATH\n", stderr)
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard let imageSource = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
      let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
    fputs("error: could not read image at \(imageURL.path)\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.revision = VNRecognizeTextRequestRevision3
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("error: OCR failed for \(imageURL.path): \(error)\n", stderr)
    exit(1)
}

let observations = (request.results ?? [])
    .sorted { a, b in
        let ay = a.boundingBox.midY
        let by = b.boundingBox.midY
        if abs(ay - by) > 0.015 {
            return ay > by
        }
        return a.boundingBox.minX < b.boundingBox.minX
    }

for observation in observations {
    if let candidate = observation.topCandidates(1).first {
        print(candidate.string)
    }
}
