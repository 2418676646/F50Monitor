#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import shutil

# Terminal color tokens
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"
BOLD = "\033[1m"

MODULE_ZIP = "f50_monitor_magisk.zip"
TEMP_DIR = "build_temp"

MODULE_PROP = """id=f50_monitor
name=ZTE F50 状态监控接口
version=v1.0.0
versionCode=100
author=Bear
description=在本地 55050 端口开放状态监控接口，实时读取精准温度与网速。配套 Mac 状态栏前端使用。
"""

CUSTOMIZE_SH = """#!/system/bin/sh
SKIPUNZIP=0
ui_print "****************************************"
ui_print "*      ZTE F50 Monitor Installer       *"
ui_print "****************************************"
ui_print "- 正在配置系统级监控程序可执行权限..."
chmod 755 "$MODPATH/f50_monitor"
ui_print "- Magisk 系统服务部署成功！"
"""

SERVICE_SH = """#!/system/bin/sh
MODDIR=${0%/*}

# 等待系统开机完成
until [ "$(getprop sys.boot_completed)" = "1" ]; do
  sleep 3
done
sleep 2

# 无限重启自愈守护循环
while true; do
  mkdir -p /data/f50_monitor
  echo "[守护进程] 开始启动监控原生服务..." >> /data/f50_monitor/run_log.txt
  "$MODDIR/f50_monitor" >> /data/f50_monitor/run_log.txt 2>&1
  echo "[守护进程] 监控服务意外退出，将在 5 秒后自动拉起重启..." >> /data/f50_monitor/run_log.txt
  sleep 5
done
"""

UNINSTALL_SH = """#!/system/bin/sh
rm -rf /data/f50_monitor
"""

