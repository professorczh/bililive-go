#!/usr/bin/env python3
"""
Danmaku parser and engagement heat analysis module.
Parses bililive-go generated .ass subtitle/danmaku files, calculates sliding-window
frequency curves, and detects audience engagement spikes.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

def parse_ass_time(timestr: str) -> float:
    """Converts ASS timestamp H:MM:SS.ss to seconds."""
    parts = timestr.strip().split(':')
    if len(parts) != 3:
        return 0.0
    h = float(parts[0])
    m = float(parts[1])
    s = float(parts[2])
    return h * 3600.0 + m * 60.0 + s

def format_time(seconds: float) -> str:
    """Converts seconds into HH:MM:SS or MM:SS."""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

class DanmakuEvent:
    def __init__(self, start: float, end: float, style: str, text: str):
        self.start = start
        self.end = end
        self.style = style
        self.raw_text = text
        
        # Strip ASS styling tags like {\c&H00FFFFFF&}
        clean = re.sub(r'\{[^}]*\}', '', text).strip()
        
        # Parse "Username: Message" if present
        if ': ' in clean:
            user, msg = clean.split(': ', 1)
            self.user = user.strip()
            self.content = msg.strip()
        elif '：' in clean:
            user, msg = clean.split('：', 1)
            self.user = user.strip()
            self.content = msg.strip()
        else:
            self.user = ""
            self.content = clean

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "user": self.user,
            "content": self.content,
            "style": self.style
        }

class DanmakuAnalyzer:
    def __init__(self, ass_file_path: str):
        self.file_path = ass_file_path
        self.events: List[DanmakuEvent] = []
        self.heat_metrics: List[Dict[str, Any]] = []
        self._load_ass()
        self._load_heat_metrics()

    def _load_ass(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('Dialogue:'):
                        parts = line[len('Dialogue:'):].strip().split(',', 9)
                        if len(parts) >= 10:
                            start_str = parts[1].strip()
                            end_str = parts[2].strip()
                            style = parts[3].strip()
                            text = parts[9].strip()
                            
                            start_sec = parse_ass_time(start_str)
                            end_sec = parse_ass_time(end_str)
                            self.events.append(DanmakuEvent(start_sec, end_sec, style, text))
            self.events.sort(key=lambda x: x.start)
        except Exception as e:
            print(f"[DanmakuAnalyzer] Error loading {self.file_path}: {e}")

    def _load_heat_metrics(self):
        """Loads companion _heat.json if present."""
        base, _ = os.path.splitext(self.file_path)
        candidates = [
            f"{base}_heat.json",
            f"{base.rstrip('.flv')}_heat.json",
            os.path.join(os.path.dirname(self.file_path), f"{os.path.basename(base)}_heat.json")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, 'r', encoding='utf-8') as f:
                        self.heat_metrics = json.load(f)
                    print(f"[DanmakuAnalyzer] Loaded companion heat metrics: {c} ({len(self.heat_metrics)} buckets)")
                    break
                except Exception as e:
                    print(f"[DanmakuAnalyzer] Error loading {c}: {e}")

    def total_count(self) -> int:
        return len(self.events)

    def get_events_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "start": round(e.start, 2),
                "end": round(e.end, 2),
                "start_str": format_time(e.start),
                "user": e.user,
                "content": e.content,
                "style": e.style
            }
            for e in self.events
        ]

    def duration(self) -> float:
        if not self.events:
            if self.heat_metrics:
                return float(self.heat_metrics[-1].get("time_sec", 0))
            return 0.0
        return max(e.end for e in self.events)

    def compute_density_curve(self, window_sec: int = 30) -> List[Dict[str, Any]]:
        """
        Calculates danmaku count and like velocity per window (e.g. 30-second bins).
        """
        max_t = self.duration()
        if max_t <= 0:
            return []
        
        num_bins = int(max_t // window_sec) + 1
        bins = [{"time": i * window_sec, "danmaku": 0, "likes": 0, "messages": []} for i in range(num_bins)]
        
        # 1. Bucket ASS danmaku events
        for e in self.events:
            bin_idx = int(e.start // window_sec)
            if 0 <= bin_idx < num_bins:
                bins[bin_idx]["danmaku"] += 1
                if len(bins[bin_idx]["messages"]) < 5:
                    bins[bin_idx]["messages"].append(f"{e.user}: {e.content}" if e.user else e.content)

        # 2. Bucket companion like metrics if present
        for hm in self.heat_metrics:
            t = hm.get("time_sec", 0)
            bin_idx = int(t // window_sec)
            if 0 <= bin_idx < num_bins:
                bins[bin_idx]["likes"] += hm.get("likes", 0)

        curve = []
        for b in bins:
            # Weighted heat score: 1 danmaku = 1.0 point, 30 likes = 1.0 point
            combined_score = b["danmaku"] + round(b["likes"] / 30.0, 1)
            curve.append({
                "time": b["time"],
                "time_str": format_time(b["time"]),
                "count": b["danmaku"],
                "likes": b["likes"],
                "heat_score": combined_score,
                "density": round(combined_score / window_sec, 2),
                "samples": b["messages"]
            })
        return curve

    def find_peaks(self, window_sec: int = 30, top_n: int = 6) -> List[Dict[str, Any]]:
        """
        Finds the top N engagement spikes based on combined heat score (danmaku + likes).
        """
        curve = self.compute_density_curve(window_sec)
        if not curve:
            return []
        
        sorted_bins = sorted(curve, key=lambda x: x["heat_score"], reverse=True)
        peaks = []
        selected_times = []
        
        min_distance = window_sec * 2
        for b in sorted_bins:
            if b["heat_score"] <= 0:
                continue
            t = b["time"]
            if any(abs(t - st) < min_distance for st in selected_times):
                continue
            peaks.append(b)
            selected_times.append(t)
            if len(peaks) >= top_n:
                break
        
        peaks.sort(key=lambda x: x["time"])
        return peaks

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        analyzer = DanmakuAnalyzer(path)
        print(f"Total Danmaku: {analyzer.total_count()}")
        print(f"Estimated Duration: {format_time(analyzer.duration())}")
        print("\n--- Top Engagement Peaks ---")
        for p in analyzer.find_peaks():
            print(f"[{p['time_str']}] Count: {p['count']} (Density: {p['density']}/s)")
            for s in p['samples']:
                print(f"   * {s}")
