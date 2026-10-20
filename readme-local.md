# 本地开发启动指南

本文档介绍如何在本地通过命令行启动 bililive-go 项目。

## 前置要求

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| [Go](https://golang.org/dl/) | 1.25+ | 后端开发语言 |
| [GNU Make](https://www.gnu.org/software/make/) | 4.0+ | 构建工具 |
| [Node.js](https://nodejs.org/) | 18+ | 前端构建（可选） |
| [FFmpeg](https://ffmpeg.org/) | - | 视频处理（程序会自动下载） |

## 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/bililive-go/bililive-go.git
cd bililive-go
```

### 2. 安装开发工具

```bash
go generate ./tools/devtools.go
```

### 3. 构建并运行

#### 方式一：仅构建后端（推荐快速开发）

```bash
# 开发版构建
make dev

# 运行（使用默认配置文件 config.yml）
./bin/bililive-dev

# 或指定配置文件
./bin/bililive-dev -c /path/to/your/config.yml
```

#### 方式二：构建前端 + 后端（完整功能）

```bash
# 安装前端依赖
cd src/webapp && npm install && cd ../..

# 构建前端
make build-web

# 构建后端
make dev

# 运行
./bin/bililive-dev
```

## 常用启动命令

### 使用命令行参数直接运行（无需配置文件）

```bash
# 基础录制模式（无 Web 界面）
./bin/bililive-dev -i "https://live.bilibili.com/22603245"

# 指定输出目录
./bin/bililive-dev -i "https://live.bilibili.com/22603245" -o /path/to/output

# 开启调试模式
./bin/bililive-dev -i "https://live.bilibili.com/22603245" --debug

# 指定查询间隔（秒）
./bin/bililive-dev -i "https://live.bilibili.com/22603245" -t 30

# 启用 Web 界面（RPC 模式）
./bin/bililive-dev --enable-rpc --rpc-bind :8080
```

### 使用配置文件运行

```bash
# 默认读取当前目录下的 config.yml
./bin/bililive-dev

# 指定配置文件路径
./bin/bililive-dev -c /path/to/config.yml
```

### 跳过 Launcher 版本检查（开发调试用）

```bash
./bin/bililive-dev --no-launcher
```

## 其他构建命令

```bash
# 发布版构建
make build

# 增量编译（仅重新编译变更部分）
make dev-incremental

# 运行测试
make test

# 代码检查
make lint

# 清理构建产物
make clean
```

## 配置文件说明

项目根目录下的 `config.yml` 是主配置文件。关键配置项：

- `rpc.enable`: 是否启用 Web 界面（默认 true）
- `rpc.bind`: Web 界面绑定地址（默认 :8080）
- `out_put_path`: 录制文件输出目录
- `live_rooms`: 要监听的直播间列表
- `ffmpeg_path`: FFmpeg 路径（留空自动检测）

完整配置说明请参考项目 Wiki。

## 访问 Web 界面

启动后，如果启用了 RPC，访问：

```
http://localhost:8080
```

## 常见问题

### 1. 找不到 FFmpeg

程序会自动下载 FFmpeg。如需手动指定：

```bash
./bin/bililive-dev --ffmpeg-path /usr/local/bin/ffmpeg
```

或在 `config.yml` 中设置：

```yaml
ffmpeg_path: /usr/local/bin/ffmpeg
```

### 2. 端口被占用

修改 RPC 绑定端口：

```bash
./bin/bililive-dev --rpc-bind :8081
```

### 3. 开发时跳过版本检查

使用 `--no-launcher` 参数跳过自动更新检查：

```bash
./bin/bililive-dev --no-launcher
```

---

## 本地调试记录（2026-10-03）

本节记录本次本地搭建过程中实际遇到的问题与解决方案，供后续参考。

### 本次环境

- macOS arm64（Apple Silicon）
- Go 1.27.1（通过 `brew install go` 安装）
- Node v26 + npm 11 + yarn（`make build-web` 依赖 yarn）

### 启动方式（本机实际可用）

```bash
# 1. 编译
cd /Users/maphi-macminim4/DEV/00_Tools/07_bililive-go/bililive-go
make dev

# 2. 把配置复制到 bin/（程序读取"可执行文件所在目录"的 config.yml）
cp config.yml bin/

# 3. 启动（必须 --no-launcher，原因见下文）
./bin/bililive-darwin-arm64 --no-launcher
```

Web 界面：http://localhost:8080

停止服务：

```bash
pkill -f "bililive-darwin-arm64"
```

### 踩坑与排查记录

#### 坑 1：`ERR_ABORTED` 打不开 Web 界面

**现象**：后端返回 200 但浏览器打不开页面。

**原因**：只编译了后端，**前端没构建**（`src/webapp/build/` 不存在）。服务器能响应但没有静态资源。

**解决**：

```bash
cd src/webapp && npm install
# make build-web 内部调用 yarn；如果 yarn 报错可绕过类型检查：
TSC_COMPILE_ON_ERROR=true npm run build
```

注：当前前端代码有 TypeScript 类型错误（`DiskIOChart.tsx` / `MemoryChart.tsx` 的 Recharts props 类型），是上游代码问题，不影响功能，用 `TSC_COMPILE_ON_ERROR=true` 跳过即可。

#### 坑 2：程序启动几分钟后自动退出

**现象**：服务跑了几分钟突然挂掉，端口不再监听。

**原因**：**自动更新**。日志中可见：

```
发现新版本: v0.8.3 → 开始自动下载更新 → 进入 Launcher 模式 → Launcher 检查未通过，程序即将退出
```

开发版二进制（dev build）触发自更新后，Launcher 状态文件路径错乱导致进程退出。

**解决**：编辑 `bin/config.yml` 关闭自动更新（注意是 bin/ 下那份）：

```yaml
update:
  auto_check: false
  auto_download: false
```

并始终用 `--no-launcher` 启动。

#### 坑 3：快手直播间"获取失败"

**现象**：添加 `https://live.kuaishou.com/u/xxx` 后主播名显示"获取失败"，但浏览器里页面正常。

**排查思路**（适用于所有平台）：

```bash
# 1. 模拟程序请求，抓取页面
curl -s -L -A "Mozilla/5.0 ... Chrome/120.0.0.0 ..." "https://live.kuaishou.com/u/xxx" -o /tmp/page.html

# 2. 提取并解析页面里的 __INITIAL_STATE__ 数据
grep -o 'window\.__INITIAL_STATE__ *= *.*' /tmp/page.html | head -c 2000
```

发现两层问题：

1. **反爬虫**：不带 Cookie 的请求被限流，返回 `errorType: {title: "请求过快，请稍后重试"}`，页面降级。
   - 解决：从浏览器导出快手 Cookie（Netscape 格式），转换为 HTTP Cookie 串（`name=value; name2=value2`），填入 `bin/config.yml`：
     ```yaml
     cookies:
       live.kuaishou.com: "did=xxx; clientid=3; ..."
     ```
2. **API 数据结构变更（上游 bug）**：带 Cookie 后数据正常了，但代码里取数路径过时。
   - 实际结构：`liveroom.playList[0].author.name`、`liveroom.playList[0].liveStream.playUrls.h264.adaptationSet.representation[0].url`
   - 旧代码路径：`liveroom.author.name`、`...playUrls.0.adaptationSet...`（playUrls 已从数组变成 `{h264, hevc}` 字典）
   - 已本地修复 `src/live/kuaishou/kuaishou.go`（`GetInfo` 和 `GetStreamUrls` 两处）

#### 坑 4：卡在"录制准备中"

**现象**：Web 界面显示"录制准备中"，日志反复 `failed to get stream url, will retry in Xs...`。

**原因**：同坑 3 的第 2 点 —— `GetStreamUrls` 的 gjson 路径取不到流地址。

**排查**：日志里 `Record Start` 之后如果一直 `failed to get stream url`，基本就是流地址解析失败，回到坑 3 的排查步骤验证数据结构。

### 后续维护提醒

1. **`git pull` 会丢失快手修复**：`kuaishou.go` 是本地补丁（已提交在分支 `fix/kuaishou-playlist-path`，推送到 fork `professorczh/bililive-go`），拉上游代码前记得 `git stash` 或备份。已于 2026-10-04 向上游提交 PR #1214：https://github.com/bililive-go/bililive-go/pull/1214 ，合并后即可删除本地补丁。
2. **Cookie 会过期**：
   - `kwssectoken` / `kwscode`：当天过期（短期 token）
   - `kuaishou.live.web_st` / `web_ph`：约 1 个月
   - 哪天快手突然又"获取失败"，**第一件事是换 Cookie**（浏览器 F12 → Application → Cookies 导出）
3. **平台失效通用排查顺序**：
   1. 看日志（`bililive-go-YYYY-MM-DD.log`）确认错误信息
   2. curl 带 Cookie 抓页面，确认数据结构是否变化
   3. 对比 `src/live/<platform>/<platform>.go` 里的 gjson 路径是否匹配
4. **配置文件位置**：程序读取的是**可执行文件同目录**的 `config.yml`（即 `bin/config.yml`），不是项目根目录那份，改配置别改错地方。

---

## 核心能力升级与扩展功能说明（2026-10）

本次本地大版本升级为 bililive-go 注入了三大核心系统：**离线 AI 智能切片分析流水线**、**多平台弹幕录制引擎** 与 **Cookie 在线安全测试校验系统**。

### 一、离线 AI 智能切片与全维直播分析系统 (`tools/analyzer/`)

系统位于 `tools/analyzer/` 目录下，采用完全本地化、离线推理设计，不依赖任何外部付费云服务与 API Key。

#### 1. 处理流水线架构

```
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  录制完成原始流   │ ──> │ FFmpeg 音轨极速提取  │ ──> │ Native Whisper 转录  │
│ (.flv / .mp4)    │     │ 16kHz Mono WAV (快速) │     │ 毫秒对齐 / 繁简转换  │
└──────────────────┘     └──────────────────────┘     └──────────────────────┘
         │                                                        │
         ├──────────────────────┐                                 ▼
         ▼                      ▼                     ┌──────────────────────┐
┌──────────────────┐   ┌──────────────────────┐       │ 本地 Ollama (Qwen)   │
│ Faststart 快速混 │   │ 弹幕热度高潮检测     │       │ 章节划分 / 核心提炼  │
│ 转 (零延迟跳转)  │   │ 滑动窗口计算峰值     │       └──────────────────────┘
└──────────────────┘   └──────────────────────┘                   │
         │                      │                                 │
         ▼                      ▼                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    多维交互式 HTML 分析报告 (reporter.py)                   │
│   • 弹幕热力图  • 智能章节索引  • 全文实时字幕搜索  • 播放器秒级联动跳转    │
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼ (启用 --clip 时)
                       ┌──────────────────────────────────┐
                       │ 自动智能切片机 (clipper.py)       │
                       │ 截取高潮区间压制独立 MP4 短视频   │
                       └──────────────────────────────────┘
```

#### 2. 核心模块一览

* **`analyze.py`**：全流程总控调度器。支持 `--video`、`--danmaku`、`--model`、`--clip`、`--output-dir` 参数。
* **`audio.py`**：调用本地 FFmpeg 极速分离音轨并重采样至 Whisper 专用的 16kHz 单声道 WAV。
* **`transcriber.py`**：原生封装 `whisper.cpp` / GGML 模型，支持 Apple Silicon CPU/GPU 多线程并发加速，毫秒级逐句对齐；内置无效语气词与噪音标牌（如 `(掌声)`、`(咳)`、`[music]` 等）净化过滤，并集成 OpenCC 转换为规范简体中文。
* **`danmaku.py`**：解析录制阶段生成的 `.ass` 弹幕文件，以 60 秒为滑动窗口统计弹幕发送速率（条/分钟），自动识别出弹幕热度前 N 的高潮区间，并提取弹幕高频词热云。
* **`summarizer.py`**：通过本地 Ollama 驱动 `qwen2.5:3b`，针对字幕切片进行结构化摘要生成，提取每个章节的主题、内容梗概、关键讨论要点与标签。
* **`reporter.py`**：输出独立自包含的现代暗黑风 HTML 分析报告。报告内置纯原生 CSS/JS 播放引擎，支持点击任何章节、高潮时间段或字幕句子秒级定位播放。
* **`clipper.py`**：依据弹幕热度峰值与 LLM 识别的高能区，自动使用 FFmpeg 无损/高质量切片压制出独立的片段短视频，统一存放于录像目录下的 `clips/` 文件夹中。

#### 3. 自动化录制后触发配置

在 `bin/config.yml` 中配置 `on_record_finished` 即可实现录制结束后自动分析与切片：

```yaml
on_record_finished:
  custom_commandline: python3 tools/analyzer/analyze.py --video "{{ .FileName }}" --clip
```

---

### 二、多平台弹幕录制引擎（抖音 & 快手）

1. **抖音弹幕录制 (`src/recorders/danmaku/douyin/`)**：
   - 升级完整的 Protobuf 解码协议与数据结构（`dy.proto`, `dy.pb.go`）。
   - 实现全双工 WebSocket 长链接弹幕监听，包含每 10 秒的心跳保活包与断线重连机制。
   - 随同视频录制全量录制弹幕并实时渲染生成时序对齐的标准 `.ass` 字幕。

2. **快手直播源与弹幕探针**：
   - 修复官方 Web 端 `liveroom.playList` API 结构变更导致的直播流解析失败问题（PR #1214）。
   - 补充专用快手 Web 弹幕客户端脚本 `tools/analyzer/ks_danmaku_client.py`，支持独立探测并抓取直播间实时消息流。

---

### 三、WebUI Cookie 在线安全测试与校验系统

针对各大平台 Cookie 有效期较短、过期后导致录制静默降级或弹幕断流的问题，开发了开箱即用的实时探针与前端交互。

#### 1. 前后端探针逻辑

* **后端校验接口**：`POST /api/cookies/verify`，入参 `{ "Host": "...", "Cookie": "..." }`。
* **各平台在线活体探测机制**：
  * **快手**：检验关键安全凭据 `kuaishou.live.web_st`，实时请求快手服务端解析 `ownerInfo`，成功后提取当前登录用户名与 UID（例如：`广源大厦陈先生 (UID: 385284051)`）。
  * **抖音**：检验会话令牌 `sessionid`，通过向 `/aweme/v1/web/notice/count/` 真实发包判定会话是否存活（`status_code == 0` 为有效，`8` 为未登录/失效）。
  * **微博直播**：检验双核心安全凭据 `SUB` 与 `SUBP`（新浪通行证统一 SSO 会话），向微博服务端请求验证并解析 `$CONFIG` 上下文中的用户昵称与 UID（例如：`Professor_Chan (UID: 1868641703)`）。
  * **哔哩哔哩**：请求 B 站 `/x/web-interface/nav` 接口读取登录态及 `uname`、`mid`。
  * **斗鱼**：校验 `acf_auth` / `acf_uid` 令牌有效性。

#### 2. 前端界面新增功能

* **Cookie 列表操作栏测试盾牌**：
  在 WebUI 的 **【Cookie管理】** 列表中，蓝色编辑按钮（✏️）右侧新增绿色圆形测试按钮（`<SafetyCertificateOutlined />`）。点击后呈现转圈防抖状态，并弹出 Ant Design 全局通知反馈测试详情（成功显示账号昵称与 UID，失败提示明确原因）。
* **已配置平台兜底展示**：
  增强了 WebUI Cookie 列表拉取逻辑，只要在 `config.yml` 中配置过的平台（如快手、抖音、微博等），即使当前未添加该平台的直播间，也会持久显示在 Cookie 管理表格中，便于随时维护与一键验证。
* **编辑弹窗内「测试当前输入」**：
  在 Cookie 修改弹窗中，新增“测试当前输入”按钮。从浏览器复制新 Cookie 粘贴后，无需先保存即可直接点击测试，确认校验通过后再保存入盘。

#### 3. 关于 Cookie 容错与“核心会话令牌”的说明

Cookie 在 HTTP 协议中是一组分号分隔的键值对。几千字节的内容中，绝大部分（如 `did`, `odin_tt`, `theme`, `volume_info`, `_s_tentry` 等）只是设备指纹或前端界面状态，**真正决定登录有效性的只有核心令牌**：
* 抖音的核心只有 **`sessionid`**；
* 快手的核心只有 **`kuaishou.live.web_st`**；
* 微博的核心是 **`SUB`**（身份凭证）与 **`SUBP`**（单点登录跨域校验，二者必须成对存在）；
* B 站的核心只有 **`SESSDATA`**。

只要核心令牌正确无损，修改或冗余其他次要键值通常不会使服务端报错；而只要核心令牌改动一个字符或过期，系统即可秒级阻断并提示错误。

---

### 四、微博直播与付费回放录制适配

#### 1. 核心改进点 (`src/live/weibolive/weibolive.go`)
1. **多格式房间 ID 自动正则提取**：
   支持形如 `https://weibo.com/l/wblive/p/show/1022:2321325354984119599338`、`1042152:...` 及常见短链，精准提取冒号复合 ID。
2. **Cookie 请求透传**：
   在向 `https://weibo.com/l/!/2/wblive/room/show_pc_live.json` 请求直播间状态时，注入全局配置的微博 Cookie。
3. **实时直播与付费回放双模支持**：
   - 官方原生逻辑仅在 `data.status == 1` 时判定为开播，一旦直播结束（`status == 3`）即判定为下线。
   - 改进后：兼容 `status == 1`（实时直播）与 `status == 3`（已结束转为回放），若检测到存在可录制流地址，则标记为可录制状态。
4. **多级码率流地址级联降级**：
   流地址提取顺序：`live_origin_flv_url` -> `live_origin_hls_url` -> `replay_origin_url`，确保回放流（HLS M3U8）能被流畅录制。

#### 2. 付费直播鉴权机制分析
- 微博 Web 端针对付费直播的“60秒试看拦截”，实质是在前端通过 JavaScript 计时器展示遮罩弹窗（`pay_dialog_info`）；
- 底层的回放/直播 CDN 流地址（如 `http://live.video.weibocdn.com/..._index.m3u8`）由阿里云/新浪 CDN 托管，分片未进行 DRM 加密。
- 在 bililive-go 中注入购买过权限的用户 Cookie（含 `SUB` + `SUBP`）后，微博服务端 API 返回 `"pay_live_status": 1` 并直接下发完整 1080P 60fps 高清原画源地址，录制器可不受任何阻碍地完整下载整场视频。

---

### 五、本地构建与更新工作流

```bash
# 1. 编译前端（每次修改 src/webapp 后执行）
cd src/webapp && yarn build && cd ../..

# 2. 编译后端（嵌入前端静态资源）
go run build.go release --platform darwin --arch arm64

# 3. 运行最新二进制（必须带 --no-launcher 防止触发自更新退出）
./bin/bililive-darwin-arm64 --no-launcher
```

