# -*- coding: utf-8 -*-
"""
CleanC - C盘深度清理工具 核心模块
作者：-_Hex  本程序完全开源免费
"""

import os
import sys
import time
import glob
import threading
import traceback
import shutil
import subprocess
import ctypes
import zipfile
from pathlib import Path

# 路径
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent

PROJECT_DIR = SCRIPT_DIR / "CleanC_Project"
PROJECT_DIR.mkdir(exist_ok=True)

# 全局异常捕获
def _global_excepthook(exc_type, exc_value, exc_tb):
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    err_text = ''.join(tb_lines)
    cprint(f"\n程序异常: {err_text}", "red")
    input("\n按回车键退出...")
    sys.exit(1)

sys.excepthook = _global_excepthook

# 颜色常量
COLORS = {
    "reset": "\033[0m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "bred": "\033[1;91m",
    "white": "\033[97m",
    "gray": "\033[90m",
    "magenta": "\033[95m",
}

def cprint(msg, color="reset"):
    print(f"{COLORS.get(color, '')}{msg}{COLORS['reset']}")

def step(msg):
    cprint(f"\n  {msg}", "cyan")

def step_num(n, total, msg):
    cprint(f"\n>> [{n}/{total}] {msg}", "cyan")

def log(msg):
    global LOG_LINES
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)

def show_space_delta(label, before_gb):
    after_gb = get_free_space_gb("C:")
    delta = round(after_gb - before_gb, 2)
    if delta >= 0.01:
        cprint(f"      C盘剩余 {after_gb} GB (+{delta} GB)", "green")
    elif delta <= -0.01:
        cprint(f"      C盘剩余 {after_gb} GB ({delta} GB)", "yellow")
    else:
        cprint(f"      C盘剩余 {after_gb} GB", "gray")
    return after_gb

def write_clean_log():
    if not LOG_LINES:
        return
    log_path = PROJECT_DIR / "clean_log.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("C盘清理工具 - 清理日志\n")
            f.write("=" * 44 + "\n")
            for line in LOG_LINES:
                f.write(line + "\n")
        cprint(f"  日志已保存: {log_path}", "gray")
    except Exception as e:
        cprint(f"  日志保存失败: {e}", "yellow")

def ok(msg):
    cprint(f"   [OK] {msg}", "green")

def warn(msg):
    cprint(f"   [!] {msg}", "yellow")

def err(msg):
    cprint(f"   [X] {msg}", "red")

def info(msg):
    cprint(f"   [i] {msg}", "gray")

def ccol(msg, color):
    return f"{COLORS.get(color, '')}{msg}{COLORS['reset']}"

# 全局状态
AUTO_MODE = False
LOG_LINES = []
MANUAL_COMMANDS = []
DEBUG_LOG = True
STOP_FLAG = threading.Event()   # 停止信号，GUI 点击停止时置位

def add_manual_command(category, title, description, command, path=""):
    MANUAL_COMMANDS.append({
        "category": category,
        "title": title,
        "description": description,
        "command": command,
        "path": path,
    })

def debug_log(msg):
    if not DEBUG_LOG:
        return
    try:
        debug_path = PROJECT_DIR / "debug_trace.txt"
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def run_cmd(cmd, capture=True, wait=True):
    creationflags = subprocess.CREATE_NO_WINDOW
    if capture:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                creationflags=creationflags
            )
            return result.stdout.strip()
        except Exception:
            return ""
    else:
        proc = subprocess.Popen(cmd, shell=True, creationflags=creationflags)
        if wait:
            proc.wait()
        return ""

def get_free_space_gb(drive="C:"):
    try:
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(drive),
            ctypes.byref(free_bytes),
            ctypes.byref(total_bytes),
            None
        )
        return round(free_bytes.value / (1024 ** 3), 2)
    except Exception:
        return 0.0

def get_disk_usage_gb(drive="C:"):
    """返回 (总容量GB, 剩余GB)"""
    try:
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(drive),
            ctypes.byref(free_bytes),
            ctypes.byref(total_bytes),
            None
        )
        return (round(total_bytes.value / (1024 ** 3), 2),
                round(free_bytes.value / (1024 ** 3), 2))
    except Exception:
        return (0.0, 0.0)