def get_adb_path():
    paths = ["/opt/homebrew/bin/adb", "/usr/local/bin/adb", os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"), "adb"]
    for p in paths:
        try:
            subprocess.run([p, "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return p
        except Exception:
            pass
    return "adb"

ADB = get_adb_path()

def check_adb():
    """Check connected ADB devices."""
    try:
        res = subprocess.run([ADB, "devices"], capture_output=True, text=True)
        lines = res.stdout.strip().split("\n")[1:]
        devices = [line.split()[0] for line in lines if "device" in line]
        return devices
    except FileNotFoundError:
        return []

def run_adb_shell(cmd, use_su=False):
    """Run an ADB shell command."""
    full_cmd = [ADB, "shell"]
    if use_su:
        full_cmd.append(f"su -c '{cmd}'")
    else:
        full_cmd.append(cmd)
    
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def get_bot_status():
    """Check if the Monitor is running on F50."""
    code, out, _ = run_adb_shell("pgrep -f f50_monitor")
    if code == 0 and out.strip():
        return f"{GREEN}● 正在运行 (原生系统守护已生效){RESET}"
    return f"{RED}○ 已停止{RESET}"

def build_magisk_zip():
    """Compiles the Go daemon and packages the Magisk Module ZIP."""
    print(f"\n{CYAN}=== 正在交叉编译并构建 Magisk 状态监控模块... ==={RESET}")
    
    try:
        subprocess.run(["go", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"{RED}[错误] 您的 Mac 未安装 Go 编译器！请先执行 brew install go 或安装 Golang。{RESET}")
        return False

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    if os.path.exists(MODULE_ZIP):
        os.remove(MODULE_ZIP)
    os.makedirs(TEMP_DIR)

    print(f"{BLUE}[1/4] 正在对 Go 源码进行 android/arm64 交叉编译...{RESET}")
    env = os.environ.copy()
    env["GOOS"] = "linux"
    env["GOARCH"] = "arm64"
    compile_cmd_bot = ["go", "build", "-ldflags=-s -w", "-o", f"{TEMP_DIR}/f50_monitor", "main.go"]
    try:
        subprocess.run(compile_cmd_bot, env=env, check=True)
        print(f"{GREEN}✔︎ Go 核心程序交叉编译成功！ ELF 文件已生成。{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[错误] Go 编译失败: {e}{RESET}")
        return False

    print(f"{BLUE}[2/4] 正在写入 Magisk 系统挂载与自启脚本...{RESET}")
    with open(f"{TEMP_DIR}/module.prop", "w", encoding="utf-8") as f:
        f.write(MODULE_PROP)
    with open(f"{TEMP_DIR}/customize.sh", "w", encoding="utf-8") as f:
        f.write(CUSTOMIZE_SH)
    with open(f"{TEMP_DIR}/service.sh", "w", encoding="utf-8") as f:
        f.write(SERVICE_SH)
    with open(f"{TEMP_DIR}/uninstall.sh", "w", encoding="utf-8") as f:
        f.write(UNINSTALL_SH)
    print(f"{GREEN}✔︎ 脚本注入就绪！{RESET}")

    print(f"{BLUE}[3/4] 正在打包 Magisk 系统刷入包 {MODULE_ZIP}...{RESET}")
    try:
        shutil.make_archive("f50_monitor_magisk", 'zip', TEMP_DIR)
        shutil.rmtree(TEMP_DIR)
        print(f"{GREEN}✔︎ 模块打包成功！{RESET}")
        return True
    except Exception as e:
        print(f"{RED}[错误] 打包失败: {e}{RESET}")
        return False

def wait_for_root():
    """Wait for Superuser permission."""
    print(f"\n{YELLOW}[安全引导] 正在请求 F50 终端 Root 命令行授权...{RESET}")
    print(f"{YELLOW}重要提示: 请看您的 scrcpy 投屏窗口，并在手机弹窗上点击“允许 (GRANT)”！{RESET}")
    while True:
        code, out, _ = run_adb_shell("su -c 'whoami'")
        if code == 0 and "root" in out.strip():
            print(f"{GREEN}✔︎ ADB Root 命令行授权成功！{RESET}\n")
            return True
        print(f"{YELLOW}⏳ 正等待 Root 权限授予，请在投屏中确认允许...{RESET}")
        time.sleep(2.5)

def one_click_install():
    """Pack, flash and reboot F50."""
    devices = check_adb()
    if not devices:
        print(f"{RED}[错误] 未检测到任何已连接的 ADB 设备！请先运行 adb connect 192.168.0.1:5555{RESET}")
        return
    
    if not build_magisk_zip():
        return
        
    if not wait_for_root():
        return
        
    print(f"{BLUE}[1/3] 正在推送模块安装包...{RESET}")
    subprocess.run([ADB, "push", MODULE_ZIP, "/data/local/tmp/"])

    print(f"{BLUE}[2/3] 正在通过 Magisk 安装服务进行系统层注入...{RESET}")
    code, out, err = run_adb_shell(f"magisk --install-module /data/local/tmp/{MODULE_ZIP}", use_su=True)
    if code != 0:
        print(f"{RED}[错误] 模块刷入失败！报错信息如下：\n{out}\n{err}{RESET}")
        return
    print(f"{GREEN}✔︎ 模块成功刷入 Magisk 引擎！{RESET}")
    
    run_adb_shell(f"rm -f /data/local/tmp/{MODULE_ZIP}", use_su=True)

    print(f"\n{GREEN}{BOLD}🎉 恭喜您！状态栏监控 Magisk 系统模块刷入圆满成功！{RESET}")
    print(f"{CYAN}中兴 F50 即将在 3 秒后自动重启激活监控服务...{RESET}")
    time.sleep(3)
    run_adb_shell("reboot", use_su=True)
    print(f"{GREEN}🚀 设备已发送重启命令！请等待开机。{RESET}")

def manage_service(action):
    devices = check_adb()
    if not devices:
        print(f"{RED}[错误] 未检测到任何已连接的 ADB 设备！{RESET}")
        return

    if action == "restart":
        print(f"\n{BLUE}正在热重启 F50 端监控服务守护...{RESET}")
        run_adb_shell("pkill -f f50_monitor", use_su=True)
        print(f"{GREEN}✔︎ 热重启指令发送，助手将在 5 秒内静默完成重载。{RESET}")
    elif action == "stop":
        print(f"\n{BLUE}正在强行停止 F50 端的监控守护...{RESET}")
        run_adb_shell("pkill -f service.sh", use_su=True)
        run_adb_shell("pkill -f f50_monitor", use_su=True)
        print(f"{GREEN}✔︎ 服务与自启守护进程已被完全强制终结！{RESET}")
    elif action == "start":
        print(f"\n{BLUE}正在手动拉起 F50 端监控服务与自启守护...{RESET}")
        run_adb_shell("nohup /data/adb/modules/f50_monitor/service.sh >/dev/null 2>&1 &", use_su=True)
        print(f"{GREEN}✔︎ 自启守护已拉起，服务正在初始化上线。{RESET}")

def view_logs():
    devices = check_adb()
    if not devices:
        print(f"{RED}[错误] 未检测到任何已连接的 ADB 设备！{RESET}")
        return
        
    print(f"\n{BLUE}=== 正在拉取中兴 F50 监控服务实时运行日志 (Tail 35) ==={RESET}\n")
    code, out, _ = run_adb_shell("tail -n 35 /data/f50_monitor/run_log.txt")
    if code == 0 and out.strip():
        print(out)
    else:
        print(f"{YELLOW}[信息] 未找到有效的运行日志，或者日志内容当前为空。{RESET}")

def one_click_uninstall():
    devices = check_adb()
    if not devices:
        print(f"{RED}[错误] 未检测到任何已连接的 ADB 设备！{RESET}")
        return

    confirm = input(f"\n{RED}{BOLD}⚠️ 物理擦除警告：您确定要彻底卸载该模块，物理抹除一切进程与数据吗？(y/n): {RESET}")
    if confirm.lower() != 'y':
        print(f"{YELLOW}操作已取消。{RESET}")
        return

    print(f"\n{BLUE}[1/2] 正在强行停止并杀死所有相关的服务进程与守护...{RESET}")
    run_adb_shell("pkill -f service.sh", use_su=True)
    run_adb_shell("pkill -f f50_monitor", use_su=True)

    print(f"{BLUE}[2/2] 正在彻底擦除系统底层挂载与持久化数据...{RESET}")
    run_adb_shell("rm -rf /data/adb/modules/f50_monitor", use_su=True)
    run_adb_shell("rm -rf /data/f50_monitor", use_su=True)
    run_adb_shell("rm -f /data/local/tmp/f50_monitor_magisk.zip", use_su=True)
    
    print(f"\n{GREEN}{BOLD}🎉 彻底卸载与清理数据完成！{RESET}")
    print(f"{CYAN}中兴 F50 即将在 3 秒后自动重启还原纯净出厂系统环境...{RESET}")
    time.sleep(3)
    run_adb_shell("reboot", use_su=True)
    print(f"{GREEN}🚀 重启中，设备已完美恢复出厂纯净态。{RESET}")

def hot_update():
    devices = check_adb()
    if not devices:
        print(f"{RED}[错误] 未检测到任何已连接的 ADB 设备！{RESET}")
        return
        
    print(f"\n{CYAN}=== 正在交叉编译并执行热更新... ==={RESET}")
    
    try:
        subprocess.run(["go", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"{RED}[错误] 您的 Mac 未安装 Go 编译器！请先执行 brew install go 或安装 Golang。{RESET}")
        return
        
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

    print(f"{BLUE}[1/3] 正在对 Go 源码进行 android/arm64 交叉编译...{RESET}")
    env = os.environ.copy()
    env["GOOS"] = "linux"
    env["GOARCH"] = "arm64"
    compile_cmd_bot = ["go", "build", "-ldflags=-s -w", "-o", f"{TEMP_DIR}/f50_monitor", "main.go"]
    try:
        subprocess.run(compile_cmd_bot, env=env, check=True)
        print(f"{GREEN}✔︎ Go 核心程序交叉编译成功！{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[错误] Go 编译失败: {e}{RESET}")
        return

    if not wait_for_root():
        return

    print(f"{BLUE}[2/3] 正在推送新版本二进制文件并覆盖底层组件...{RESET}")
    subprocess.run([ADB, "push", f"{TEMP_DIR}/f50_monitor", "/data/local/tmp/"])
    
    run_adb_shell("rm -f /data/adb/modules/f50_monitor/f50_monitor", use_su=True)
    run_adb_shell("cp /data/local/tmp/f50_monitor /data/adb/modules/f50_monitor/f50_monitor && chmod 755 /data/adb/modules/f50_monitor/f50_monitor", use_su=True)
    run_adb_shell("rm -f /data/local/tmp/f50_monitor", use_su=True)
    
    shutil.rmtree(TEMP_DIR)
    
    print(f"{BLUE}[3/3] 正在重启 F50 以应用更新...{RESET}")
    run_adb_shell("reboot", use_su=True)
    print(f"{GREEN}🚀 新版本已推送，设备正在重启！请等待开机后即可生效。{RESET}")
    print(f"\n{GREEN}{BOLD}🎉 更新操作圆满成功！{RESET}")

def show_menu():
    while True:
        os.system("clear")
        devices = check_adb()
        conn_str = f"{GREEN}已连接 (F50 就绪) 📶{RESET}" if devices else f"{RED}未连接 (请开启 ADB 连接) 🔌{RESET}"
        bot_status = get_bot_status() if devices else f"{RED}未连机无法读取{RESET}"
        
        print(f"{CYAN}==================================================")
        print(f"🌡️      ZTE F50 Mac状态栏监控 - 极速控制面板   ")
        print(f"==================================================")
        print(f" 设备连接状态: {conn_str}")
        print(f" 后台监控状态: {bot_status}")
        print(f"=================================================={RESET}")
        print(f"  {BOLD}[1]{RESET} 一键编译并安装 Magisk 系统监控模块 (静默自启)")
        print(f"  {BOLD}[2]{RESET} 查看监控程序在 F50 端的实时运行日志")
        print(f"  {BOLD}[3]{RESET} 重启 监控服务守护 (热重载)")
        print(f"  {BOLD}[4]{RESET} 手动 启动 监控服务")
        print(f"  {BOLD}[5]{RESET} 手动 停止 监控服务")
        print(f"  {BOLD}[6]{RESET} {RED}{BOLD}一键物理彻底卸载模块并还原系统 (物理清空干净){RESET}")
        print(f"  {BOLD}[7]{RESET} {YELLOW}{BOLD}一键更新核心程序 (推送新代码并重启设备){RESET}")
        print(f"--------------------------------------------------")
        print(f"  {BOLD}[r]{RESET} 刷新状态")
        print(f"  {BOLD}[q]{RESET} 退出控制面板")
        print(f"==================================================")
        
        choice = input("请选择操作编号 [1-7 或 r/q]: ").strip()
        if choice == '1':
            one_click_install()
            input(f"\n点击回车继续...")
        elif choice == '2':
            view_logs()
            input(f"\n点击回车继续...")
        elif choice == '3':
            manage_service("restart")
            input(f"\n点击回车继续...")
        elif choice == '4':
            manage_service("start")
            input(f"\n点击回车继续...")
        elif choice == '5':
            manage_service("stop")
            input(f"\n点击回车继续...")
        elif choice == '6':
            one_click_uninstall()
            input(f"\n点击回车继续...")
        elif choice == '7':
            hot_update()
            input(f"\n点击回车继续...")
        elif choice.lower() == 'r':
            continue
        elif choice.lower() == 'q':
            print(f"\n{GREEN}感谢使用！退出控制面板。{RESET}")
            break
        else:
            print(f"{RED}无效的选择，请重新输入！{RESET}")
            time.sleep(1.5)

if __name__ == "__main__":
    show_menu()
