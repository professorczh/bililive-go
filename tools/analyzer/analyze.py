#!/usr/bin/env python3
"""
Master Livestream Analysis Pipeline.
Automates:
1. Danmaku parsing & engagement spike detection.
2. FFmpeg high-speed 16kHz audio extraction.
3. Native Whisper speech-to-text transcription.
4. Local LLM (Qwen2.5) topical chaptering & summarization.
5. Interactive HTML dashboard generation.
"""

import os
import sys
import argparse
import json
import time
import subprocess

from danmaku import DanmakuAnalyzer, format_time
from audio import extract_audio_for_whisper
from transcriber import WhisperTranscriber
from summarizer import StreamSummarizer, sec_to_str
from reporter import generate_report
from clipper import auto_clip_from_analysis

def main():
    parser = argparse.ArgumentParser(description="Bililive-go Livestream Offline AI Analyzer")
    parser.add_argument("--video", "-v", required=True, help="Path to recorded video file (.flv, .mp4, etc.)")
    parser.add_argument("--danmaku", "-d", help="Path to .ass danmaku file (auto-detected if omitted)")
    parser.add_argument("--model", "-m", default="tools/analyzer/models/ggml-small.bin", help="Path to whisper ggml model")
    parser.add_argument("--ollama-model", default="qwen2.5:3b", help="Ollama model name (default: qwen2.5:3b)")
    parser.add_argument("--threads", "-t", type=int, default=8, help="Number of CPU threads for Whisper (default: 8)")
    parser.add_argument("--output-dir", "-o", help="Output directory for reports (default: next to video)")
    parser.add_argument("--clip", action="store_true", help="Automatically cut and export highlight clips as MP4 with subtitles")
    args = parser.parse_args()

    video_path = os.path.abspath(args.video)
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        sys.exit(1)

    base_dir = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]

    out_dir = os.path.abspath(args.output_dir) if args.output_dir else base_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n==========================================")
    print(f"🎬 Starting Livestream Analysis")
    print(f"📹 Target: {video_path}")
    print(f"==========================================")
    t_start = time.time()

    # 0. Check or Fast-Remux to Faststart MP4 for browser native zero-latency seeking
    play_video_name = os.path.basename(video_path)
    if video_path.lower().endswith(".flv"):
        mp4_cand = os.path.join(base_dir, f"{base_name}.mp4")
        if not os.path.exists(mp4_cand):
            print(f"\n⚡ Fast-remuxing FLV to Faststart MP4 for zero-latency seeking in browser ...")
            cmd = ["ffmpeg", "-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", mp4_cand]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(mp4_cand):
            play_video_name = os.path.basename(mp4_cand)
            print(f"   ✓ Faststart MP4 ready: {play_video_name}")

    # 1. Danmaku Analysis
    ass_path = args.danmaku
    if not ass_path:
        cand = os.path.join(base_dir, f"{base_name}.ass")
        if os.path.exists(cand):
            ass_path = cand

    danmaku_data = {"count": 0, "peaks": [], "curve": [], "events": []}
    if ass_path and os.path.exists(ass_path):
        print(f"\n[Step 1/4] 💬 Analyzing Danmaku: {ass_path} ...")
        dan_analyzer = DanmakuAnalyzer(ass_path)
        danmaku_data["count"] = dan_analyzer.total_count()
        danmaku_data["peaks"] = dan_analyzer.find_peaks(window_sec=30, top_n=6)
        danmaku_data["curve"] = dan_analyzer.compute_density_curve(window_sec=30)
        danmaku_data["events"] = dan_analyzer.get_events_list()
        print(f"   ✓ Total Danmaku: {danmaku_data['count']}")
        print(f"   ✓ Identified {len(danmaku_data['peaks'])} major engagement peaks")
    else:
        print(f"\n[Step 1/4] 💬 No .ass danmaku file found, proceeding without danmaku metrics.")

    # 2. Audio Extraction
    print(f"\n[Step 2/4] 🎵 Extracting 16kHz Audio ...")
    wav_path = os.path.join(out_dir, f"{base_name}_audio16k.wav")
    extract_audio_for_whisper(video_path, wav_path)

    # 3. Whisper Speech Transcription
    print(f"\n[Step 3/4] 🗣️ Transcribing Audio with Whisper ({args.model}) ...")
    whisper_prefix = os.path.join(out_dir, f"{base_name}_whisper")
    transcriber = WhisperTranscriber(model_path=args.model)
    transcript_res = transcriber.transcribe(wav_path, output_prefix=whisper_prefix, threads=args.threads)
    segments = transcript_res.get("segments", [])
    duration_sec = transcript_res.get("duration", 0.0)
    print(f"   ✓ Transcribed {len(segments)} segments ({duration_sec:.1f}s audio)")

    # 4. LLM Chaptering & Summarization
    print(f"\n[Step 4/4] 🧠 AI Chaptering & Summarization with {args.ollama_model} ...")
    summarizer = StreamSummarizer(model=args.ollama_model)
    chapters = summarizer.generate_chapters(segments, danmaku_data["peaks"])
    print(f"   ✓ Generated {len(chapters)} structured chapters")

    # 5. Output Artifacts
    print(f"\n📊 Exporting Results ...")
    result_json_path = os.path.join(out_dir, f"{base_name}_analysis.json")
    report_html_path = os.path.join(out_dir, f"{base_name}_report.html")

    report_payload = {
        "title": base_name,
        "video_file": play_video_name,
        "subtitle_file": f"{base_name}_whisper.srt",
        "duration_sec": duration_sec,
        "duration_str": sec_to_str(duration_sec),
        "total_danmaku": danmaku_data["count"],
        "peaks": danmaku_data["peaks"],
        "chapters": chapters,
        "danmaku_curve": danmaku_data["curve"],
        "danmaku_events": danmaku_data.get("events", []),
        "segments": segments
    }

    with open(result_json_path, 'w', encoding='utf-8') as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)
    print(f"   ✓ JSON Analysis: {result_json_path}")

    if args.clip:
        print(f"\n[Step 5/5] ✂️ Auto-Clipping Highlight Chapters ...")
        auto_clip_from_analysis(result_json_path, only_highlights=True)

    generate_report(report_payload, report_html_path)

    elapsed = time.time() - t_start
    print(f"\n==========================================")
    print(f"✨ Completed in {elapsed:.2f}s ({elapsed/60:.2f} mins)!")
    print(f"🌐 Interactive Dashboard: {report_html_path}")
    print(f"==========================================\n")

if __name__ == '__main__':
    main()
