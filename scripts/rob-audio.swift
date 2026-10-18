// rob-audio: ROB's voice out and the Mac's microphone in, through one AVAudioEngine with
// Apple's voice processing on (echo cancellation, noise suppression, gain control), so
// ROB's own lines are taken out of what the microphone hears (docs/LISTEN-PLAN.md).
//
//   rob-audio DIR      serves DIR/mic.sock and DIR/play.sock until killed
//
// mic.sock: every client gets the cleaned microphone from the moment it connects, 16 kHz
// 16-bit mono little-endian, as it comes.
// play.sock: a client sends a 4-byte little-endian length and that many bytes of 16 kHz
// 16-bit mono PCM; the line plays, and one byte "d" comes back once it has played. A
// length of 0 cuts the line that is playing (its "d" then comes at once).
// Built by scripts/rob.sh: swiftc -O scripts/rob-audio.swift -o .cache/bin/rob-audio

import AVFoundation
import Foundation

setvbuf(stdout, nil, _IOLBF, 0)
func say(_ s: String) { FileHandle.standardError.write(("rob-audio: " + s + "\n").data(using: .utf8)!) }

guard CommandLine.arguments.count == 2 else { say("usage: rob-audio DIR"); exit(2) }
let dir = CommandLine.arguments[1]
try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)

let engine = AVAudioEngine()
let input = engine.inputNode
_ = engine.outputNode  // the output must exist before voice processing goes on, or it fails to start (-10875)
_ = engine.mainMixerNode
do { try input.setVoiceProcessingEnabled(true) } catch { say("no voice processing: \(error)"); exit(1) }
if #available(macOS 14.0, *) {
    input.voiceProcessingOtherAudioDuckingConfiguration =
        AVAudioVoiceProcessingOtherAudioDuckingConfiguration(enableAdvancedDucking: false, duckingLevel: .min)
}
let player = AVAudioPlayerNode()
let lineFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false)!
engine.attach(player)
engine.connect(player, to: engine.mainMixerNode, format: lineFormat)

// The microphone: channel 0 of the processed input, resampled to 16 kHz Int16.
let inFormat = input.outputFormat(forBus: 0)
let monoIn = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: inFormat.sampleRate, channels: 1, interleaved: false)!
let micFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true)!
let converter = AVAudioConverter(from: monoIn, to: micFormat)!
let lock = NSLock()
var micClients: [Int32] = []

func send(_ fd: Int32, _ data: UnsafeRawPointer, _ count: Int) -> Bool {
    var off = 0
    while off < count {
        let n = write(fd, data + off, count - off)
        if n <= 0 { return false }
        off += n
    }
    return true
}

input.installTap(onBus: 0, bufferSize: 1024, format: inFormat) { buffer, _ in
    guard let src = buffer.floatChannelData, buffer.frameLength > 0 else { return }
    let mono = AVAudioPCMBuffer(pcmFormat: monoIn, frameCapacity: buffer.frameLength)!
    mono.frameLength = buffer.frameLength
    mono.floatChannelData![0].update(from: src[0], count: Int(buffer.frameLength))
    let cap = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / inFormat.sampleRate) + 32
    let out = AVAudioPCMBuffer(pcmFormat: micFormat, frameCapacity: cap)!
    var fed = false
    var err: NSError?
    converter.convert(to: out, error: &err) { _, status in
        if fed { status.pointee = .noDataNow; return nil }
        fed = true
        status.pointee = .haveData
        return mono
    }
    let bytes = Int(out.frameLength) * 2
    guard bytes > 0, let p = out.int16ChannelData?[0] else { return }
    lock.lock()
    micClients = micClients.filter { fd in
        if send(fd, p, bytes) { return true }
        close(fd)
        return false
    }
    lock.unlock()
}

// The voice: one line at a time.
let playLock = NSLock()
var playing: (fd: Int32, id: Int)? = nil
var nextId = 0

func readAll(_ fd: Int32, _ count: Int) -> Data? {
    var data = Data(count: count)
    var off = 0
    while off < count {
        let n = data.withUnsafeMutableBytes { read(fd, $0.baseAddress! + off, count - off) }
        if n <= 0 { return nil }
        off += n
    }
    return data
}

func serveLine(_ fd: Int32) {
    while true {
        guard let head = readAll(fd, 4) else { break }
        let n = Int(head.withUnsafeBytes { $0.loadUnaligned(as: UInt32.self).littleEndian })
        if n == 0 {
            playLock.lock()
            let cut = playing != nil
            playLock.unlock()
            if cut { player.stop() }
            continue
        }
        guard let pcm = readAll(fd, n) else { break }
        let frames = AVAudioFrameCount(n / 2)
        let buf = AVAudioPCMBuffer(pcmFormat: lineFormat, frameCapacity: frames)!
        buf.frameLength = frames
        pcm.withUnsafeBytes { raw in
            let s = raw.bindMemory(to: Int16.self)
            let d = buf.floatChannelData![0]
            for i in 0..<Int(frames) { d[i] = Float(Int16(littleEndian: s[i])) / 32768.0 }
        }
        playLock.lock()
        nextId += 1
        let id = nextId
        playing = (fd, id)
        playLock.unlock()
        player.scheduleBuffer(buf, completionCallbackType: .dataPlayedBack) { _ in
            playLock.lock()
            let mine = playing?.id == id
            if mine { playing = nil }
            playLock.unlock()
            if mine { var d: UInt8 = 100; _ = send(fd, &d, 1) }
        }
        if !engine.isRunning { try? engine.start() }
        player.play()
    }
    close(fd)
}

func serve(_ name: String, _ onClient: @escaping (Int32) -> Void) {
    let path = dir + "/" + name
    unlink(path)
    let s = socket(AF_UNIX, SOCK_STREAM, 0)
    var addr = sockaddr_un()
    addr.sun_family = sa_family_t(AF_UNIX)
    withUnsafeMutableBytes(of: &addr.sun_path) { raw in
        let b = Array(path.utf8.prefix(raw.count - 1))
        raw.copyBytes(from: b + [0])
    }
    let ok = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(s, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
    }
    guard ok == 0, Darwin.listen(s, 8) == 0 else { say("cannot listen on \(path)"); exit(1) }
    Thread.detachNewThread {
        while true {
            let c = accept(s, nil, nil)
            if c >= 0 { onClient(c) }
        }
    }
}

signal(SIGPIPE, SIG_IGN)
engine.prepare()
do { try engine.start() } catch { say("the audio engine did not start: \(error)"); exit(1) }
serve("mic.sock") { fd in lock.lock(); micClients.append(fd); lock.unlock() }
serve("play.sock") { fd in Thread.detachNewThread { serveLine(fd) } }
say("ready: \(Int(inFormat.sampleRate)) Hz, \(inFormat.channelCount) channel(s) in, voice processing on, sockets in \(dir)")
signal(SIGTERM) { _ in exit(0) }
dispatchMain()
