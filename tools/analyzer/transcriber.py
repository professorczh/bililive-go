#!/usr/bin/env python3
"""
Transcription module using whisper-cli (whisper.cpp).
Leverages Apple Silicon Metal acceleration to transcribe audio locally.
"""

import os
import re
import json
import subprocess
from typing import List, Dict, Any, Optional

try:
    import zhconv
    def to_simplified(text: str) -> str:
        return zhconv.convert(text, 'zh-cn')
except ImportError:
    def to_simplified(text: str) -> str:
        return text

class WhisperTranscriber:
    def __init__(self, model_path: str = "tools/analyzer/models/ggml-small.bin", whisper_bin: str = "whisper-cli"):
        self.model_path = os.path.abspath(model_path)
        self.whisper_bin = whisper_bin

    def transcribe(self, wav_path: str, output_prefix: Optional[str] = None, language: str = "zh", threads: int = 8) -> Dict[str, Any]:
        """
        Transcribes the wav file. Returns normalized transcription dictionary:
        {
            "segments": [
                {"start": 0.0, "end": 5.2, "start_str": "00:00:00", "end_str": "00:00:05", "text": "..."},
                ...
            ],
            "full_text": "...",
            "duration": float
        }
        """
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"Audio file not found: {wav_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Whisper model not found at {self.model_path}")

        if output_prefix is None:
            base, _ = os.path.splitext(wav_path)
            output_prefix = f"{base}_whisper"

        json_file = f"{output_prefix}.json"
        
        # Check cache
        if os.path.exists(json_file) and os.path.getsize(json_file) > 100:
            print(f"[Transcriber] Using cached transcription: {json_file}")
            return self._parse_json(json_file)

        print(f"[Transcriber] Starting whisper-cli inference on {wav_path} ...")
        cmd = [
            self.whisper_bin,
            "-m", self.model_path,
            "-f", os.path.abspath(wav_path),
            "-l", language,
            "-t", str(threads),
            "--prompt", "以下是普通话的简体中文内容。",
            "-oj",
            "-osrt",
            "-of", output_prefix,
            "-pp"
        ]

        print(f"[Transcriber] Running command: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"whisper-cli failed (code {res.returncode}): {res.stderr.decode('utf-8', errors='ignore')}")

        if not os.path.exists(json_file):
            raise FileNotFoundError(f"Expected whisper output file not found: {json_file}")

        return self._parse_json(json_file, srt_file=f"{output_prefix}.srt")

    def _parse_json(self, json_file: str, srt_file: Optional[str] = None) -> Dict[str, Any]:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        raw_segments = data.get("transcription", [])
        segments = []
        full_text_list = []

        # Bracketed noise annotations common in Whisper hallucinated on mouth/eating sounds
        noise_pattern = re.compile(
            r'[\(（\[【](?:口误|口誤|笑声|笑聲|掌声|掌聲|咳嗽|咳|music|applause|laughter|叹气|嘆氣|喘息|吸吮|杂音|噪音)[\)）\]】]',
            re.IGNORECASE
        )
        punct_strip_pattern = re.compile(r'^[。，！？、.,!?:：\s]+|[。，！？、.,!?:：\s]+$')

        for item in raw_segments:
            raw_text = item.get("text", "").strip()
            if not raw_text:
                continue

            # 1. Strip bracketed noise tokens
            cleaned = noise_pattern.sub('', raw_text).strip()
            # 2. Check if anything substantial remains (not just residual punctuation)
            stripped = punct_strip_pattern.sub('', cleaned).strip()
            if not stripped or stripped in {"口误", "口誤"}:
                continue

            # 3. Convert to Simplified Chinese
            text = to_simplified(cleaned)

            # offsets is in ms
            offsets = item.get("offsets", {})
            start_sec = offsets.get("from", 0) / 1000.0
            end_sec = offsets.get("to", 0) / 1000.0
            
            timestamps = item.get("timestamps", {})
            start_str = timestamps.get("from", "")
            end_str = timestamps.get("to", "")

            segments.append({
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "start_str": start_str,
                "end_str": end_str,
                "text": text
            })
            full_text_list.append(text)

        # Also write cleaned SRT if path provided
        if srt_file:
            try:
                with open(srt_file, 'w', encoding='utf-8') as f:
                    for idx, seg in enumerate(segments, start=1):
                        f.write(f"{idx}\n")
                        f.write(f"{self._sec_to_srt_time(seg['start'])} --> {self._sec_to_srt_time(seg['end'])}\n")
                        f.write(f"{seg['text']}\n\n")
            except Exception as e:
                print(f"[Transcriber] Warning: failed to write cleaned SRT: {e}")

        max_dur = segments[-1]["end"] if segments else 0.0
        return {
            "segments": segments,
            "full_text": "\n".join(full_text_list),
            "duration": max_dur
        }

    @staticmethod
    def _sec_to_srt_time(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            ms = 999
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        t = WhisperTranscriber()
        res = t.transcribe(sys.argv[1])
        print(f"Transcription finished! Segments: {len(res['segments'])}, Duration: {res['duration']}s")
