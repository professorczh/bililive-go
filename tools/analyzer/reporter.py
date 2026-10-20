#!/usr/bin/env python3
"""
Interactive HTML Report Generator for Livestream Analysis.
Renders a desktop-class AI Studio Workspace:
- 16:9 Responsive Video Player with FLV (mpegts.js) & MP4 support (Vertical/Horizontal adaptive)
- Progress bar chapter markers & heat peak dots (Artplayer highlight)
- Interactive Engagement Heatmap with real-time synchronized playhead needle
- Seamless Switcher between Full Livestream & Highlight Video Clips
- Dual-panel Layout with AI Chapter Cards & Karaoke-style Auto-scrolling Subtitles
"""

import os
import json
import re
from typing import Dict, Any, List

try:
    import zhconv
    def to_simplified(text: str) -> str:
        return zhconv.convert(str(text), 'zh-cn')
except ImportError:
    def to_simplified(text: str) -> str:
        return str(text)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__STREAM_TITLE__ - AI 智能切片与分段归纳报告</title>
  
  <!-- mpegts.js & Artplayer -->
  <script src="https://cdn.jsdelivr.net/npm/mpegts.js@1.7.3/dist/mpegts.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/artplayer@5.1.1/dist/artplayer.js"></script>

  <style>
    :root {
      --bg: #07090e;
      --surface: #0f172a;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-hover: rgba(56, 189, 248, 0.25);
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --accent-fire: #f43f5e;
      --accent-glow: rgba(244, 63, 94, 0.35);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --tag-bg: rgba(56, 189, 248, 0.1);
      --tag-border: rgba(56, 189, 248, 0.25);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(circle at 20% 0%, rgba(30, 27, 75, 0.5) 0%, transparent 50%),
        radial-gradient(circle at 80% 0%, rgba(15, 23, 42, 0.8) 0%, transparent 60%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      min-height: 100vh;
      padding: 1.25rem 1.75rem 2rem;
      line-height: 1.5;
    }

    .container {
      max-width: 1720px;
      margin: 0 auto;
    }

    /* Header Bar */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 1.25rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .badge-live {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 10px;
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #fb7185;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
    }

    .badge-live .pulse {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #f43f5e;
      box-shadow: 0 0 8px #f43f5e;
      animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    h1 {
      font-size: 1.35rem;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.01em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 750px;
    }

    .stats-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .stat-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    .stat-pill b {
      color: var(--text);
      font-weight: 600;
    }

    /* Main Studio Grid Layout */
    .studio-grid {
      display: grid;
      grid-template-columns: minmax(0, 58%) minmax(0, 42%);
      gap: 20px;
      align-items: start;
    }

    @media (max-width: 1100px) {
      .studio-grid {
        grid-template-columns: 1fr;
      }
    }

    /* Left Column: Visual & Heatmap Hub */
    .studio-left {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .player-card {
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 9;
      background: radial-gradient(circle at center, #111827 0%, #030712 100%);
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--card-border);
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    #artplayer-container {
      width: 100%;
      height: 100%;
      position: relative;
      z-index: 2;
    }

    #artplayer-container video {
      object-fit: contain !important;
    }

    /* Source Selector Bar */
    .source-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(15, 23, 42, 0.7);
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      overflow-x: auto;
      scrollbar-width: thin;
    }

    .source-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-dim);
      white-space: nowrap;
      margin-right: 4px;
    }

    .src-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.78rem;
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s ease;
      user-select: none;
    }

    .src-pill:hover {
      background: rgba(56, 189, 248, 0.15);
      border-color: rgba(56, 189, 248, 0.4);
      color: var(--text);
    }

    .src-pill.active {
      background: rgba(56, 189, 248, 0.22);
      border-color: var(--primary);
      color: #38bdf8;
      font-weight: 600;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
    }

    /* Heatmap Card */
    .heatmap-card {
      background: rgba(15, 23, 42, 0.75);
      border-radius: 10px;
      border: 1px solid var(--card-border);
      padding: 10px 14px 12px;
      position: relative;
    }

    .heatmap-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .heatmap-title {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .heatmap-hint {
      font-size: 0.72rem;
      color: var(--text-dim);
    }

    .chart-container {
      position: relative;
      height: 90px;
      width: 100%;
      cursor: pointer;
    }

    svg.heat-svg {
      width: 100%;
      height: 100%;
      display: block;
      overflow: visible;
    }

    .chart-tooltip {
      position: absolute;
      display: none;
      pointer-events: none;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid var(--primary);
      border-radius: 6px;
      padding: 5px 9px;
      font-size: 0.75rem;
      color: #fff;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
      transform: translate(-50%, -120%);
      white-space: nowrap;
      z-index: 10;
    }

    /* Right Column: AI Intelligence & Transcript */
    .studio-right {
      display: flex;
      flex-direction: column;
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border-radius: 12px;
      border: 1px solid var(--card-border);
      height: calc(100vh - 110px);
      min-height: 580px;
      overflow: hidden;
    }

    .tabs-header {
      display: flex;
      border-bottom: 1px solid var(--card-border);
      background: rgba(15, 23, 42, 0.8);
    }

    .tab-btn {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 10px 10px;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
    }

    .tab-btn:hover {
      color: var(--text);
      background: rgba(255, 255, 255, 0.02);
    }

    .tab-btn.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
      background: rgba(56, 189, 248, 0.06);
    }

    .tab-content {
      flex: 1;
      overflow-y: auto;
      padding: 14px;
      scrollbar-width: thin;
      scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
    }

    /* Chapter Cards */
    .chapter-cards-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .chapter-card {
      background: rgba(30, 41, 59, 0.5);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 12px 14px;
      transition: all 0.25s ease;
      position: relative;
    }

    .chapter-card:hover {
      background: rgba(30, 41, 59, 0.8);
      border-color: var(--card-hover);
      transform: translateY(-1px);
    }

    .chapter-card.highlight {
      background: linear-gradient(135deg, rgba(244, 63, 94, 0.07) 0%, rgba(30, 41, 59, 0.6) 100%);
      border-color: rgba(244, 63, 94, 0.3);
    }

    .chapter-card.active-chapter {
      border-color: var(--primary) !important;
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
      background: rgba(30, 41, 59, 0.95);
    }

    .chapter-card.active-chapter::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 4px;
      background: var(--primary);
      border-top-left-radius: 10px;
      border-bottom-left-radius: 10px;
    }

    .chapter-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 6px;
    }

    .jump-btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: #38bdf8;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .jump-btn:hover {
      background: var(--primary);
      color: #000;
    }

    .chapter-title {
      font-size: 0.95rem;
      font-weight: 700;
      color: #fff;
      margin-top: 4px;
    }

    .card-badges {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }

    .peak-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 7px;
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.35);
      color: #fb7185;
      border-radius: 9999px;
      font-size: 0.7rem;
      font-weight: 600;
    }

    .clip-badge-btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 7px;
      background: rgba(168, 85, 247, 0.15);
      border: 1px solid rgba(168, 85, 247, 0.35);
      color: #c084fc;
      border-radius: 9999px;
      font-size: 0.7rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }

    .clip-badge-btn:hover {
      background: #a855f7;
      color: #fff;
    }

    .chapter-summary {
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 8px;
      line-height: 1.45;
    }

    .key-points {
      margin-left: 18px;
      margin-bottom: 8px;
      font-size: 0.78rem;
      color: var(--text-muted);
    }

    .key-points li {
      margin-bottom: 3px;
    }

    .tags-list {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }

    .tag-item {
      font-size: 0.7rem;
      color: var(--primary);
      background: var(--tag-bg);
      border: 1px solid var(--tag-border);
      padding: 1px 6px;
      border-radius: 4px;
    }

    /* Transcript Panel */
    .search-box {
      margin-bottom: 10px;
      position: sticky;
      top: 0;
      z-index: 5;
      background: var(--surface);
      padding-bottom: 8px;
    }

    .search-input {
      width: 100%;
      padding: 8px 12px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      color: #fff;
      font-size: 0.82rem;
      outline: none;
      transition: all 0.2s ease;
    }

    .search-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 8px rgba(56, 189, 248, 0.3);
    }

    .transcript-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .transcript-line {
      display: flex;
      align-items: baseline;
      gap: 10px;
      padding: 6px 10px;
      border-radius: 6px;
      background: rgba(30, 41, 59, 0.3);
      cursor: pointer;
      transition: all 0.15s ease;
      font-size: 0.82rem;
      border: 1px solid transparent;
    }

    .transcript-line:hover {
      background: rgba(30, 41, 59, 0.7);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .transcript-line.active-line {
      background: rgba(56, 189, 248, 0.15) !important;
      border-color: var(--primary) !important;
      color: #fff;
      font-weight: 500;
    }

    .ts-time {
      font-family: monospace;
      color: var(--primary);
      font-size: 0.72rem;
      flex-shrink: 0;
    }

    .ts-text {
      color: var(--text);
      line-height: 1.4;
    }

    /* Danmaku Panel */
    .danmaku-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .danmaku-line {
      display: flex;
      align-items: baseline;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 6px;
      background: rgba(30, 41, 59, 0.3);
      cursor: pointer;
      transition: all 0.15s ease;
      font-size: 0.82rem;
      border: 1px solid transparent;
    }

    .danmaku-line:hover {
      background: rgba(30, 41, 59, 0.7);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .danmaku-line.active-line {
      background: rgba(245, 158, 11, 0.15) !important;
      border-color: #f59e0b !important;
      color: #fff;
      font-weight: 500;
    }

    .dm-time {
      font-family: monospace;
      color: var(--primary);
      font-size: 0.72rem;
      flex-shrink: 0;
    }

    .dm-user {
      color: #f59e0b;
      font-weight: 600;
      font-size: 0.78rem;
      flex-shrink: 0;
      max-width: 130px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dm-text {
      color: var(--text);
      line-height: 1.4;
      word-break: break-word;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-left">
        <span class="badge-live"><span class="pulse"></span> LIVE 智能切片分析</span>
        <h1>__STREAM_TITLE__</h1>
      </div>
      <div class="stats-bar">
        <span class="stat-pill">⏱️ 时长 <b>__DURATION_STR__</b></span>
        <span class="stat-pill">💬 弹幕 <b>__TOTAL_DANMAKU__</b> 条</span>
        <span class="stat-pill">📑 章节 <b>__TOTAL_CHAPTERS__</b> 段</span>
        <span class="stat-pill">🔥 峰值 <b>__MAX_DENSITY__</b> 条/30s</span>
      </div>
    </header>

    <div class="studio-grid">
      <!-- Left Column: Video Player & Heatmap -->
      <div class="studio-left">
        <div class="player-card">
          <div id="artplayer-container"></div>
        </div>

        <!-- Video Source Switcher -->
        <div class="source-bar">
          <span class="source-label">播放源:</span>
          __SOURCE_PILLS_HTML__
        </div>

        <!-- Compact Heatmap Timeline -->
        <div class="heatmap-card">
          <div class="heatmap-header">
            <span class="heatmap-title">📈 互动热度与点赞走势 (30s 窗口)</span>
            <span class="heatmap-hint">💡 点击折线图可快速跳播</span>
          </div>
          <div class="chart-container" id="chartBox">
            <svg class="heat-svg" id="heatSvg" preserveAspectRatio="none">
              <defs>
                <linearGradient id="heatGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4" />
                  <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0" />
                </linearGradient>
              </defs>
              <line id="chartPlayhead" x1="0" y1="0" x2="0" y2="90" stroke="#38bdf8" stroke-width="2" stroke-dasharray="3,2" style="display:none;" />
            </svg>
            <div class="chart-tooltip" id="chartTip"></div>
          </div>
        </div>
      </div>

      <!-- Right Column: AI Intelligence, Transcript & Danmaku Panel -->
      <div class="studio-right">
        <div class="tabs-header">
          <button class="tab-btn active" id="tabBtnChapters" onclick="switchTab('chapters')">
            🌟 AI 结构化章节 (__TOTAL_CHAPTERS__)
          </button>
          <button class="tab-btn" id="tabBtnTranscript" onclick="switchTab('transcript')">
            📝 逐句检索字幕 (__TOTAL_SEGMENTS__)
          </button>
          <button class="tab-btn" id="tabBtnDanmaku" onclick="switchTab('danmaku')">
            💬 实时弹幕明细 (__TOTAL_DANMAKU__)
          </button>
        </div>

        <!-- Tab 1: Chapters -->
        <div class="tab-content" id="panelChapters">
          <div class="chapter-cards-list">
            __CHAPTER_CARDS_HTML__
          </div>
        </div>

        <!-- Tab 2: Transcript -->
        <div class="tab-content" id="panelTranscript" style="display:none;">
          <div class="search-box">
            <input type="text" class="search-input" id="searchInput" placeholder="🔍 搜索主播发言关键词..." />
          </div>
          <div class="transcript-list" id="transcriptList">
            __TRANSCRIPT_ITEMS_HTML__
          </div>
        </div>

        <!-- Tab 3: Danmaku -->
        <div class="tab-content" id="panelDanmaku" style="display:none;">
          <div class="search-box">
            <input type="text" class="search-input" id="danmakuSearchInput" placeholder="🔍 搜索弹幕内容或发送者昵称..." />
          </div>
          <div class="danmaku-list" id="danmakuList">
            __DANMAKU_ITEMS_HTML__
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const curveData = __CURVE_DATA_JSON__;
    const chaptersData = __CHAPTERS_DATA_JSON__;
    const durationSec = __DURATION_SEC__;
    const mainVideoUrl = "__MAIN_VIDEO_URL__";
    const mainSubtitleUrl = "__MAIN_SUBTITLE_URL__";

    let currentSource = 'main';
    let currentTab = 'chapters';

    // 1. Initialize Highlights for Timeline
    const timelineHighlights = [];
    chaptersData.forEach(ch => {
      if (ch.start_sec !== undefined) {
        timelineHighlights.push({
          time: Math.round(ch.start_sec),
          text: '📌 ' + ch.title
        });
      }
    });

    const peaksData = __PEAKS_DATA_JSON__;
    peaksData.forEach(p => {
      if (p.time !== undefined) {
        timelineHighlights.push({
          time: Math.round(p.time),
          text: '🔥 峰值 (' + p.count + '条/30s)'
        });
      }
    });

    // 2. Initialize Artplayer
    const isFlv = mainVideoUrl.toLowerCase().endsWith('.flv');
    const art = new Artplayer({
      container: '#artplayer-container',
      url: mainVideoUrl,
      type: isFlv ? 'flv' : 'mp4',
      customType: {
        flv: function(video, url, artInstance) {
          if (window.mpegts && window.mpegts.isSupported()) {
            const flvPlayer = window.mpegts.createPlayer({
              type: 'flv',
              url: url,
              hasVideo: true,
              hasAudio: true,
              isLive: false,
              lazyLoad: true,
              enableStashBuffer: false
            });
            flvPlayer.attachMediaElement(video);
            flvPlayer.load();
            artInstance.flvPlayer = flvPlayer;
            artInstance.on('destroy', () => flvPlayer.destroy());
          } else {
            artInstance.notice.show = '浏览器不支持 MSE FLV 解码';
          }
        }
      },
      volume: 0.75,
      isLive: false,
      muted: false,
      autoplay: false,
      pip: true,
      autoSize: false,
      screenshot: true,
      playbackRate: true,
      aspectRatio: true,
      fullscreen: true,
      fullscreenWeb: true,
      miniProgressBar: true,
      mutex: true,
      backdrop: true,
      playsInline: true,
      theme: '#38bdf8',
      lang: 'zh-cn',
      highlight: timelineHighlights,
      subtitle: mainSubtitleUrl ? {
        url: mainSubtitleUrl,
        type: 'srt',
        encoding: 'utf-8',
        style: {
          color: '#ffffff',
          fontSize: '18px',
          textShadow: '0 2px 4px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.8)'
        }
      } : undefined
    });

    // 3. Jump to Time function
    window.jumpToTime = function(sec, el) {
      if (!art) return;
      const targetSec = parseFloat(sec) || 0;

      if (el) {
        document.querySelectorAll('.transcript-line, .danmaku-line').forEach(l => l.classList.remove('active-line'));
        el.classList.add('active-line');
      }

      if (currentSource !== 'main') {
        const mainPill = document.getElementById('src_pill_main');
        switchSource(mainVideoUrl, isFlv, mainPill, 'main');
        setTimeout(() => {
          art.currentTime = targetSec;
          art.play();
        }, 200);
        return;
      }
      art.currentTime = targetSec;
      art.play();
    };

    // 4. Switch Source function
    window.switchSource = function(url, flvMode, pillEl, sourceKey) {
      currentSource = sourceKey || 'clip';
      document.querySelectorAll('.src-pill').forEach(p => p.classList.remove('active'));
      if (pillEl) pillEl.classList.add('active');

      if (art.flvPlayer) {
        art.flvPlayer.destroy();
        art.flvPlayer = null;
      }
      art.switchUrl(url);
      art.play();
    };

    window.playClip = function(clipUrl, pillId) {
      const pill = pillId ? document.getElementById(pillId) : document.querySelector(`.src-pill[data-url="${clipUrl}"]`);
      switchSource(clipUrl, false, pill, 'clip');
      art.currentTime = 0;
      art.play();
    };

    // 5. Tabs Switching
    window.switchTab = function(tab) {
      currentTab = tab;
      document.getElementById('tabBtnChapters').classList.toggle('active', tab === 'chapters');
      document.getElementById('tabBtnTranscript').classList.toggle('active', tab === 'transcript');
      document.getElementById('tabBtnDanmaku').classList.toggle('active', tab === 'danmaku');

      document.getElementById('panelChapters').style.display = tab === 'chapters' ? 'block' : 'none';
      document.getElementById('panelTranscript').style.display = tab === 'transcript' ? 'block' : 'none';
      document.getElementById('panelDanmaku').style.display = tab === 'danmaku' ? 'block' : 'none';

      if (tab === 'transcript') {
        const activeLine = document.querySelector('.transcript-line.active-line');
        if (activeLine) {
          setTimeout(() => activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
        }
      } else if (tab === 'danmaku') {
        const activeDm = document.querySelector('.danmaku-line.active-line');
        if (activeDm) {
          setTimeout(() => activeDm.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
        }
      }
    };

    // 6. Timeupdate Follow-along
    art.on('video:timeupdate', () => {
      const t = art.currentTime;
      updatePlayhead(t);
      updateActiveChapter(t);
      updateActiveSubtitle(t);
      updateActiveDanmaku(t);
    });

    function updatePlayhead(t) {
      if (!durationSec) return;
      const pct = Math.min(1, Math.max(0, t / durationSec));
      const svg = document.getElementById('heatSvg');
      const rect = svg.getBoundingClientRect();
      const x = pct * rect.width;
      const playhead = document.getElementById('chartPlayhead');
      if (playhead) {
        playhead.setAttribute('x1', x);
        playhead.setAttribute('x2', x);
        playhead.style.display = 'block';
      }
    }

    function updateActiveChapter(t) {
      if (currentSource !== 'main') return;
      const cards = document.querySelectorAll('.chapter-card');
      cards.forEach(card => {
        const s = parseFloat(card.dataset.start);
        const e = parseFloat(card.dataset.end);
        if (t >= s && t <= e) {
          if (!card.classList.contains('active-chapter')) {
            cards.forEach(c => c.classList.remove('active-chapter'));
            card.classList.add('active-chapter');
          }
        }
      });
    }

    function updateActiveSubtitle(t) {
      if (currentSource !== 'main') return;
      const lines = document.querySelectorAll('.transcript-line');
      let target = null;
      for (let i = 0; i < lines.length; i++) {
        const s = parseFloat(lines[i].dataset.start);
        if (s <= t + 0.3) {
          target = lines[i];
        } else {
          break;
        }
      }

      if (target && !target.classList.contains('active-line')) {
        lines.forEach(l => l.classList.remove('active-line'));
        target.classList.add('active-line');
        if (currentTab === 'transcript') {
          target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }

    function updateActiveDanmaku(t) {
      if (currentSource !== 'main') return;
      const dmLines = document.querySelectorAll('.danmaku-line');
      if (!dmLines.length) return;
      let target = null;
      for (let i = 0; i < dmLines.length; i++) {
        const s = parseFloat(dmLines[i].dataset.start);
        if (s <= t + 0.3) {
          target = dmLines[i];
        } else {
          break;
        }
      }

      if (target && !target.classList.contains('active-line')) {
        dmLines.forEach(l => l.classList.remove('active-line'));
        target.classList.add('active-line');
        if (currentTab === 'danmaku') {
          target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }

    // 7. Render Heatmap SVG
    const chartBox = document.getElementById('chartBox');
    const chartTip = document.getElementById('chartTip');
    const svg = document.getElementById('heatSvg');

    function renderChart() {
      if (!curveData || curveData.length < 2) return;
      const rect = chartBox.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      // Keep only playhead
      const playhead = document.getElementById('chartPlayhead');
      svg.innerHTML = `
        <defs>
          <linearGradient id="heatGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4" />
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0" />
          </linearGradient>
        </defs>
      `;
      svg.appendChild(playhead);

      const maxCount = Math.max(...curveData.map(d => d.count), 1);
      const points = curveData.map((d, i) => {
        const x = (i / (curveData.length - 1)) * width;
        const y = height - (d.count / maxCount) * (height - 12) - 4;
        return { x, y, d };
      });

      // Area
      let areaD = `M 0 ${height} `;
      points.forEach(p => { areaD += `L ${p.x} ${p.y} `; });
      areaD += `L ${width} ${height} Z`;

      const area = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      area.setAttribute('d', areaD);
      area.setAttribute('fill', 'url(#heatGrad)');
      svg.appendChild(area);

      // Line
      let lineD = `M ${points[0].x} ${points[0].y} `;
      points.slice(1).forEach(p => { lineD += `L ${p.x} ${p.y} `; });
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      line.setAttribute('d', lineD);
      line.setAttribute('fill', 'none');
      line.setAttribute('stroke', '#38bdf8');
      line.setAttribute('stroke-width', '2');
      svg.appendChild(line);

      // Peaks
      points.forEach(p => {
        if (p.d.count > maxCount * 0.45) {
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', p.x);
          circle.setAttribute('cy', p.y);
          circle.setAttribute('r', '3.5');
          circle.setAttribute('fill', '#f43f5e');
          circle.setAttribute('stroke', '#fff');
          circle.setAttribute('stroke-width', '1.5');
          svg.appendChild(circle);
        }
      });
    }

    renderChart();
    window.addEventListener('resize', renderChart);

    // Click heatmap to seek
    chartBox.addEventListener('click', (e) => {
      const rect = chartBox.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const pct = Math.min(1, Math.max(0, mouseX / rect.width));
      const targetSec = pct * durationSec;
      jumpToTime(targetSec);
    });

    // Tooltip
    chartBox.addEventListener('mousemove', (e) => {
      const rect = chartBox.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const w = rect.width;
      const n = curveData.length;
      const idx = Math.min(n - 1, Math.max(0, Math.round((mouseX / w) * (n - 1))));
      const d = curveData[idx];

      if (d) {
        chartTip.style.display = 'block';
        chartTip.style.left = `${mouseX}px`;
        chartTip.style.top = `${e.clientY - rect.top}px`;
        let samplesHtml = d.samples && d.samples.length ? `<div style="color:#94a3b8;font-size:0.72rem;margin-top:4px;">${d.samples.slice(0, 2).join('<br>')}</div>` : '';
        chartTip.innerHTML = `<strong>${d.time_str}</strong> · ${d.count} 条互动 (${d.density}/s)${samplesHtml}`;
      }
    });

    chartBox.addEventListener('mouseleave', () => {
      chartTip.style.display = 'none';
    });

    // 8. Transcript Search Filter
    const searchInput = document.getElementById('searchInput');
    const transcriptList = document.getElementById('transcriptList');
    const lines = transcriptList.getElementsByClassName('transcript-line');

    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      for (let item of lines) {
        const text = item.innerText.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      }
    });

    // 9. Danmaku Search Filter
    const danmakuSearchInput = document.getElementById('danmakuSearchInput');
    const danmakuList = document.getElementById('danmakuList');
    if (danmakuSearchInput && danmakuList) {
      const dmLines = danmakuList.getElementsByClassName('danmaku-line');
      danmakuSearchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        for (let item of dmLines) {
          const text = item.innerText.toLowerCase();
          item.style.display = text.includes(q) ? 'flex' : 'none';
        }
      });
    }
  </script>
</body>
</html>
"""

def generate_report(data: Dict[str, Any], output_html_path: str):
    """
    Generates a full AI Studio HTML report with embedded player, clips, and subtitles.
    """
    output_dir = os.path.dirname(os.path.abspath(output_html_path))
    chapters = data.get("chapters", [])
    curve = data.get("danmaku_curve", [])
    segments = data.get("segments", [])
    peaks = data.get("peaks", [])
    duration_sec = data.get("duration_sec", 0.0)
    NOISE_TOKENS = {
        "(口误)", "（口误）", "(口誤)", "（口誤）",
        "(笑声)", "（笑声）", "(笑聲)", "（笑聲）",
        "(掌声)", "（掌声）", "(掌聲)", "（掌声）",
        "(咳)", "（咳）", "(咳嗽)", "（咳嗽）",
        "[music]", "[applause]", "[laughter]"
    }

    # Normalize to Simplified Chinese & filter out noise tokens
    clean_segments = []
    for s in segments:
        txt = to_simplified(s.get("text", "")).strip()
        if txt and txt not in NOISE_TOKENS:
            s["text"] = txt
            clean_segments.append(s)
    segments = clean_segments

    for ch in chapters:
        ch["title"] = to_simplified(ch.get("title", ""))
        ch["summary"] = to_simplified(ch.get("summary", ""))
        ch["key_points"] = [to_simplified(kp) for kp in ch.get("key_points", [])]
        ch["tags"] = [to_simplified(t) for t in ch.get("tags", [])]

    # 1. Detect Main Video & Subtitle paths
    title = data.get("title", "")
    video_file = data.get("video_file", "")
    
    # Prefer .mp4 over .flv for instant, zero-buffering browser native seeking
    cand_mp4 = os.path.join(output_dir, f"{title}.mp4")
    if os.path.exists(cand_mp4):
        video_file = os.path.basename(cand_mp4)
    elif not video_file or not os.path.exists(os.path.join(output_dir, video_file)):
        for ext in [".mp4", ".flv", ".ts", ".mkv"]:
            cand = os.path.join(output_dir, f"{title}{ext}")
            if os.path.exists(cand):
                video_file = os.path.basename(cand)
                break
    
    subtitle_file = data.get("subtitle_file", "")
    if not subtitle_file:
        cand_srt = os.path.join(output_dir, f"{data.get('title', '')}_whisper.srt")
        if os.path.exists(cand_srt):
            subtitle_file = os.path.basename(cand_srt)

    # 2. Discover Existing Highlight Clips in ./clips/
    clips_dir = os.path.join(output_dir, "clips")
    available_clips = []
    if os.path.exists(clips_dir):
        for f in sorted(os.listdir(clips_dir)):
            if f.endswith(".mp4"):
                available_clips.append({
                    "filename": f,
                    "rel_path": f"clips/{f}",
                    "name": f[:-4]
                })

    # Associate clips with chapters
    for ch in chapters:
        ch_id = ch.get("id")
        ch["clip"] = None
        for c in available_clips:
            if f"高光切片{ch_id}_" in c["filename"] or f"切片{ch_id}_" in c["filename"]:
                ch["clip"] = c
                break

    # 3. Format Source Pills HTML
    main_ext = os.path.splitext(video_file)[1].upper() if video_file else "FLV"
    source_pills = [
        f'<div class="src-pill active" id="src_pill_main" data-url="{video_file}" onclick="switchSource(\'{video_file}\', {str(video_file.endswith(".flv")).lower()}, this, \'main\')">🎥 完整录播原片 ({main_ext})</div>'
    ]
    for idx, c in enumerate(available_clips):
        pill_id = f"src_pill_clip_{idx}"
        c["pill_id"] = pill_id
        clean_name = re.sub(r"^高光切片\d+_[^_]+_", "", c["name"])
        source_pills.append(
            f'<div class="src-pill" id="{pill_id}" data-url="{c["rel_path"]}" onclick="switchSource(\'{c["rel_path"]}\', false, this, \'clip\')">🎬 切片 {idx+1}: {clean_name}</div>'
        )

    # 4. Format Chapter Cards HTML
    cards_html = []
    for ch in chapters:
        highlight_class = "highlight" if ch.get("is_highlight") else ""
        ch_peaks = ch.get("peaks", [])
        peak_badge = ""
        if ch_peaks:
            top_p = max(ch_peaks, key=lambda x: x.get("count", 0))
            peak_badge = f'<span class="peak-badge">🔥 观众反响高峰 ({top_p.get("count", 0)}条/30s)</span>'

        clip_badge = ""
        if ch.get("clip"):
            clip_rel = ch["clip"]["rel_path"]
            pill_id = ch["clip"].get("pill_id", "src_pill_clip_0")
            clip_badge = f'<span class="clip-badge-btn" onclick="event.stopPropagation(); playClip(\'{clip_rel}\', \'{pill_id}\')">🎬 播放切片 MP4</span>'

        key_points_html = "".join([f"<li>{kp}</li>" for kp in ch.get("key_points", [])])
        tags_html = "".join([f'<span class="tag-item">#{t}</span>' for t in ch.get("tags", [])])

        start_sec = ch.get("start_sec", 0.0)
        end_sec = ch.get("end_sec", 0.0)

        card = f"""
        <div class="chapter-card {highlight_class}" data-start="{start_sec}" data-end="{end_sec}">
          <div class="chapter-header">
            <div>
              <button class="jump-btn" onclick="jumpToTime({start_sec})">▶ {ch.get('start', '00:00:00')} - {ch.get('end', '00:00:00')}</button>
              <h3 class="chapter-title">{ch.get('title', '章节')}</h3>
            </div>
            <div class="card-badges">
              {peak_badge}
              {clip_badge}
            </div>
          </div>
          <p class="chapter-summary">{ch.get('summary', '')}</p>
          <ul class="key-points">{key_points_html}</ul>
          <div class="tags-list">{tags_html}</div>
        </div>
        """
        cards_html.append(card)

    # 5. Format Transcript Items HTML
    transcript_html = []
    for s in segments:
        s_start = s.get("start", s.get("start_sec", 0.0))
        s_end = s.get("end", s.get("end_sec", 0.0))
        transcript_html.append(f"""
        <div class="transcript-line" data-start="{s_start}" data-end="{s_end}" onclick="jumpToTime({s_start}, this)">
          <span class="ts-time">[{s.get('start_str', '00:00:00')}]</span>
          <span class="ts-text">{s.get('text', '')}</span>
        </div>
        """)

    # 6. Format Danmaku Items HTML
    danmaku_events = data.get("danmaku_events", [])
    if not danmaku_events:
        title = data.get("title", "")
        cand_ass = os.path.join(output_dir, f"{title}.ass")
        if not os.path.exists(cand_ass) and video_file:
            cand_ass = os.path.join(output_dir, f"{os.path.splitext(video_file)[0]}.ass")
        if os.path.exists(cand_ass):
            try:
                from danmaku import DanmakuAnalyzer
                da = DanmakuAnalyzer(cand_ass)
                danmaku_events = da.get_events_list()
            except Exception as e:
                print(f"[Reporter] Warning loading .ass events: {e}")

    danmaku_html = []
    for dm in danmaku_events:
        dm_start = dm.get("start", 0.0)
        dm_time = dm.get("start_str", "00:00:00")
        dm_user = to_simplified(dm.get("user", "")).strip()
        dm_content = to_simplified(dm.get("content", "")).strip()
        user_html = f'<span class="dm-user">{dm_user}:</span>' if dm_user else ''
        danmaku_html.append(f"""
        <div class="danmaku-line" data-start="{dm_start}" onclick="jumpToTime({dm_start}, this)">
          <span class="dm-time">[{dm_time}]</span>
          {user_html}
          <span class="dm-text">{dm_content}</span>
        </div>
        """)

    max_density = max([c["count"] for c in curve]) if curve else 0

    # 7. Assemble Full HTML using safe replacements
    html_content = HTML_TEMPLATE
    replacements = {
        "__STREAM_TITLE__": str(data.get("title", "直播录制")),
        "__DURATION_STR__": str(data.get("duration_str", "00:00:00")),
        "__DURATION_SEC__": str(duration_sec),
        "__TOTAL_DANMAKU__": str(len(danmaku_events) if danmaku_events else data.get("total_danmaku", 0)),
        "__TOTAL_CHAPTERS__": str(len(chapters)),
        "__TOTAL_SEGMENTS__": str(len(segments)),
        "__MAX_DENSITY__": str(max_density),
        "__MAIN_VIDEO_URL__": str(video_file),
        "__MAIN_SUBTITLE_URL__": str(subtitle_file),
        "__SOURCE_PILLS_HTML__": "\n".join(source_pills),
        "__CHAPTER_CARDS_HTML__": "\n".join(cards_html),
        "__TRANSCRIPT_ITEMS_HTML__": "\n".join(transcript_html),
        "__DANMAKU_ITEMS_HTML__": "\n".join(danmaku_html) if danmaku_html else '<div style="color:var(--text-muted);padding:1rem;text-align:center;">暂无弹幕记录</div>',
        "__CURVE_DATA_JSON__": json.dumps(curve, ensure_ascii=False),
        "__CHAPTERS_DATA_JSON__": json.dumps(chapters, ensure_ascii=False),
        "__PEAKS_DATA_JSON__": json.dumps(peaks, ensure_ascii=False)
    }

    for key, val in replacements.items():
        html_content = html_content.replace(key, val)

    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[Reporter] High-performance AI Studio report generated: {output_html_path}")