def get_total_memory_gb():
    try:
        mem_kb = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_kb))
        return round(mem_kb.value / (1024 ** 2), 2)
    except Exception:
        try:
            out = run_cmd('wmic memorychip get capacity /format:csv')
            total = 0
            for line in out.split('\n')[1:]:
                parts = line.split(',')
                if len(parts) > 1 and parts[-1].strip().isdigit():
                    total += int(parts[-1].strip())
            return round(total / (1024 ** 3), 2) if total > 0 else 0
        except Exception:
            return 0

def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def dir_size(path):
    """计算目录大小（Python 原生遍历，支持停止检查）"""
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            if STOP_FLAG.is_set():
                return total
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        pass
    return total

def remove_tree_safe(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            return True
        elif os.path.isfile(path):
            os.remove(path)
            return True
        return False
    except Exception as e:
        debug_log(f"remove_tree_safe failed: {path} - {e}")
        return False

def clear_dir_with_stop(path):
    """清空目录内容（保留目录本身），支持停止检查"""
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            if STOP_FLAG.is_set():
                return False
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass
        return True
    except Exception:
        return False

def clear_files_with_stop(pattern):
    """删除匹配通配符的文件，支持停止检查，返回删除的字节数"""
    total = 0
    try:
        for f in glob.glob(pattern):
            if STOP_FLAG.is_set():
                return total
            try:
                total += os.path.getsize(f)
                os.remove(f)
            except OSError:
                pass
    except Exception:
        pass
    return total

def scan_appdata_caches(exclude_paths=None):
    """扫描 AppData 下散落的应用缓存目录（Cache/GPUCache/Code Cache），返回 [(名称, 路径, 大小)] 按大小降序"""
    results = []
    cache_keywords = ("cache", "gpu cache", "code cache", "gpucache", "codecache")
    exclude_paths = exclude_paths or set()
    roots = [os.environ.get("APPDATA", ""), os.environ.get("LOCALAPPDATA", "")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for entry in os.scandir(root):
                if not entry.is_dir():
                    continue
                try:
                    for sub in os.scandir(entry.path):
                        if not sub.is_dir():
                            continue
                        if sub.path in exclude_paths:
                            continue
                        name_lower = sub.name.lower()
                        if any(kw in name_lower for kw in cache_keywords):
                            size = dir_size(sub.path)
                            if size > 5 * 1024 * 1024:  # > 5MB 才记录
                                results.append((f"{entry.name}\\{sub.name}", sub.path, size))
                except OSError:
                    continue
        except OSError:
            continue
    results.sort(key=lambda x: -x[2])
    return results

# ============================================================
# 阶段 1: Windows 内置清理
# ============================================================
def stage1_builtin():
    step_num(1, 7, "Windows 内置清理")

    if not is_admin():
        warn("需要管理员权限，跳过")
        return False

    before = get_free_space_gb("C:")
    ok_count = 0

    # DISM 组件清理
    info("正在运行 DISM 组件清理...")
    try:
        proc = subprocess.Popen(
            'dism /online /cleanup-image /startcomponentcleanup',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        while proc.poll() is None:
            if STOP_FLAG.is_set():
                proc.terminate()
                info("已停止 DISM 组件清理")
                break
            time.sleep(0.5)
        if proc.poll() is not None:
            ok("DISM 组件清理完成")
            ok_count += 1
    except Exception as e:
        err(f"DISM 组件清理失败: {e}")

    # DISM 健康恢复
    info("正在检查系统映像健康状态...")
    try:
        proc = subprocess.Popen(
            'dism /online /cleanup-image /restorehealth',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        while proc.poll() is None:
            if STOP_FLAG.is_set():
                proc.terminate()
                info("已停止 DISM 映像修复")
                break
            time.sleep(0.5)
        if proc.poll() is not None:
            ok("DISM 系统映像修复完成")
            ok_count += 1
    except Exception as e:
        err(f"DISM 映像修复失败: {e}")

    after = show_space_delta("第一阶段", before)
    return ok_count > 0


# ============================================================
# 阶段 2: 休眠文件
# ============================================================
def stage2_hibernate():
    step_num(2, 7, "休眠文件")

    mem_gb = get_total_memory_gb()
    info(f"物理内存: {mem_gb} GB")

    if not is_admin():
        warn("需要管理员权限，跳过")
        return False

    hiber_path = r"C:\hiberfil.sys"
    if os.path.exists(hiber_path):
        h_size = os.path.getsize(hiber_path)
        info(f"休眠文件大小: {format_size(h_size)}")
        info("正在禁用休眠...")
        try:
            run_cmd("powercfg -h off")
            if not os.path.exists(hiber_path):
                ok("休眠已禁用，hiberfil.sys 已删除")
            else:
                warn("休眠已禁用，但 hiberfil.sys 仍存在（可能被占用，重启后自动删除）")
            return True
        except Exception as e:
            err(f"禁用休眠失败: {e}")
            return False
    else:
        ok("休眠文件不存在，无需处理")
        return False


# ============================================================
# 阶段 3: 显卡驱动残留清理
# ============================================================
def stage3_gpu_drivers():
    step_num(3, 7, "显卡驱动残留清理")

    info("清理 C:\\NVIDIA、C:\\AMD、C:\\Intel 安装残留目录")
    before = get_free_space_gb("C:")

    found_any = False
    gpu_dirs = {
        "NVIDIA": [r"C:\NVIDIA"],
        "AMD": [r"C:\AMD"],
        "Intel": [r"C:\Intel"],
    }

    if AUTO_MODE:
        choice = "4"
        info("自动模式: 清理所有品牌驱动残留")
    else:
        print("\n  选择清理目标:")
        print("    1 = NVIDIA  2 = AMD  3 = Intel  4 = 全部  0 = 跳过")
        choice = input("  >>> ").strip()

    if choice == "0":
        info("已跳过")
        return False

    targets = set()
    if choice == "1": targets.add("NVIDIA")
    elif choice == "2": targets.add("AMD")
    elif choice == "3": targets.add("Intel")
    elif choice == "4": targets = {"NVIDIA", "AMD", "Intel"}
    else:
        warn("无效选择，跳过")
        return False

    total_removed = 0
    for brand, dirs in gpu_dirs.items():
        if brand not in targets:
            continue
        for d in dirs:
            if STOP_FLAG.is_set():
                info("已停止")
                return found_any
            if os.path.isdir(d):
                try:
                    size = dir_size(d)
                    shutil.rmtree(d, ignore_errors=True)
                    if not os.path.exists(d):
                        ok(f"已删除 {brand} 目录: {d} ({format_size(size)})")
                        total_removed += size
                        found_any = True
                except Exception as e:
                    err(f"删除失败 {d}: {e}")

    if total_removed > 0:
        ok(f"共释放 {format_size(total_removed)}")
    elif not found_any:
        ok("未找到可清理的驱动残留目录")

    show_space_delta("第三阶段", before)
    return found_any


# ============================================================
# 阶段 4: 虚拟内存配置
# ============================================================
def stage4_virtual_memory():
    step_num(4, 7, "虚拟内存配置")

    if not is_admin():
        warn("需要管理员权限，跳过")
        return False

    before = get_free_space_gb("C:")
    total_mem = get_total_memory_gb()

    info(f"物理内存: {total_mem} GB")

    if AUTO_MODE:
        info("自动模式: 保持默认设置")
        return False

    choice = input("是否手动设置虚拟内存？(y/n): ").strip().lower()
    if choice != "y":
        info("保持默认设置")
        return False

    drive = input("目标盘符 (默认 D): ").strip().upper() or "D"
    if not (len(drive) == 1 and drive.isalpha()):
        warn("无效盘符，已取消")
        return False
    vmin = input("初始大小 MB (推荐 4096): ").strip() or "4096"
    vmax = input("最大大小 MB (推荐 8192): ").strip() or "8192"
    if not (vmin.isdigit() and vmax.isdigit() and int(vmin) > 0 and int(vmax) > 0):
        warn("大小必须为正整数，已取消")
        return False
    if int(vmax) < int(vmin):
        warn("最大值不能小于最小值，已取消")
        return False

    info(f"配置: {drive} 盘, {vmin}-{vmax} MB")

    confirm = input("确认应用？(y/n): ").strip().lower()
    if confirm != "y":
        info("已取消")
        return False

    # PowerShell WMI 设置虚拟内存
    ps_script = f'''
$computer = "."
$pagefile = Get-WmiObject -Class Win32_PageFileSetting -ComputerName $computer
if ($pagefile) {{
    $pagefile.InitialSize = {vmin}
    $pagefile.MaximumSize = {vmax}
    $pagefile.Put() | Out-Null
}} else {{
    $pf = [wmiclass]"\\\\.\\root\\cimv2:Win32_PageFileSetting"
    $pf.Name = "{drive}:\\pagefile.sys"
    $pf.InitialSize = {vmin}
    $pf.MaximumSize = {vmax}
    $pf.Put() | Out-Null
}}
Write-Output "DONE"
'''

    try:
        result = run_cmd(f'powershell -NoProfile -WindowStyle Hidden -Command "{ps_script}"')
        if "DONE" in result:
            ok(f"虚拟内存已设置为 {drive} 盘 {vmin}-{vmax} MB")
            warn("需要重启计算机以生效")
            return True
        else:
            err("虚拟内存设置失败")
            return False
    except Exception as e:
        err(f"虚拟内存设置异常: {e}")
        return False


# ============================================================
# 阶段 5: WizTree 空间分析
# ============================================================
def stage5_wiztree():
    step_num(5, 7, "WizTree 空间分析")

    wiztree_exe = PROJECT_DIR / "WizTree" / "WizTree64.exe"
    csv_path = PROJECT_DIR / "wiztree_scan.csv"

    if not wiztree_exe.exists():
        # 尝试下载
        info("WizTree 未找到，正在下载...")
        try:
            url = "https://wiztreefree.com/files/wiztree_4_30_portable.zip"
            zip_path = PROJECT_DIR / "wiztree_portable.zip"
            run_cmd(f'powershell -NoProfile -WindowStyle Hidden -Command "Invoke-WebRequest -Uri \'{url}\' -OutFile \'{zip_path}\' -UseBasicParsing"')
            if zip_path.exists():
                wiztree_dir = PROJECT_DIR / "WizTree"
                wiztree_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(wiztree_dir)
                zip_path.unlink()
                ok("WizTree 下载完成")
        except Exception as e:
            err(f"WizTree 下载失败: {e}")
            return False

    if not wiztree_exe.exists():
        err("WizTree 不可用")
        return False

    return _stage5_run_wiztree(wiztree_exe, csv_path)


def _stage5_run_wiztree(wiztree_exe, csv_path):
    before = get_free_space_gb("C:")

    info("正在扫描 C 盘（WizTree 窗口会自动关闭）...")

    try:
        run_cmd(f'"{wiztree_exe}" C: /export="{csv_path}" /admin=1 /close', capture=False, wait=True)
    except Exception as e:
        err(f"WizTree 扫描失败: {e}")
        return False

    if not csv_path.exists():
        err("扫描结果文件未生成")
        return False

    info("正在分析扫描结果...")
    top_items = []
    try:
        import csv
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if len(rows) < 3:
            err("扫描结果为空")
            return False

        for row in rows[2:]:
            if STOP_FLAG.is_set():
                info("已停止")
                break
            if len(row) < 3:
                continue
            try:
                name = row[0].strip()
                size_str = row[1].strip()
                size = int(size_str) if size_str.isdigit() else 0
                if size > 0:
                    top_items.append((name, size, row[2].strip()))
            except (ValueError, IndexError):
                continue

        top_items.sort(key=lambda x: x[1], reverse=True)

        cprint(f"\n  {'目录/文件名':<50} {'大小':>12}", "white")
        cprint("  " + "-" * 65, "gray")
        # Windows / Program Files X86 / ProgramData / Users (全量和 Top)
        c_dirs = {"Windows": 0, "Program Files": 0, "Program Files (x86)": 0,
                  "ProgramData": 0, "Users": 0}
        for name, size, alloc in top_items:
            for key in c_dirs:
                if name.startswith(key) or name == key:
                    c_dirs[key] += size
            if len(top_items[:15]) > 0:
                pass

        # 展示主要目录占用
        for key in ["Windows", "Program Files", "Program Files (x86)", "ProgramData", "Users"]:
            if c_dirs[key] > 0:
                cprint(f"  {key:<50} {format_size(c_dirs[key]):>12}", "white")

        # Top 15 大项
        cprint(f"\n  Top 15 大项:", "white")
        for i, (name, size, alloc) in enumerate(top_items[:15], 1):
            short_name = name if len(name) <= 48 else name[:45] + "..."
            cprint(f"  {i:2}. {short_name:<48} {format_size(size):>12}", "gray")

        ok(f"WizTree 分析完成，共 {len(top_items)} 项")
    except Exception as e:
        err(f"分析扫描结果失败: {e}")
        return False

    show_space_delta("第五阶段", before)
    return True


# ============================================================
# 阶段 6: 驱动仓库空间分析
# ============================================================
def stage6_driver_store():
    step_num(6, 7, "驱动仓库空间分析")

    if not is_admin():
        warn("需要管理员权限，跳过")
        return False

    before = get_free_space_gb("C:")
    driver_store = r"C:\Windows\System32\DriverStore\FileRepository"

    if not os.path.isdir(driver_store):
        err("驱动仓库目录不存在")
        return False

    # 获取已加载驱动
    info("正在获取已加载驱动列表...")
    loaded_drivers = set()
    try:
        out = run_cmd("driverquery /v /fo csv")
        for line in out.split("\n")[1:]:
            line = line.strip().strip('"')
            if line:
                parts = line.split(",")
                if parts:
                    loaded_drivers.add(parts[0].strip().strip('"').lower())
    except Exception:
        pass

    # 扫描驱动仓库目录
    info("正在扫描驱动仓库...")
    inf_map = {}
    for item in os.listdir(driver_store):
        if STOP_FLAG.is_set():
            info("已停止")
            break
        item_path = os.path.join(driver_store, item)
        if not os.path.isdir(item_path):
            continue
        # 查找 .inf 文件获取 OEM 编号
        inf_files = list(Path(item_path).glob("*.inf"))
        oem_num = None
        for inf_f in inf_files:
            try:
                with open(inf_f, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "oem" in line.lower() and ".inf" in line.lower():
                            parts = line.strip().split("=")
                            if len(parts) > 1:
                                oem_num = parts[1].strip().strip('"')
                                break
                    if oem_num:
                        break
            except Exception:
                pass

        drv_size = dir_size(item_path)
        if oem_num:
            inf_map[oem_num] = (item, drv_size)
        else:
            inf_map[item] = (item, drv_size)

    # OEM 驱动映射
    info("正在分析 OEM 驱动...")
    oem_map = {}
    try:
        out = run_cmd("pnputil /enum-drivers")
        current_name = None
        for line in out.split("\n"):
            line = line.strip()
            if "Published Name" in line:
                current_name = line.split(":")[-1].strip().lower()
            elif "Driver Package Provider" in line and current_name:
                provider = line.split(":")[-1].strip().lower()
                oem_map[current_name] = provider
    except Exception:
        pass

    # 分类: 已加载/未加载, 同基名多版本
    total_size = 0
    removable = []
    keep = []

    for oem_or_name, (dir_name, size) in inf_map.items():
        if size <= 0:
            continue
        total_size += size
        name_key = oem_or_name.lower()

        # 规则1: 已加载驱动 → 保留
        if any(name_key.startswith(ld) or ld.startswith(name_key) for ld in loaded_drivers):
            keep.append((dir_name, size, "已加载驱动"))
            continue

        # 规则2: 同基名存在多版本 → 旧版可删
        base_name = dir_name.split("_")[0].lower() if "_" in dir_name else dir_name.lower()
        same_base = [d for d, s in inf_map.values() if d != dir_name and d.lower().startswith(base_name)]
        if same_base:
            removable.append((dir_name, size, "多版本-旧版"))
            continue

        # 规则3: 无 OEM 映射 → 残留
        if oem_or_name not in oem_map:
            removable.append((dir_name, size, "无驱动映射"))
            continue

        keep.append((dir_name, size, "未知"))

    removable.sort(key=lambda x: x[1], reverse=True)
    keep.sort(key=lambda x: x[1], reverse=True)

    cprint(f"\n  驱动仓库总占用: {format_size(total_size)}", "white")

    # 可清理项
    if removable:
        cprint(f"\n  可清理的驱动 ({len(removable)} 项):", "yellow")
        for dir_name, size, reason in removable:
            cprint(f"    {dir_name:<50} {format_size(size):>10}  ({reason})", "gray")
    else:
        ok("未发现可清理的驱动")

    # 保留项
    if keep:
        cprint(f"\n  保留的驱动 ({len(keep)} 项):", "green")
        for dir_name, size, reason in keep[:10]:
            cprint(f"    {dir_name:<50} {format_size(size):>10}  ({reason})", "gray")
        if len(keep) > 10:
            cprint(f"    ... 共 {len(keep)} 项", "gray")

    # 驱动仓库清理说明（不加入 MANUAL_COMMANDS，避免误导用户勾选执行）
    if removable:
        cprint(
            f"\n  驱动仓库可清理 {len(removable)} 项，约 {format_size(sum(r[1] for r in removable))}。",
            "yellow"
        )
        cprint("  本工具不自动删除驱动，如需清理请在管理员 PowerShell 中逐项执行：", "yellow")
        cprint("    pnputil /delete-driver <OEM编号.inf> /uninstall /force", "yellow")

    show_space_delta("第六阶段", before)
    return len(removable) > 0


# ============================================================
# 阶段 7: 临时文件与缓存深度清理
# ============================================================
def stage7_temp_cache():
    step_num(7, 7, "临时文件与缓存深度清理")

    before = get_free_space_gb("C:")
    total_cleaned = 0

    # 安全可自动清理项：("dir", 目录路径) 清空目录内容；("files", 通配符) 删除匹配文件
    # 均为可自动重建的缓存/日志，不影响用户数据
    safe_items = {
        "用户临时文件": ("dir", os.environ.get("TEMP", "")),
        "系统临时文件": ("dir", os.environ.get("SystemRoot", "C:\\Windows") + "\\Temp"),
        "预读取文件": ("dir", r"C:\Windows\Prefetch"),
        "Windows更新下载缓存": ("dir", r"C:\Windows\SoftwareDistribution\Download"),
        "传递优化文件": ("dir", r"C:\Windows\SoftwareDistribution\DeliveryOptimization"),
        "程序崩溃记录": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\CrashDumps"),
        "Windows错误报告": ("dir", os.environ.get("ProgramData", "") + "\\Microsoft\\Windows\\WER"),
        "DISM日志": ("dir", r"C:\Windows\Logs\DISM"),
        "CBS日志": ("dir", r"C:\Windows\Logs\CBS"),
        "Windows更新日志": ("dir", r"C:\Windows\Logs\WindowsUpdate"),
        "Windows事件日志": ("dir", r"C:\Windows\System32\winevt\Logs"),
        "崩溃转储": ("dir", r"C:\Windows\Minidump"),
        "Windows通知缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Windows\\Notifications"),
        "Windows网络缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Windows\\INetCache"),
        "字体缓存": ("dir", r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"),
        "缩略图缓存": ("files", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Windows\\Explorer\\thumbcache_*.db"),
        "图标缓存": ("files", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Windows\\Explorer\\iconcache_*.db"),
        "DirectX着色器缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\D3DSCache"),
        "NVIDIA着色器缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\NVIDIA\\DXCache"),
        "NVIDIA OpenGL缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\NVIDIA\\GLCache"),
        "AMD着色器缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\AMD\\DxCache"),
        "Intel着色器缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Intel\\ShaderCache"),
        "Chrome缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Google\\Chrome\\User Data\\Default\\Cache"),
        "Chrome代码缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Google\\Chrome\\User Data\\Default\\Code Cache"),
        "ChromeGPU缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Google\\Chrome\\User Data\\Default\\GPUCache"),
        "Edge缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Edge\\User Data\\Default\\Cache"),
        "Edge代码缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Edge\\User Data\\Default\\Code Cache"),
        "EdgeGPU缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\Edge\\User Data\\Default\\GPUCache"),
        "Steam缓存": ("dir", r"C:\Program Files (x86)\Steam\appcache"),
        "SteamHTML缓存": ("dir", r"C:\Program Files (x86)\Steam\htmlcache"),
        "Teams缓存": ("dir", os.environ.get("APPDATA", "") + "\\Microsoft\\Teams\\Cache"),
        "VS Code缓存": ("dir", os.environ.get("APPDATA", "") + "\\Code\\Cache"),
        "npm缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\npm-cache"),
        "pip缓存": ("dir", os.environ.get("LOCALAPPDATA", "") + "\\pip\\cache"),
    }

    # NVIDIA 残留
    nvidia_programdata = os.environ.get("ProgramData", "") + "\\NVIDIA Corporation"
    nvidia_local = os.environ.get("LOCALAPPDATA", "") + "\\NVIDIA Corporation"
    for name, path in [("NVIDIA残留(ProgramData)", nvidia_programdata),
                        ("NVIDIA残留(LocalAppData)", nvidia_local)]:
        if os.path.isdir(path):
            safe_items[name] = ("dir", path)

    info("正在清理安全可自动处理的临时文件...")

    for name, item in safe_items.items():
        if STOP_FLAG.is_set():
            info("已停止")
            break
        kind, path = item
        if not path:
            continue

        # 目录类型：跳过根目录
        if kind == "dir":
            if not os.path.isdir(path):
                continue
            drive_root = os.path.splitdrive(path)[0] + "\\"
            if path == drive_root:
                continue
            try:
                size_before = dir_size(path)
                if size_before <= 0:
                    continue
                info(f"  清理 {name}... ({format_size(size_before)})")
                clear_dir_with_stop(path)
                if STOP_FLAG.is_set():
                    info("已停止")
                    break
                size_after = dir_size(path)
                cleaned = size_before - size_after
            except Exception as e:
                debug_log(f"清理 {name} 失败: {e}")
                continue
        else:
            # 文件通配符类型：缩略图/图标缓存
            try:
                matched = glob.glob(path)
                if not matched:
                    continue
                size_before = sum(os.path.getsize(f) for f in matched if os.path.isfile(f))
                if size_before <= 0:
                    continue
                info(f"  清理 {name}... ({format_size(size_before)})")
                cleaned = clear_files_with_stop(path)
                if STOP_FLAG.is_set():
                    info("已停止")
                    break
            except Exception as e:
                debug_log(f"清理 {name} 失败: {e}")
                continue

        if cleaned > 1024 * 1024:  # > 1MB 才算有效
            total_cleaned += cleaned
            ok(f"  清理 {name}: {format_size(cleaned)}")
        else:
            info(f"  {name}: 无需清理")

    # 通用应用缓存扫描：AppData 下散落、无明显特征的 Cache/GPUCache/Code Cache
    info("正在扫描 AppData 下散落的应用缓存...")
    exclude_paths = {p for _, p in safe_items.values()}
    appdata_caches = scan_appdata_caches(exclude_paths)
    for name, path, size in appdata_caches:
        if STOP_FLAG.is_set():
            info("已停止")
            break
        if size < 10 * 1024 * 1024:
            continue
        info(f"  清理 {name}... ({format_size(size)})")
        clear_dir_with_stop(path)
        if STOP_FLAG.is_set():
            info("已停止")
            break
        size_after = dir_size(path)
        cleaned = size - size_after
        if cleaned > 1024 * 1024:
            total_cleaned += cleaned
            ok(f"  清理 {name}: {format_size(cleaned)}")
        else:
            info(f"  {name}: 无需清理")

    # 高收益慎清项（涉及用户数据或影响体验，仅给命令，不自动执行）
    high_value = {
        "Firefox浏览器缓存": r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\cache2\*",
        "微信文件缓存": r"%USERPROFILE%\Documents\WeChat Files\*\FileStorage\Cache\*",
        "QQ图片视频缓存": r"%USERPROFILE%\Documents\Tencent Files\*\Image\*",
        "Windows搜索索引缓存": r"C:\ProgramData\Microsoft\Search\Data\*",
    }

    for name, path in high_value.items():
        add_manual_command(
            "高收益慎清项",
            f"清理{name}",
            f"清理 {name}: {path}。涉及用户数据或影响体验，请确认后手动执行。",
            f"del /f /s /q \"{path}\" 2>nul",
            path
        )

    if total_cleaned > 0:
        ok(f"阶段7 共释放 {format_size(total_cleaned)}")
    else:
        info("未发现可清理的临时文件")

    show_space_delta("第七阶段", before)
    return total_cleaned > 0


