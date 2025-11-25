import os
import sys
import argparse
import subprocess
import time
import json
import requests

def rpc_call(host, port, method, params, secret):
    if not isinstance(params, list):
        params = []
    if secret:
        params = [f"token:{secret}"] + params
    payload = {"jsonrpc": "2.0", "id": method, "method": method, "params": params}
    url = f"http://{host}:{port}/jsonrpc"
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def check_rpc(host, port, secret, retries, wait):
    print(f"检查RPC: host={host} port={port} secret={'是' if secret else '否'}")
    print(f"请求: aria2.getVersion -> http://{host}:{port}/jsonrpc")
    tries = max(1, int(retries))
    for _ in range(tries):
        j = rpc_call(host, port, "aria2.getVersion", [], secret)
        if j and j.get("result"):
            res = j.get("result") or {}
            ver = res.get("version") or ""
            feats = ",".join(res.get("enabledFeatures") or [])
            print(f"检查结果: 已可用 version={ver} features={feats}")
            return True
        time.sleep(max(0.1, float(wait)))
    print("检查结果: 不可用")
    return False

def start_rpc(exe_path, port, listen_all, secret, max_concurrent, summary_interval, check_certificate, no_window):
    print("启动RPC服务")
    print(f"可执行: {exe_path}")
    print(f"监听: port={port} listen_all={'true' if listen_all else 'false'}")
    print(f"安全: secret={'已设置' if secret else '未设置'} check_certificate={'true' if check_certificate else 'false'}")
    print(f"并发: max_concurrent={max_concurrent} summary_interval={summary_interval}")
    cmd = [exe_path,
           "--enable-rpc=true",
           f"--rpc-listen-port={int(port)}",
           f"--rpc-listen-all={'true' if listen_all else 'false'}",
           f"--max-concurrent-downloads={int(max_concurrent)}",
           f"--summary-interval={int(summary_interval)}",
           f"--check-certificate={'true' if check_certificate else 'false'}"]
    if secret:
        cmd.append(f"--rpc-secret={secret}")
    creationflags = subprocess.CREATE_NO_WINDOW if no_window else 0
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", creationflags=creationflags)
    try:
        while True:
            line = p.stdout.readline()
            if line == "" and p.poll() is not None:
                break
            if line:
                print(line.rstrip())
    except KeyboardInterrupt:
        pass
    return p.wait()

def print_global_stat(host, port, secret):
    j = rpc_call(host, port, "aria2.getGlobalStat", [], secret)
    if j and j.get("result"):
        r = j.get("result")
        na = r.get("numActive")
        nw = r.get("numWaiting")
        ns = r.get("numStopped")
        nst = r.get("numStoppedTotal")
        ds = r.get("downloadSpeed")
        us = r.get("uploadSpeed")
        print(f"全局状态: active={na} waiting={nw} stopped={ns}/{nst} downSpeed={ds} upSpeed={us}")
        return True
    print("全局状态: 无法获取")
    return False

def ensure(host, port, secret, exe_path, listen_all, max_concurrent, summary_interval, check_certificate, no_window, retries, wait, startup_wait):
    print("链路: [检查] -> [启动] -> [等待] -> [检查]")
    ok = check_rpc(host, port, secret, 1, wait)
    if ok:
        print_global_stat(host, port, secret)
        return 0
    rc = start_rpc(exe_path, port, listen_all, secret, max_concurrent, summary_interval, check_certificate, no_window)
    time.sleep(max(0.1, float(startup_wait)))
    ok = check_rpc(host, port, secret, retries, wait)
    if ok:
        print_global_stat(host, port, secret)
    return 0 if ok else (rc if isinstance(rc, int) else 1)

def shutdown_rpc(host, port, secret, force):
    m = "aria2.forceShutdown" if force else "aria2.shutdown"
    print(f"关闭RPC: method={'forceShutdown' if force else 'shutdown'}")
    j = rpc_call(host, port, m, [], secret)
    if j and j.get("result"):
        print("关闭结果: 成功")
        return True
    print("关闭结果: 失败")
    return False

def kill_process_by_name(exe_name):
    try:
        print(f"进程结束: {exe_name}")
        r = subprocess.run(["taskkill", "/IM", exe_name, "/F"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        print(r.stdout.strip())
        return r.returncode == 0
    except Exception as e:
        print(str(e))
        return False

def main():
    ap = argparse.ArgumentParser(
        description="Aria2c RPC 启停与状态检查脚本",
        epilog="链路: start=仅启动; check=仅检查; ensure=检查→启动→等待→检查; stop=关闭RPC(可force/shutdown),失败可taskkill",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--action",
        choices=["start", "check", "ensure", "stop"],
        default="check",
        help="执行动作类型: start=仅启动RPC; check=仅检查RPC可用性; ensure=检查→启动→等待→再检查; stop=关闭RPC(可配合 --force 与 --kill_process)"
    )
    ap.add_argument("--exe", default=os.path.join(os.path.dirname(__file__), "aria2c.exe"), help="aria2c.exe 的绝对路径")
    ap.add_argument("--host", default="127.0.0.1", help="RPC 服务主机地址")
    ap.add_argument("--port", type=int, default=6800, help="RPC 服务监听端口")
    ap.add_argument("--secret", default="", help="RPC 密钥(提高安全性),脚本调用时会以 token 传递")
    ap.add_argument("--listen_all", type=int, default=0, help="是否监听所有地址 1=是 0=否")
    ap.add_argument("--max_concurrent", type=int, default=4, help="最大并发下载任务数量(aria2 全局配置)")
    ap.add_argument("--summary_interval", type=int, default=1, help="aria2 日志状态输出的时间间隔(秒)")
    ap.add_argument("--check_certificate", type=int, default=0, help="是否检查 SSL 证书 1=是 0=否")
    ap.add_argument("--no_window", type=int, default=0, help="Windows 下是否隐藏命令行窗口 1=隐藏 0=显示")
    ap.add_argument("--retries", type=int, default=3, help="检查 RPC 可用性的重试次数")
    ap.add_argument("--wait", type=float, default=1.0, help="两次检查 RPC 之间的等待秒数")
    ap.add_argument("--startup_wait", type=float, default=1.0, help="启动 RPC 后等待多少秒再进行检查")
    ap.add_argument("--force", type=int, default=0, help="关闭 RPC 时是否使用 forceShutdown 1=是 0=否")
    ap.add_argument("--kill_process", type=int, default=0, help="关闭失败时是否尝试 taskkill 进程 1=是 0=否")
    args = ap.parse_args()
    if args.action == "check":
        ok = check_rpc(args.host, args.port, args.secret, args.retries, args.wait)
        sys.exit(0 if ok else 1)
    if args.action == "ensure":
        rc = ensure(args.host, args.port, args.secret, args.exe, bool(args.listen_all), args.max_concurrent, args.summary_interval, bool(args.check_certificate), bool(args.no_window), args.retries, args.wait, args.startup_wait)
        sys.exit(rc)
    if args.action == "stop":
        ok = shutdown_rpc(args.host, args.port, args.secret, bool(args.force))
        if not ok and bool(args.kill_process):
            name = os.path.basename(args.exe) if args.exe else "aria2c.exe"
            ok = kill_process_by_name(name)
        sys.exit(0 if ok else 1)
    rc = start_rpc(args.exe, args.port, bool(args.listen_all), args.secret, args.max_concurrent, args.summary_interval, bool(args.check_certificate), bool(args.no_window))
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()

