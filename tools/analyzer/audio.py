#!/usr/bin/env python3
"""
Audio extraction utility using FFmpeg.
Extracts 16kHz mono 16-bit PCM WAV from livestream video (.flv, .mp4, etc.)
optimized for Whisper speech recognition.
"""

import os
import subprocess
from typing import Optional

def extract_audio_for_whisper(video_path: str, output_wav_path: Optional[str] = None) -> str:
    """
    Extracts audio from video_path and converts to 16000Hz mono 16-bit WAV.
    If output_wav_path is None, saves alongside the video file.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    if output_wav_path is None:
        base, _ = os.path.splitext(video_path)
        output_wav_path = f"{base}_audio16k.wav"
        
    # Check if target already exists and is non-empty
    if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 1024:
        print(f"[Audio] Using cached audio file: {output_wav_path}")
        return output_wav_path

    print(f"[Audio] Extracting 16kHz WAV from {video_path} -> {output_wav_path} ...")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav_path
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg failed with code {res.returncode}: {res.stderr.decode('utf-8', errors='ignore')}")
    
    print(f"[Audio] Extracted successfully: {output_wav_path} ({os.path.getsize(output_wav_path) / (1024*1024):.2f} MB)")
    return output_wav_path

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        extract_audio_for_whisper(sys.argv[1])