# ============================================================
# 手动命令确认对话框 (CLI版本使用)
# ============================================================
def show_manual_commands_dialog():
    if not MANUAL_COMMANDS:
        return

    cprint("\n" + "=" * 44, "yellow")
    cprint("  以下操作建议手动执行：", "yellow")
    cprint("=" * 44, "yellow")

    last_cat = ""
    for i, cmd in enumerate(MANUAL_COMMANDS, 1):
        if cmd["category"] != last_cat:
            last_cat = cmd["category"]
            cprint(f"\n  ▎{last_cat}", "white")
        cprint(f"    [{i}] {cmd['description']}", "gray")

    if AUTO_MODE:
        cprint("\n  自动模式: 跳过手动命令", "gray")
        return

    print()
    choice = input("是否生成批处理脚本执行选中操作？(y/n): ").strip().lower()
    if choice != "y":
        return

    bat_path = PROJECT_DIR / "manual_cleanup.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\nchcp 65001 >nul\ntitle 清理操作执行中\n\n")
        for cmd in MANUAL_COMMANDS:
            f.write(f'echo 正在执行: {cmd["title"]}\n')
            f.write(f'{cmd["command"]}\n')
            f.write("echo.\n")
        f.write("echo 全部操作已完成\npause >nul\n")

    run_cmd(f'start "" "{bat_path}"', capture=False, wait=False)
    ok(f"批处理已生成: {bat_path}")


