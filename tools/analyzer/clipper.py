#!/usr/bin/env python3
"""
High-Speed Lossless Video Clipper & Subtitle Slicer.
Extracts highlight segments from recorded livestream videos using FFmpeg stream copy
(0 re-encoding, sub-second execution) and slices synchronized .srt subtitles.
"""

import os
import sys
import json
import argparse
import subprocess
from typing import List, Dict, Any, Optional

def sec_to_srt_time(seconds: float) -> str:
    """Converts seconds float to SRT timestamp 00:00:00,000."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

def sanitize_filename(name: str) -> str:
    """Removes or replaces invalid filesystem characters."""
    invalid = '<>:"/\\|?*[]() '
    res = name
    for c in invalid:
        res = res.replace(c, '_')
    return res.strip('_')

def slice_subtitles(segments: List[Dict[str, Any]], start_sec: float, end_sec: float, output_srt_path: str):
    """
    Filters transcript segments falling into [start_sec, end_sec], offsets their
    timestamps so the clip begins at 00:00:00, and writes an SRT file.
    """
    matched = []
    for seg in segments:
        s = seg.get("start", 0.0)
        e = seg.get("end", 0.0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        
        # Check overlap with [start_sec, end_sec]
        if e >= start_sec and s <= end_sec:
            new_s = max(0.0, s - start_sec)
            new_e = max(0.0, e - start_sec)
            matched.append((new_s, new_e, text))

    if not matched:
        return

    with open(output_srt_path, 'w', encoding='utf-8') as f:
        for idx, (s, e, text) in enumerate(matched, start=1):
            f.write(f"{idx}\n")
            f.write(f"{sec_to_srt_time(s)} --> {sec_to_srt_time(e)}\n")
            f.write(f"{text}\n\n")

def cut_clip(video_path: str, start_sec: float, end_sec: float, output_clip_path: str) -> bool:
    """
    Executes lossless FFmpeg stream copy for fast cutting without re-encoding.
    """
    # -ss before -i for fast seek
    duration = end_sec - start_sec
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(round(start_sec, 2)),
        "-i", video_path,
        "-t", str(round(duration, 2)),
        "-c", "copy",
        "-avoid_negative_ts", "1",
        output_clip_path
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"[Clipper] FFmpeg copy cut failed: {res.stderr.decode('utf-8', errors='ignore')}")
        return False
    return True

def auto_clip_from_analysis(analysis_json_path: str, output_dir: Optional[str] = None, only_highlights: bool = True) -> List[str]:
    """
    Reads an analysis JSON file and cuts out highlight chapters.
    """
    if not os.path.exists(analysis_json_path):
        raise FileNotFoundError(f"Analysis file not found: {analysis_json_path}")

    with open(analysis_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    base_dir = os.path.dirname(os.path.abspath(analysis_json_path))
    video_title = data.get("title", "clip")
    
    # Try finding the video file
    video_path = None
    for ext in [".flv", ".mp4", ".ts", ".mkv"]:
        cand = os.path.join(base_dir, f"{video_title}{ext}")
        if os.path.exists(cand):
            video_path = cand
            break

    if not video_path:
        # Check if video_title already has an extension or look for files in dir
        raise FileNotFoundError(f"Cannot find video corresponding to title '{video_title}' in {base_dir}")

    if output_dir is None:
        output_dir = os.path.join(base_dir, "clips")
    os.makedirs(output_dir, exist_ok=True)

    chapters = data.get("chapters", [])
    segments = data.get("segments", [])
    created_clips = []

    print(f"\n[Clipper] Starting video clipping for: {video_path}")
    print(f"[Clipper] Output directory: {output_dir}\n")

    for ch in chapters:
        is_highlight = ch.get("is_highlight", False)
        if only_highlights and not is_highlight:
            continue

        ch_id = ch.get("id", 1)
        ch_title = sanitize_filename(ch.get("title", f"chapter_{ch_id}"))
        start_sec = max(0.0, ch.get("start_sec", 0.0) - 1.5)  # 1.5s padding
        end_sec = ch.get("end_sec", 0.0) + 1.0                # 1.0s padding
        start_tag = ch.get("start", "00_00_00").replace(':', '_')
        end_tag = ch.get("end", "00_00_00").replace(':', '_')

        clip_filename = f"高光切片{ch_id}_{start_tag}-{end_tag}_{ch_title}.mp4"
        clip_path = os.path.join(output_dir, clip_filename)
        srt_path = os.path.join(output_dir, f"高光切片{ch_id}_{start_tag}-{end_tag}_{ch_title}.srt")

        dur = end_sec - start_sec
        print(f"🎬 [Clip {ch_id}] '{ch.get('title')}' ({ch.get('start')} -> {ch.get('end')}, 时长 {dur:.1f}s)")
        print(f"   导出至: {clip_filename} ...")

        if cut_clip(video_path, start_sec, end_sec, clip_path):
            slice_subtitles(segments, start_sec, end_sec, srt_path)
            created_clips.append(clip_path)
            print(f"   ✓ 视频切片与同步字幕导出成功!")
        else:
            print(f"   ✗ 切片失败")

    print(f"\n[Clipper] 任务完成! 共生成 {len(created_clips)} 个高光短视频切片\n")
    return created_clips

def main():
    parser = argparse.ArgumentParser(description="Livestream Highlight Video Clipper")
    parser.add_argument("--analysis", "-a", help="Path to *_analysis.json file")
    parser.add_argument("--video", "-v", help="Path to video file")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS")
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS")
    parser.add_argument("--title", default="clip", help="Title for the clip")
    parser.add_argument("--output-dir", "-o", help="Output directory for clips")
    parser.add_argument("--all", action="store_true", help="Clip all chapters instead of only highlights")
    args = parser.parse_args()

    if args.analysis:
        auto_clip_from_analysis(args.analysis, output_dir=args.output_dir, only_highlights=not args.all)
    elif args.video and args.start and args.end:
        # Manual single cut
        def to_sec(s):
            if ':' in str(s):
                p = str(s).split(':')
                if len(p) == 3: return float(p[0])*3600 + float(p[1])*60 + float(p[2])
                if len(p) == 2: return float(p[0])*60 + float(p[1])
            return float(s)
        s_sec = to_sec(args.start)
        e_sec = to_sec(args.end)
        out_dir = args.output_dir or os.path.dirname(os.path.abspath(args.video))
        out_file = os.path.join(out_dir, f"{sanitize_filename(args.title)}.mp4")
        cut_clip(args.video, s_sec, e_sec, out_file)
        print(f"Exported clip to: {out_file}")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
