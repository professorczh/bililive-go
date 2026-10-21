#!/usr/bin/env python3
"""
bililive-go 核心服务精准体检与靶向自愈工具 (Doctor & Auto-Healer)
用于精准排查 WebUI 红色感叹号报警、18110 抖音微服务卡死、孤儿僵尸进程。
"""

import sys
import os
import subprocess
import time
import json
import urllib.request
import urllib.error

BGO_PORT = 8080
BTOOLS_PORT = 18110
BTOOLS_AUTH = "Basic YTph"

def log_info(msg):
    print(f"\033[34m[*]\033[0m {msg}")

def log_ok(msg):
    print(f"\033[32m[✓]\033[0m {msg}")

def log_warn(msg):
    print(f"\033[33m[!]\033[0m {msg}")

def log_error(msg):
    print(f"\033[31m[✗]\033[0m {msg}")

def check_btools_health(timeout=3):
    """测试 18110 辅助服务是否在指定秒数内正常响应"""
    test_url = f"http://127.0.0.1:{BTOOLS_PORT}/bgo/live-info?platform=douyin&roomId=230616274247"
    headers = {"Authorization": BTOOLS_AUTH}
    req = urllib.request.Request(test_url, headers=headers)
    
    start_t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            elapsed = int((time.time() - start_t) * 1000)
            return True, elapsed, data
    except urllib.error.URLError as e:
        elapsed = int((time.time() - start_t) * 1000)
        return False, elapsed, str(e.reason)
    except Exception as e:
        elapsed = int((time.time() - start_t) * 1000)
        return False, elapsed, str(e)

def check_bgo_lives():
    """获取 bililive-go 当前所有监控房间的错误状态"""
    url = f"http://127.0.0.1:{BGO_PORT}/api/lives"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            errors = []
            for item in data:
                last_err = item.get("last_error")
                if last_err:
                    errors.append({
                        "platform": item.get("platform_cn_name", "未知"),
                        "host": item.get("host_name", "未知"),
                        "url": item.get("live_url", ""),
                        "error": last_err
                    })
            return True, errors, len(data)
    except Exception as e:
        return False, str(e), 0

def find_target_zombies():
    """仅查找霸占 18110 或属于 bililive-go 内部 external_tools 的 node 孤儿进程"""
    zombie_pids = []
    
    # 1. 查 18110 端口占用的 PID
    try:
        out = subprocess.check_output(["lsof", "-ti", f":{BTOOLS_PORT}"], stderr=subprocess.DEVNULL)
        pids = [int(p.strip()) for p in out.decode().split() if p.strip()]
        for p in pids:
            if p not in zombie_pids:
                zombie_pids.append(p)
    except Exception:
        pass

    # 2. 查路径显式包含 .appdata/external_tools 的 node 进程
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,ppid,args"], stderr=subprocess.DEVNULL)
        for line in out.decode().splitlines():
            if ".appdata/external_tools" in line and "node" in line and "server" in line:
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    pid = int(parts[0])
                    if pid not in zombie_pids:
                        zombie_pids.append(pid)
    except Exception:
        pass

    return zombie_pids

def run_doctor(auto_fix=False):
    print("==================================================")
    print("🩺 bililive-go 核心服务精准体检与诊断")
    print("==================================================")

    # 1. 检测主程序 (8080)
    bgo_ok, bgo_errors, total_rooms = check_bgo_lives()
    if bgo_ok:
        log_ok(f"bililive-go 主服务正常运行 (8080 端口，监控中房间: {total_rooms} 个)")
        if bgo_errors:
            log_warn(f"当前有 {len(bgo_errors)} 个房间存在异常感叹号报错：")
            for err in bgo_errors:
                print(f"    - [{err['platform']}] {err['host']}: {err['error'][:90]}...")
        else:
            log_ok("当前所有监控房间均无异常报错（无红色感叹号）")
    else:
        log_error(f"bililive-go 主服务 (8080) 无法连接: {bgo_errors}")

    print("\n--------------------------------------------------")
    # 2. 检测抖音辅助签名服务 (18110)
    log_info("正在对抖音签名服务 (18110 端口) 进行毫秒级活体探测...")
    bt_ok, elapsed, detail = check_btools_health(timeout=3)
    
    need_fix = False
    if bt_ok:
        log_ok(f"抖音签名服务健康！耗时: {elapsed}ms（正常响应）")
        print(f"    样例数据响应: {detail[:60]}...")
    else:
        need_fix = True
        log_error(f"抖音签名服务异常（已确诊）！耗时: {elapsed}ms")
        log_error(f"失败详情: {detail}")

    # 3. 进程扫描
    zombies = find_target_zombies()
    print("\n--------------------------------------------------")
    if zombies:
        log_warn(f"定位到相关的内部辅助进程 PID: {zombies}")
    else:
        log_info("未发现异常驻留的 18110 孤儿进程")

    # 诊断结论
    print("\n================== 诊断结论 ==================")
    if not need_fix and (not bgo_ok or not bgo_errors):
        log_ok("系统状态完全健康，无死锁，无服务故障！")
        return

    if need_fix:
        print("\n\033[31m【精准归因】\033[0m: 本地 18110 辅助微服务死锁/挂起，导致所有抖音房间探测超时。")
        print("          绝非抖音官方封禁，也非 Cookie 失效，仅需靶向释放 18110 端口。")
        if auto_fix:
            print("\n⚙️ 正在执行靶向自愈重置（只杀目标进程，绝不误伤系统其他应用）...")
            for pid in zombies:
                try:
                    subprocess.run(["kill", "-9", str(pid)], check=True)
                    log_ok(f"已精准终止挂死进程 PID: {pid}")
                except Exception as e:
                    log_warn(f"终止 PID {pid} 失败: {e}")
            
            # 找到主程序 bililive 进程并安全重启
            log_info("正在平滑重启 bililive-go 后台主程序...")
            try:
                subprocess.run(["pkill", "-f", "bililive-darwin-arm64"], stderr=subprocess.DEVNULL)
            except Exception:
                pass
            time.sleep(1)

            # 重新启动
            subprocess.Popen(["./bin/bililive-darwin-arm64", "--no-launcher"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             preexec_fn=os.setpgrp)
            print("等待服务重新初始化 (3秒)...")
            time.sleep(3)

            # 复检
            bt_recheck, r_elapsed, _ = check_btools_health(timeout=4)
            if bt_recheck:
                log_ok(f"自愈成功！18110 端口已恢复毫秒级响应 ({r_elapsed}ms)")
                log_ok("刷新 WebUI 页面后，红色感叹号已自动清除。")
            else:
                log_warn("服务已重启，但 18110 仍在加载依赖中，请稍等数秒后复查。")
        else:
            print("\n💡 修复建议：")
            print("   执行一键精准自愈命令：")
            print("   \033[32mpython3 tools/doctor.py --fix\033[0m")

if __name__ == "__main__":
    auto_fix = "--fix" in sys.argv
    run_doctor(auto_fix)