# ============================================================
# 主入口
# ============================================================
def main():
    if not is_admin():
        cprint("请以管理员身份运行此程序！", "red")
        input("\n按回车键退出...")
        return

    cprint("=" * 44, "magenta")
    cprint("  C盘深度清理工具", "magenta")
    cprint("  作者：-_Hex  本程序完全开源免费", "magenta")
    cprint("=" * 44, "magenta")

    before_main = get_free_space_gb("C:")
    info(f"清理前 C 盘剩余: {before_main} GB")
    LOG_LINES.append(f"C盘清理开始，初始剩余 {before_main} GB")

    auto_choice = input("\n是否使用自动模式？(跳过所有交互) (y/n): ").strip().lower()
    global AUTO_MODE
    if auto_choice == "y":
        AUTO_MODE = True
        info("已启用自动模式")
    else:
        info("交互模式（需要手动确认关键操作）")

    stages = [
        ("第一阶段", stage1_builtin),
        ("第二阶段", stage2_hibernate),
        ("第三阶段", stage3_gpu_drivers),
        ("第四阶段", stage4_virtual_memory),
        ("第五阶段", stage5_wiztree),
        ("第六阶段", stage6_driver_store),
        ("第七阶段", stage7_temp_cache),
    ]

    if not AUTO_MODE:
        print("\n  选择要执行的阶段（输入数字，如 '1 2 3' 或 'all'）:")
        for i, (name, _) in enumerate(stages, 1):
            print(f"    [{i}] {name}")
        sel = input("  >>> ").strip().lower()
        if sel == "all":
            selected = list(range(7))
        else:
            selected = [int(s) - 1 for s in sel.split() if s.isdigit() and 1 <= int(s) <= 7]
        if not selected:
            warn("未选择有效阶段，已取消")
            return

        confirm = input(f"\n  确认执行 {len(selected)} 个阶段？(y/n): ").strip().lower()
        if confirm != "y":
            info("已取消")
            return
    else:
        selected = list(range(7))

    need_reboot = False
    for i in selected:
        name, func = stages[i]
        try:
            result = func()
            if result:
                need_reboot = True
        except Exception as e:
            err(f"{name} 执行异常: {e}")

    # 写日志
    write_clean_log()

    after_main = get_free_space_gb("C:")
    released = round(max(0, after_main - before_main), 2)

    cprint(f"\n{'='*44}", "green")
    cprint(f"  全部完成！共释放约 {released} GB", "green")
    cprint(f"{'='*44}", "green")

    if need_reboot:
        cprint("\n  虚拟内存配置已修改，请手动重启计算机以生效。", "yellow")

    # 手动命令
    if MANUAL_COMMANDS:
        show_manual_commands_dialog()

    if not AUTO_MODE:
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
