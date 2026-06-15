import Foundation
import Vision
import ImageIO

if CommandLine.arguments.count < 3 {
    fputs("usage: ocr_pages.swift INPUT_ROOT OUTPUT_ROOT\n", stderr)
    exit(2)
}

let inputRoot = URL(fileURLWithPath: CommandLine.arguments[1])
let outputRoot = URL(fileURLWithPath: CommandLine.arguments[2])
let fm = FileManager.default

func isImage(_ url: URL) -> Bool {
    let ext = url.pathExtension.lowercased()
    return ext == "jpg" || ext == "jpeg" || ext == "png"
}

func chapterName(for url: URL) -> String? {
    let comps = url.pathComponents
    return comps.first { $0.hasPrefix("Chapter ") }
}

let enumerator = fm.enumerator(at: inputRoot, includingPropertiesForKeys: nil)!
let imageURLs = enumerator
    .compactMap { $0 as? URL }
    .filter(isImage)
    .sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }

try fm.createDirectory(at: outputRoot, withIntermediateDirectories: true)

let request = VNRecognizeTextRequest()
request.revision = VNRecognizeTextRequestRevision3
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = true

var indexLines: [String] = []

for (i, imageURL) in imageURLs.enumerated() {
    guard let chapter = chapterName(for: imageURL) else {
        continue
    }
    let chapterOutput = outputRoot.appendingPathComponent(chapter, isDirectory: true)
    try fm.createDirectory(at: chapterOutput, withIntermediateDirectories: true)
    let pageOutput = chapterOutput
        .appendingPathComponent(imageURL.deletingPathExtension().lastPathComponent)
        .appendingPathExtension("txt")

    guard let imageSource = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
          let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
        fputs("WARN could not read image: \(imageURL.path)\n", stderr)
        continue
    }

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        fputs("WARN OCR failed: \(imageURL.path): \(error)\n", stderr)
        continue
    }

    let lines = (request.results ?? [])
        .sorted { a, b in
            let ay = a.boundingBox.midY
            let by = b.boundingBox.midY
            if abs(ay - by) > 0.015 {
                return ay > by
            }
            return a.boundingBox.minX < b.boundingBox.minX
        }
        .compactMap { $0.topCandidates(1).first?.string.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }

    let body = """
    # \(chapter) / \(imageURL.lastPathComponent)
    source: \(imageURL.path)

    \(lines.joined(separator: "\n"))
    """
    try body.write(to: pageOutput, atomically: true, encoding: .utf8)
    indexLines.append("\(chapter)/\(pageOutput.lastPathComponent)\t\(imageURL.path)")

    if i % 10 == 0 || i + 1 == imageURLs.count {
        print("OCR \(i + 1)/\(imageURLs.count): \(chapter) \(imageURL.lastPathComponent)")
        fflush(stdout)
    }
}

try indexLines.joined(separator: "\n")
    .write(to: outputRoot.appendingPathComponent("index.tsv"), atomically: true, encoding: .utf8)
