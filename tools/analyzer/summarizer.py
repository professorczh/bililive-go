#!/usr/bin/env python3
"""
AI Chapter & Summarization module using local Ollama (qwen2.5:3b).
Segments transcript into topical chapters with titles, summaries, key points,
and correlates with danmaku excitement peaks.
"""

import os
import re
import json
import urllib.request
from typing import List, Dict, Any, Optional

def sec_to_str(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"

def str_to_sec(timestr: str) -> float:
    parts = timestr.strip().split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0

class StreamSummarizer:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:3b"):
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model

    def _call_ollama(self, prompt: str, system: Optional[str] = None) -> str:
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,  # Low temperature for factual consistency
                "num_ctx": 16384     # Extended context window for long streams
            }
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get("response", "")
        except Exception as e:
            print(f"[Summarizer] Ollama call error or timeout: {e}")
            return ""

    def coalesce_segments(self, segments: List[Dict[str, Any]], target_duration: float = 60.0) -> List[Dict[str, Any]]:
        """
        Coalesces small sentence-level segments into readable paragraphs with timestamps.
        """
        if not segments:
            return []

        coalesced = []
        cur_text = []
        cur_start = segments[0]["start"]
        cur_end = segments[0]["end"]

        for seg in segments:
            cur_text.append(seg["text"])
            cur_end = seg["end"]
            if (cur_end - cur_start) >= target_duration:
                coalesced.append({
                    "start": cur_start,
                    "end": cur_end,
                    "start_str": sec_to_str(cur_start),
                    "end_str": sec_to_str(cur_end),
                    "text": "".join(cur_text).strip()
                })
                cur_text = []
                cur_start = cur_end

        if cur_text:
            coalesced.append({
                "start": cur_start,
                "end": cur_end,
                "start_str": sec_to_str(cur_start),
                "end_str": sec_to_str(cur_end),
                "text": "".join(cur_text).strip()
            })

        return coalesced

    def generate_chapters(self, transcript_segments: List[Dict[str, Any]], danmaku_peaks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyzes the transcript and groups into structured chapters.
        """
        if not transcript_segments:
            return []

        total_dur = transcript_segments[-1].get("end", 0.0) - transcript_segments[0].get("start", 0.0)
        # Adapt target duration so paragraph count stays between 25-35 for fast, reliable LLM inference
        target_dur = 60.0
        if total_dur > 2400: # > 40 mins
            target_dur = max(60.0, round(total_dur / 30.0))

        paragraphs = self.coalesce_segments(transcript_segments, target_duration=target_dur)
        
        # Build prompt input
        transcript_lines = []
        for p in paragraphs:
            transcript_lines.append(f"[{p['start_str']} -> {p['end_str']}] {p['text']}")
        transcript_text = "\n".join(transcript_lines)

        peak_summary = []
        for p in danmaku_peaks:
            peak_summary.append(f"时间点: {p['time_str']}, 弹幕密度: {p['count']}条, 观众反响热词: {', '.join(p['samples'][:3])}")
        peak_text = "\n".join(peak_summary)

        system_prompt = (
            "你是一位极其资深的直播内容切片分析师与重点提炼专家。\n"
            "你的任务是根据给出的带时间戳的直播录音转文字记录（以及观众弹幕密集反响点），"
            "对直播内容进行宏观段落划分（通常每个主题章节2-8分钟左右，勿碎裂过细），"
            "精准定位切片起止时间，并输出客观、准确的章节总结。"
        )

        user_prompt = f"""以下是一场直播的转文字记录：
{transcript_text}

同时检测到以下弹幕互动高峰时刻（观众情绪高涨/热点话题）：
{peak_text}

请完成以下分析任务：
1. 梳理主播讲解的不同主题或话题转移节点，划分成连贯的章节（按时间正序排列，时间必须覆盖整个直播过程，起止时间严格对应上述时间范围）。
2. 为每个章节拟定一个吸引眼球、精准概括内容的标题（title）。
3. 用2-3句话撰写内容摘要（summary）。
4. 列出2-4条核心要点（key_points），包含关键人名、事件、主播观点。
5. 给出1-3个分类标签（tags）。

请【严格】输出 JSON 数组格式，不要输出多余的解释、开场白或结束语。
格式规范：
[
  {{
    "start": "00:00:00",
    "end": "00:06:30",
    "title": "章节标题",
    "summary": "内容概述...",
    "key_points": ["核心信息点1", "核心信息点2"],
    "tags": ["标签1", "标签2"]
  }}
]
"""

        print(f"[Summarizer] Sending {len(paragraphs)} paragraph blocks (target_dur={target_dur}s) to Ollama {self.model} ...")
        response = self._call_ollama(user_prompt, system=system_prompt)
        
        # Parse JSON from response (robust to backticks)
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            try:
                chapters = json.loads(json_match.group(0))
                # Validate and enhance chapters
                enhanced = []
                for idx, ch in enumerate(chapters):
                    s_sec = str_to_sec(ch.get("start", "00:00:00"))
                    e_sec = str_to_sec(ch.get("end", "00:00:00"))
                    
                    # Find associated danmaku peaks in this chapter
                    ch_peaks = [p for p in danmaku_peaks if s_sec <= p["time"] <= e_sec]
                    
                    enhanced.append({
                        "id": idx + 1,
                        "start": ch.get("start", "00:00:00"),
                        "end": ch.get("end", "00:00:00"),
                        "start_sec": s_sec,
                        "end_sec": e_sec,
                        "title": ch.get("title", f"第 {idx+1} 章节"),
                        "summary": ch.get("summary", ""),
                        "key_points": ch.get("key_points", []),
                        "tags": ch.get("tags", []),
                        "peaks": ch_peaks,
                        "is_highlight": len(ch_peaks) > 0 or (idx in [0, 1])
                    })
                return enhanced
            except Exception as e:
                print(f"[Summarizer] JSON parse error: {e}, raw text:\n{response}")
        else:
            print(f"[Summarizer] No valid JSON array found in Ollama response. Falling back to structured time partition.")

        # Robust multi-chapter fallback if LLM response parsing fails
        num_sections = min(8, max(4, len(paragraphs) // 4)) if paragraphs else 1
        step = max(1, len(paragraphs) // num_sections) if paragraphs else 1
        fallback_chapters = []
        for i in range(num_sections):
            idx_start = i * step
            idx_end = min(len(paragraphs) - 1, (i + 1) * step - 1) if i < num_sections - 1 else len(paragraphs) - 1
            if idx_start >= len(paragraphs):
                break
            p_s = paragraphs[idx_start]
            p_e = paragraphs[idx_end]
            s_time = p_s["start_str"]
            e_time = p_e["end_str"]
            s_sec = p_s["start"]
            e_sec = p_e["end"]
            title_text = p_s["text"][:20].replace("\n", " ").strip()
            ch_peaks = [p for p in danmaku_peaks if s_sec <= p["time"] <= e_sec]
            fallback_chapters.append({
                "id": i + 1,
                "start": s_time,
                "end": e_time,
                "start_sec": s_sec,
                "end_sec": e_sec,
                "title": f"实录第 {i+1} 段: {title_text}...",
                "summary": p_s["text"][:150],
                "key_points": [p_s["text"][:60], p_e["text"][:60]],
                "tags": ["直播实录", "自动切片"],
                "peaks": ch_peaks,
                "is_highlight": len(ch_peaks) > 0 or (i in [0, 1])
            })
        return fallback_chapters
