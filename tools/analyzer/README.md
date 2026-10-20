# bililive-go 离线智能切片与重点归纳分析器 (Livestream Offline AI Analyzer)

基于本地轻量化 AI 体系（**whisper.cpp (Metal GPU加速)** + **Ollama (Qwen2.5)**）构建的无人值守直播录制后处理引擎。无需任何云端 API 费用，完全本地运行。

---

## 核心设计理念

1. **经济性 (Zero Cloud Cost)**：
   - 语音转写：`whisper.cpp` 本地模型（ggml-small.bin 465MB，高中文准确率）。
   - 文本归纳与章节打标：本地 Ollama `qwen2.5:3b`。
2. **性能与内存经济性 (Apple Silicon 原生加速)**：
   - 利用 Mac mini M4 的 Metal GPU 与 Unified Memory，40 分钟录播在 2-3 分钟内完成转写。
   - 峰值内存占用低于 1.5GB（Whisper ~800MB + Ollama Qwen ~1.9GB，串行执行）。
3. **稳定性与进程解耦 (Decoupled & Unattended)**：
   - 与 bililive-go 核心录制进程完全物理隔离，即便转写中断也不影响视频流拉取。
   - 录制关播后自动或手动对产生的 `.flv` 和 `.ass` 触发批处理。
4. **弹幕热度联动 (Danmaku Engagement Correlation)**：
   - 自动解析弹幕文件（`.ass`），计算 30 秒滑动窗口弹幕 TPS（每秒发送率）。
   - 智能识别观众情绪高潮、爆梗点、互动峰值（如“笑死”、“做切片”、“666”）。
   - 将弹幕峰值精准映射到 AI 划分的章节上，自动点亮 `🔥 重点高光片段`。

---

## 目录结构

```
tools/analyzer/
├── analyze.py           # 主执行入口 (CLI Master Pipeline)
├── clipper.py           # 高速无损切片器与字幕时间轴对齐裁剪
├── danmaku.py           # 弹幕解析与滑动窗口热度计算
├── audio.py             # FFmpeg 音频抽取 (16kHz mono WAV)
├── transcriber.py       # whisper.cpp Metal 转录封装
├── summarizer.py        # Ollama Qwen2.5 章节分段与结构化总结
├── reporter.py          # 交互式现代暗色 HTML 报告生成器
└── models/
    └── ggml-small.bin   # whisper ggml 中文识别模型
```

---

## 使用方法

### 1. 快速分析单场直播录像并自动切片

```bash
# 完整分析 + 自动无损导出高光片段与字幕
python3 tools/analyzer/analyze.py \
  --video "抖音/中国足球小将吴探/[2026-10-20 14-59-47][中国足球小将吴探][小将2018都跑哪里去了].flv" \
  --clip
```

> **提示**：同名目录下若存在同名 `.ass` 弹幕文件，程序将自动挂载分析；若无弹幕文件，则自动跳过弹幕统计只做音视频文本分析。

### 2. 产物输出

执行完毕后，在视频同级目录下自动生成：
- `*_report.html`：包含可缩放热度折线图、AI 章节卡片、高光片段、全文带时间戳检索的交互式仪表盘。
- `*_analysis.json`：包含机器可读的章节时间戳、标签、核心要点与弹幕统计。
- `*_whisper.json` / `*_whisper.srt`：标准字幕文件，可直接导入剪映/PR 进行切片剪辑。
- `clips/`：**自动导出的高光短视频切片**（`.mp4`，无损极速复制）及对应经过零点对齐的独立字幕（`.srt`）。
