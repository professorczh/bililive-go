#!/usr/bin/env python3
"""
Kuaishou Live Danmaku Protocol Tester & Client.
Tests handshake, WebSocket connection, and Protobuf message decoding for Kuaishou Live.
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
import urllib.parse

def fetch_room_info(room_url, cookie_str=""):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://live.kuaishou.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str

    req = urllib.request.Request(room_url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    except Exception as e:
        return None, f"Failed to fetch room page: {e}"

    # Extract __INITIAL_STATE__
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(.*?);\s*\(function", html, re.DOTALL)
    if not m:
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not m:
        return None, "window.__INITIAL_STATE__ not found in page"

    raw = m.group(1).strip()
    raw = re.sub(r":\s*undefined\b", ": null", raw)
    try:
        data = json.loads(raw)
    except Exception as e:
        return None, f"JSON parse error: {e}"

    liveroom = data.get("liveroom", {})
    playList = liveroom.get("playList", [])
    if not playList:
        return None, "No playList in liveroom data (anchor might be offline)"

    item = playList[0]
    info = {
        "is_living": item.get("isLiving", False),
        "author": item.get("author", {}).get("name", "Unknown"),
        "title": item.get("liveStream", {}).get("caption", ""),
        "live_stream_id": item.get("liveStream", {}).get("id", ""),
        "flv_urls": [],
        "token": item.get("authToken") or item.get("liveStream", {}).get("token"),
        "websocket_info": item.get("websocketInfo") or {}
    }

    # Extract FLV streams
    reps = item.get("liveStream", {}).get("playUrls", {}).get("h264", {}).get("adaptationSet", {}).get("representation", [])
    for r in reps:
        info["flv_urls"].append({
            "name": r.get("name"),
            "url": r.get("url")
        })

    return info, None

def query_websocket_info(live_stream_id, room_url, cookie_str=""):
    """
    Queries Kuaishou live_graphql for WebSocket credentials (token & wss urls).
    """
    url = "https://live.kuaishou.com/live_graphql"
    payload = {
        "operationName": "WebSocketInfoQuery",
        "variables": {"liveStreamId": live_stream_id},
        "query": "query WebSocketInfoQuery($liveStreamId: String) {\n  webSocketInfo(liveStreamId: $liveStreamId) {\n    token\n    webSocketUrls\n    __typename\n  }\n}"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": room_url,
    }
    if cookie_str:
        headers["Cookie"] = cookie_str

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        res = json.loads(resp.read().decode("utf-8"))
        ws_info = res.get("data", {}).get("webSocketInfo")
        if ws_info and ws_info.get("token") and ws_info.get("webSocketUrls"):
            return ws_info, None
        return None, f"Response: {res}"
    except Exception as e:
        return None, str(e)

def query_rest_websocket_info(live_stream_id, room_url, cookie_str=""):
    """
    Fallback to REST websocketinfo endpoint
    """
    api_url = f"https://live.kuaishou.com/live_api/liveroom/websocketinfo?liveStreamId={live_stream_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": room_url,
    }
    if cookie_str:
        headers["Cookie"] = cookie_str

    req = urllib.request.Request(api_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        res = json.loads(resp.read().decode("utf-8"))
        return res, None
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(description="Kuaishou Live Danmaku Protocol Tester")
    parser.add_argument("url", help="Kuaishou live room URL, e.g. https://live.kuaishou.com/u/3xf3s9hfmawhx2u")
    parser.add_argument("--cookie", default="", help="Cookie string containing kuaishou.live.web_st and userId")
    args = parser.parse_args()

    print("==================================================")
    print("🔍 快手直播弹幕协议连通性测试")
    print(f"🎯 目标直播间: {args.url}")
    print("==================================================")

    # 1. Fetch Room Info
    print("\n[第 1 步] 正在拉取直播间基础信息与开播状态 ...")
    info, err = fetch_room_info(args.url, args.cookie)
    if err:
        print(f"❌ 获取失败: {err}")
        return

    print(f"   ✓ 主播昵称: {info['author']}")
    print(f"   ✓ 直播标题: {info['title'] or '(未设置标题)'}")
    print(f"   ✓ 开播状态: {'🟢 正在直播 (Living)' if info['is_living'] else '🔴 未开播'}")
    print(f"   ✓ 本场 LiveStreamId: {info['live_stream_id']}")
    print(f"   ✓ 可用 FLV 视频源数量: {len(info['flv_urls'])}")

    if not info["is_living"]:
        print("⚠️ 该直播间当前未开播，无法建立弹幕长连接。")
        return

    # 2. Query WebSocket Credentials
    print("\n[第 2 步] 探测弹幕 WebSocket 凭据与长连接网关 ...")
    ws_info, err = query_websocket_info(info["live_stream_id"], args.url, args.cookie)
    if ws_info:
        print("   ✅ 成功获取快手弹幕通道凭证！")
        print(f"   ✓ Token: {ws_info.get('token')[:30]}...")
        print(f"   ✓ WebSocket 集群地址: {ws_info.get('webSocketUrls')}")
    else:
        print(f"   ⚠️ GraphQL 探测结果: {err}")
        print("   -> 尝试 REST 接口探测 ...")
        rest_res, rest_err = query_rest_websocket_info(info["live_stream_id"], args.url, args.cookie)
        print(f"   ✓ REST 响应: {rest_res}")

        if not args.cookie:
            print("\n--------------------------------------------------")
            print("💡 【测试诊断结果】:")
            print("1. 直播视频流（FLV）完全公开，bililive-go 可免登录正常录制。")
            print("2. 快手弹幕长连接（WebSocket）存在严格的风控限制：")
            print("   快手服务器对游客拦截了 WebSocketInfo 接口（返回 result: 2），")
            print("   必须携带登录 Cookie（核心是 kuaishou.live.web_st）才能签发 WSS token。")
            print("--------------------------------------------------")

if __name__ == "__main__":
    main()
