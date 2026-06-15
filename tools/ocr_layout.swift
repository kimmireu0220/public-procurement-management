import Foundation
import Vision
import ImageIO

if CommandLine.arguments.count < 3 {
    fputs("usage: ocr_layout.swift INPUT_ROOT OUTPUT_ROOT\n", stderr)
    exit(2)
}

struct Line {
    let text: String
    let minX: Double
    let midX: Double
    let maxX: Double
    let minY: Double
    let midY: Double
    let maxY: Double
}

let inputRoot = URL(fileURLWithPath: CommandLine.arguments[1])
let outputRoot = URL(fileURLWithPath: CommandLine.arguments[2])
let fm = FileManager.default

func isImage(_ url: URL) -> Bool {
    let ext = url.pathExtension.lowercased()
    return ext == "jpg" || ext == "jpeg" || ext == "png"
}

func chapterName(for url: URL) -> String? {
    url.pathComponents.first { $0.hasPrefix("Chapter ") }
}

func sortTopToBottom(_ lines: [Line]) -> [Line] {
    lines.sorted { a, b in
        if abs(a.midY - b.midY) > 0.015 {
            return a.midY > b.midY
        }
        return a.minX < b.minX
    }
}

let imageURLs = fm.enumerator(at: inputRoot, includingPropertiesForKeys: nil)!
    .compactMap { $0 as? URL }
    .filter(isImage)
    .sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }

try fm.createDirectory(at: outputRoot, withIntermediateDirectories: true)

let request = VNRecognizeTextRequest()
request.revision = VNRecognizeTextRequestRevision3
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = true

for (i, imageURL) in imageURLs.enumerated() {
    guard let chapter = chapterName(for: imageURL) else { continue }
    let chapterOutput = outputRoot.appendingPathComponent(chapter, isDirectory: true)
    try fm.createDirectory(at: chapterOutput, withIntermediateDirectories: true)
    let baseName = imageURL.deletingPathExtension().lastPathComponent
    let pageOutput = chapterOutput.appendingPathComponent(baseName).appendingPathExtension("layout.txt")
    let tsvOutput = chapterOutput.appendingPathComponent(baseName).appendingPathExtension("tsv")

    guard let imageSource = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
          let cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, nil) else {
        fputs("WARN could not read image: \(imageURL.path)\n", stderr)
        continue
    }

    do {
        try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
    } catch {
        fputs("WARN OCR failed: \(imageURL.path): \(error)\n", stderr)
        continue
    }

    let lines = (request.results ?? []).compactMap { observation -> Line? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let text = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.isEmpty { return nil }
        let box = observation.boundingBox
        return Line(
            text: text,
            minX: Double(box.minX),
            midX: Double(box.midX),
            maxX: Double(box.maxX),
            minY: Double(box.minY),
            midY: Double(box.midY),
            maxY: Double(box.maxY)
        )
    }

    let left = sortTopToBottom(lines.filter { $0.midX < 0.50 })
    let right = sortTopToBottom(lines.filter { $0.midX >= 0.50 })
    let farRight = sortTopToBottom(lines.filter { $0.minX >= 0.74 })
    let full = sortTopToBottom(lines)

    var layout = """
    # \(chapter) / \(imageURL.lastPathComponent)
    source: \(imageURL.path)

    ## Left column (midX < 0.50)
    \(left.map(\.text).joined(separator: "\n"))

    ## Right column (midX >= 0.50)
    \(right.map(\.text).joined(separator: "\n"))

    ## Far-right strip (minX >= 0.74; often answers/explanations)
    \(farRight.map(\.text).joined(separator: "\n"))

    ## Full top-to-bottom order
    \(full.map(\.text).joined(separator: "\n"))
    """
    layout.append("\n")
    try layout.write(to: pageOutput, atomically: true, encoding: .utf8)

    var tsv = "minX\tmidX\tmaxX\tminY\tmidY\tmaxY\ttext\n"
    for line in full {
        let safe = line.text.replacingOccurrences(of: "\t", with: " ")
        tsv += String(format: "%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%@\n",
                      line.minX, line.midX, line.maxX, line.minY, line.midY, line.maxY, safe)
    }
    try tsv.write(to: tsvOutput, atomically: true, encoding: .utf8)

    if i % 10 == 0 || i + 1 == imageURLs.count {
        print("LAYOUT OCR \(i + 1)/\(imageURLs.count): \(chapter) \(imageURL.lastPathComponent)")
        fflush(stdout)
    }
}
