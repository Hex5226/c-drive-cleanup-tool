# -*- coding: utf-8 -*-
"""
CleanC GUI - C盘深度清理工具 图形界面
作者：-_Hex  本程序完全开源免费
UI：CustomTkinter 现代化界面（圆角卡片 / 深色主题 / 主色青绿）
"""

import sys
import os
import builtins
import threading
import queue
import subprocess
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
import tkinter as tk

# ── 路径 ──────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import CleanC
import updater

# ── 配色（清理主题：深色底 + 青绿主色）────────────────
COLOR_BG = "#1a1b1e"
COLOR_CARD = "#24262b"
COLOR_CARD_ALT = "#2a2d33"
COLOR_PRIMARY = "#2fa88a"
COLOR_PRIMARY_HOVER = "#3bbf9e"
COLOR_DANGER = "#e5484d"
COLOR_DANGER_HOVER = "#f2555a"
COLOR_TEXT = "#e6e6e6"
COLOR_TEXT_DIM = "#8a8f98"
COLOR_BORDER = "#33363d"
COLOR_LOG_BG = "#1e2024"

# 日志 tag → 前景色
TAG_COLORS = {
    "cyan": "#569cd6", "green": "#4ec9b0", "yellow": "#dcdcaa",
    "red": "#f44747", "bred": "#ff6b6b", "white": "#ffffff",
    "gray": "#8a8f98", "magenta": "#c586c0",
}

# ── 线程安全的输入/输出拦截 ──────────────────────────
_log_queue = queue.Queue()       # (type, text) → GUI 日志
_input_queue = queue.Queue()     # 预置的用户输入响应
_input_lock = threading.Lock()
_stop_flag = threading.Event()
_is_running = False
_checking_update = False
_original_input = builtins.input
_original_print = builtins.print
_original_os_system = os.system


def _gui_print(*args, **kwargs):
    """拦截 print，转发到 GUI 日志"""
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    text = sep.join(str(a) for a in args) + end
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped:
            _log_queue.put(('info', stripped))


def _gui_input(prompt=""):
    """拦截 input，从预置队列取响应；队列空时返回空串"""
    if prompt and prompt.strip():
        _log_queue.put(('info', prompt.strip()))
    try:
        return _input_queue.get(timeout=0.1)
    except queue.Empty:
        return ""


def _gui_os_system(cmd):
    """拦截 os.system，防止 title/cls 干扰 GUI"""
    if 'title' in cmd or 'cls' in cmd:
        return 0
    return _original_os_system(cmd)


def _hijack_output():
    """重定向 CleanC 模块的输出到 GUI"""
    CleanC.cprint = lambda msg, color="reset": _log_queue.put((color, msg))
    CleanC.info = lambda msg: _log_queue.put(('gray', f"   [i] {msg}"))
    CleanC.ok = lambda msg: _log_queue.put(('green', f"   [OK] {msg}"))
    CleanC.warn = lambda msg: _log_queue.put(('yellow', f"   [!] {msg}"))
    CleanC.err = lambda msg: _log_queue.put(('red', f"   [X] {msg}"))
    CleanC.step_num = lambda n, t, msg: _log_queue.put(('cyan', f"\n>> [{n}/{t}] {msg}"))
    CleanC.show_space_delta = _gui_show_space_delta
    CleanC.log = _gui_log
    CleanC.ccol = lambda msg, color: msg  # GUI 不需要 ANSI 颜色
    CleanC.debug_log = lambda msg: None   # GUI 模式不写调试日志


def _gui_show_space_delta(label, before_gb):
    after_gb = CleanC.get_free_space_gb("C:")
    delta = round(after_gb - before_gb, 2)
    if delta >= 0.01:
        _log_queue.put(('green', f"      C盘剩余 {after_gb} GB (+{delta} GB)"))
    elif delta <= -0.01:
        _log_queue.put(('yellow', f"      C盘剩余 {after_gb} GB ({delta} GB)"))
    else:
        _log_queue.put(('gray', f"      C盘剩余 {after_gb} GB"))
    _log_queue.put(('space_update', str(after_gb)))
    return after_gb


def _gui_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    CleanC.LOG_LINES.append(f"[{ts}] {msg}")


# ── 主窗口 ────────────────────────────────────────────
class CleanCGUI:
    def __init__(self):
        self.root = self._init_tk()
        self._build_ui()

        # 状态
        self.before_free = 0.0
        self.current_free = 0.0
        self.cleaned_total = 0.0
        self.need_reboot = False
        self.progress_value = 0

        # 用户选择
        self.gpu_choice = "0"
        self.vm_enabled = False
        self.vm_drive = "D"
        self.vm_min = "4096"
        self.vm_max = "8192"

        # 更新 UI
        self._update_space()
        self._poll_log_queue()

    # ── CustomTkinter 初始化 ────────────────────────
    def _init_tk(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        root = ctk.CTk()
        root.title("CleanC - C盘深度清理工具")
        root.geometry("1000x760")
        root.minsize(880, 660)
        root.configure(fg_color=COLOR_BG)
        # 设置窗口图标（打包后从 _MEIPASS 读取内嵌 ico，源码运行读 assets）
        try:
            _base = getattr(sys, "_MEIPASS", str(SCRIPT_DIR))
            _ico = os.path.join(_base, "CleanC.ico")
            if os.path.exists(_ico):
                root.iconbitmap(_ico)
        except Exception:
            pass
        return root

    # ── 界面构建 ────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # ── 顶部标题栏 ──
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(header, text="CleanC", font=("Microsoft YaHei UI", 20, "bold"),
                     text_color=COLOR_PRIMARY).pack(side="left")
        ctk.CTkLabel(header, text="C盘深度清理工具", font=("Microsoft YaHei UI", 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(header, text="-_Hex  |  完全开源免费", font=("Microsoft YaHei UI", 9),
                     text_color=COLOR_TEXT_DIM).pack(side="right")

        # ── 磁盘空间卡片 ──
        dash = ctk.CTkFrame(root, corner_radius=12, fg_color=COLOR_CARD,
                            border_width=1, border_color=COLOR_BORDER)
        dash.pack(fill="x", padx=18, pady=6)

        dash_left = ctk.CTkFrame(dash, fg_color="transparent")
        dash_left.pack(side="left", padx=18, pady=12)
        ctk.CTkLabel(dash_left, text="C盘剩余", font=("Microsoft YaHei UI", 10),
                     text_color=COLOR_TEXT_DIM).pack(anchor="w")
        self.lbl_space_big = ctk.CTkLabel(dash_left, text="-- GB",
                                          font=("Microsoft YaHei UI", 26, "bold"),
                                          text_color=COLOR_PRIMARY)
        self.lbl_space_big.pack(anchor="w")

        dash_right = ctk.CTkFrame(dash, fg_color="transparent")
        dash_right.pack(side="left", fill="x", expand=True, padx=(0, 18), pady=12)
        # 自定义空间条：左侧=已用（颜色随占用率变化），右侧=可用（绿色）
        self.space_canvas = tk.Canvas(dash_right, height=14, bg=COLOR_CARD,
                                      highlightthickness=0, bd=0)
        self.space_canvas.pack(fill="x", pady=(10, 4))
        # 图例
        legend = ctk.CTkFrame(dash_right, fg_color="transparent")
        legend.pack(fill="x", pady=(0, 2))
        self.legend_used = ctk.CTkLabel(legend, text="  ", width=12, height=12,
                                        fg_color=COLOR_PRIMARY, corner_radius=3)
        self.legend_used.pack(side="left")
        ctk.CTkLabel(legend, text="已用", font=("Microsoft YaHei UI", 9),
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(4, 12))
        self.legend_free = ctk.CTkLabel(legend, text="  ", width=12, height=12,
                                        fg_color=COLOR_PRIMARY, corner_radius=3)
        self.legend_free.pack(side="left")
        ctk.CTkLabel(legend, text="可用", font=("Microsoft YaHei UI", 9),
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(4, 0))
        self.lbl_space_text = ctk.CTkLabel(dash_right, text="C: -- GB / ~-- GB",
                                           font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT)
        self.lbl_space_text.pack(anchor="w")
        self.lbl_space_delta = ctk.CTkLabel(
            dash_right, text="清理前 -- GB  |  本次释放 -- GB  |  当前 -- GB",
            font=("Microsoft YaHei UI", 9), text_color=COLOR_TEXT_DIM)
        self.lbl_space_delta.pack(anchor="w", pady=(2, 0))

        # ── 中间主区域 ──
        main_frame = ctk.CTkFrame(root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=18, pady=6)

        # 左卡片 - 阶段列表（可滚动，防止窗口变小时按钮被挤出）
        left_card = ctk.CTkScrollableFrame(main_frame, corner_radius=12, fg_color=COLOR_CARD,
                                           border_width=1, border_color=COLOR_BORDER, width=290)
        left_card.pack(side="left", fill="y", padx=(0, 8))

        ctk.CTkLabel(left_card, text="清理阶段", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=16, pady=(14, 8))

        stage_names = [
            "Windows 内置清理",
            "休眠文件",
            "显卡驱动残留清理",
            "虚拟内存配置",
            "WizTree 空间分析",
            "驱动仓库空间分析",
            "临时文件与缓存深度清理",
        ]

        self.stage_vars = []
        for i, name in enumerate(stage_names):
            var = ctk.IntVar(value=1)
            self.stage_vars.append(var)
            cb = ctk.CTkCheckBox(left_card, text=f"[{i+1}/7] {name}", variable=var,
                                 font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT,
                                 fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                                 corner_radius=6, checkbox_width=20, checkbox_height=20)
            cb.pack(anchor="w", padx=16, pady=4)

        # 全选/取消
        sel_btn = ctk.CTkFrame(left_card, fg_color="transparent")
        sel_btn.pack(fill="x", padx=16, pady=(10, 0))
        ctk.CTkButton(sel_btn, text="全选", command=lambda: self._toggle_all(True),
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 10), height=28).pack(side="left", padx=(0, 6))
        ctk.CTkButton(sel_btn, text="取消全选", command=lambda: self._toggle_all(False),
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 10), height=28).pack(side="left")

        # 快捷配置
        cfg_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        cfg_frame.pack(fill="x", padx=16, pady=(14, 14))
        ctk.CTkLabel(cfg_frame, text="快捷配置", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 6))
        ctk.CTkButton(cfg_frame, text="选择显卡品牌", command=self._dlg_gpu,
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 10), height=32).pack(fill="x", pady=3)
        ctk.CTkButton(cfg_frame, text="设置虚拟内存", command=self._dlg_vm,
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 10), height=32).pack(fill="x", pady=3)

        # 右卡片 - 日志
        right_card = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=COLOR_CARD,
                                  border_width=1, border_color=COLOR_BORDER)
        right_card.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(right_card, text="运行日志", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=16, pady=(14, 8))

        self.log_text = ctk.CTkTextbox(right_card, font=("Consolas", 12),
                                       fg_color=COLOR_LOG_BG, text_color=COLOR_TEXT,
                                       corner_radius=8, border_width=1, border_color=COLOR_BORDER,
                                       wrap="word", activate_scrollbars=True)
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for color, fg in TAG_COLORS.items():
            self.log_text.tag_config(color, foreground=fg)

        # ── 阶段进度条 ──
        prog_frame = ctk.CTkFrame(root, fg_color="transparent")
        prog_frame.pack(fill="x", padx=18, pady=(4, 2))
        ctk.CTkLabel(prog_frame, text="阶段进度", font=("Microsoft YaHei UI", 10),
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(0, 10))
        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=10, corner_radius=5,
                                               fg_color=COLOR_CARD_ALT, progress_color=COLOR_PRIMARY)
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_bar.set(0)

        # ── 底部按钮栏 ──
        btn_frame = ctk.CTkFrame(root, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(8, 14))

        self.btn_start = ctk.CTkButton(btn_frame, text="开始清理", command=self._start_cleanup,
                                       fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                                       corner_radius=8, font=("Microsoft YaHei UI", 13, "bold"),
                                       height=40, width=140)
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = ctk.CTkButton(btn_frame, text="停止", command=self._stop_cleanup,
                                      fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                                      corner_radius=8, font=("Microsoft YaHei UI", 13, "bold"),
                                      height=40, width=100, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="复制日志", command=self._copy_log,
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 11), height=40).pack(side="left")

        self.btn_update = ctk.CTkButton(btn_frame, text="检查更新", command=self._check_update,
                                        fg_color=COLOR_CARD_ALT, hover_color="#3a3d44",
                                        corner_radius=8, font=("Microsoft YaHei UI", 11),
                                        height=40)
        self.btn_update.pack(side="left", padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(btn_frame, text="就绪", font=("Microsoft YaHei UI", 11),
                                       text_color=COLOR_TEXT_DIM)
        self.lbl_status.pack(side="right")

    # ── 通用对话框 ──────────────────────────────────
    def _ask_yes_no(self, title, message):
        """自绘确认对话框，返回 bool"""
        result = {"value": False}
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(title)
        dlg.geometry("440x210")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=message, wraplength=390, justify="left",
                     font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT
                     ).pack(pady=(22, 18), padx=24)
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(0, 18))
        def yes():
            result["value"] = True
            dlg.destroy()
        def no():
            result["value"] = False
            dlg.destroy()
        ctk.CTkButton(btn_frame, text="是", command=yes, fg_color=COLOR_PRIMARY,
                      hover_color=COLOR_PRIMARY_HOVER, corner_radius=8,
                      font=("Microsoft YaHei UI", 11), width=96).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="否", command=no, fg_color=COLOR_CARD_ALT,
                      hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 11), width=96).pack(side="left", padx=8)
        dlg.wait_window()
        return result["value"]

    def _show_info(self, title, message):
        """自绘提示对话框"""
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(title)
        dlg.geometry("440x200")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=message, wraplength=390, justify="left",
                     font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT
                     ).pack(pady=(24, 18), padx=24)
        ctk.CTkButton(dlg, text="确定", command=dlg.destroy, fg_color=COLOR_PRIMARY,
                      hover_color=COLOR_PRIMARY_HOVER, corner_radius=8,
                      font=("Microsoft YaHei UI", 11), width=120).pack(pady=(0, 18))
        dlg.wait_window()

    # ── 用户对话框 ──────────────────────────────────
    def _dlg_gpu(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("选择显卡品牌")
        dlg.geometry("380x320")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="选择要清理的显卡驱动残留：",
                     font=("Microsoft YaHei UI", 12, "bold"), text_color=COLOR_TEXT
                     ).pack(pady=(18, 10))

        choices = [
            ("0", "跳过（不清理显卡残留）"),
            ("1", "NVIDIA"),
            ("2", "AMD"),
            ("3", "Intel 核显"),
            ("4", "全部清理"),
        ]
        var = ctk.StringVar(value=self.gpu_choice)
        for val, label in choices:
            ctk.CTkRadioButton(dlg, text=label, variable=var, value=val,
                               font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT,
                               fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER
                               ).pack(anchor="w", padx=36, pady=3)

        def confirm():
            self.gpu_choice = var.get()
            self._log("info", f"[i] 已选择显卡选项: {self.gpu_choice}")
            dlg.destroy()

        ctk.CTkButton(dlg, text="确定", command=confirm, fg_color=COLOR_PRIMARY,
                      hover_color=COLOR_PRIMARY_HOVER, corner_radius=8,
                      font=("Microsoft YaHei UI", 11), width=140).pack(pady=(14, 16))

    def _dlg_vm(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("配置虚拟内存")
        dlg.geometry("400x360")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="虚拟内存配置", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=COLOR_TEXT).pack(pady=(18, 10))

        enable_var = ctk.StringVar(value="y" if self.vm_enabled else "n")
        ctk.CTkRadioButton(dlg, text="手动设置虚拟内存", variable=enable_var, value="y",
                           font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT,
                           fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER
                           ).pack(anchor="w", padx=36, pady=3)
        ctk.CTkRadioButton(dlg, text="保持默认设置", variable=enable_var, value="n",
                           font=("Microsoft YaHei UI", 11), text_color=COLOR_TEXT,
                           fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER
                           ).pack(anchor="w", padx=36, pady=3)

        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="x", padx=36, pady=(12, 4))

        ctk.CTkLabel(form, text="目标盘符", font=("Microsoft YaHei UI", 10),
                     text_color=COLOR_TEXT_DIM).grid(row=0, column=0, sticky="w", pady=3)
        drive_entry = ctk.CTkEntry(form, width=120, font=("Microsoft YaHei UI", 11),
                                   fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER,
                                   corner_radius=6)
        drive_entry.grid(row=0, column=1, sticky="w", pady=3, padx=(10, 0))
        drive_entry.insert(0, self.vm_drive)

        ctk.CTkLabel(form, text="初始大小 MB", font=("Microsoft YaHei UI", 10),
                     text_color=COLOR_TEXT_DIM).grid(row=1, column=0, sticky="w", pady=3)
        vmin_entry = ctk.CTkEntry(form, width=120, font=("Microsoft YaHei UI", 11),
                                  fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER,
                                  corner_radius=6)
        vmin_entry.grid(row=1, column=1, sticky="w", pady=3, padx=(10, 0))
        vmin_entry.insert(0, self.vm_min)

        ctk.CTkLabel(form, text="最大大小 MB", font=("Microsoft YaHei UI", 10),
                     text_color=COLOR_TEXT_DIM).grid(row=2, column=0, sticky="w", pady=3)
        vmax_entry = ctk.CTkEntry(form, width=120, font=("Microsoft YaHei UI", 11),
                                  fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER,
                                  corner_radius=6)
        vmax_entry.grid(row=2, column=1, sticky="w", pady=3, padx=(10, 0))
        vmax_entry.insert(0, self.vm_max)

        def confirm():
            if enable_var.get() != "y":
                self.vm_enabled = False
                self._log("info", "[i] 已选择: 保持虚拟内存默认设置")
                dlg.destroy()
                return
            drive = drive_entry.get().strip().upper() or "D"
            vmin = vmin_entry.get().strip() or "4096"
            vmax = vmax_entry.get().strip() or "8192"
            if not (len(drive) == 1 and drive.isalpha()):
                self._log("yellow", "[!] 无效盘符，已取消虚拟内存配置")
                dlg.destroy()
                return
            if not (vmin.isdigit() and vmax.isdigit() and int(vmin) > 0 and int(vmax) > 0):
                self._log("yellow", "[!] 大小必须为正整数，已取消虚拟内存配置")
                dlg.destroy()
                return
            if int(vmax) < int(vmin):
                self._log("yellow", "[!] 最大值不能小于最小值，已取消虚拟内存配置")
                dlg.destroy()
                return
            self.vm_enabled = True
            self.vm_drive = drive
            self.vm_min = vmin
            self.vm_max = vmax
            self._log("info", f"[i] 虚拟内存: {self.vm_drive}盘 {self.vm_min}-{self.vm_max} MB")
            dlg.destroy()

        ctk.CTkButton(dlg, text="确定", command=confirm, fg_color=COLOR_PRIMARY,
                      hover_color=COLOR_PRIMARY_HOVER, corner_radius=8,
                      font=("Microsoft YaHei UI", 11), width=140).pack(pady=(14, 16))

    # ── 日志与 UI 更新 ──────────────────────────────
    def _log(self, color, text):
        self.log_text.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] ", "gray")
        self.log_text.insert("end", text + "\n", color)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_space(self):
        try:
            total, free = CleanC.get_disk_usage_gb("C:")
            if total <= 0:
                total = 256  # 兜底
            pct = max(0, min(100, int((1 - free / max(total, 1)) * 100)))

            if pct < 70:
                used_color = "#3b82f6"  # 蓝色：已用（与绿色可用区分）
            elif pct < 85:
                used_color = "#dcdcaa"  # 黄色：占用偏高
            else:
                used_color = COLOR_DANGER  # 红色：占用过高
            self._draw_space_bar(pct, used_color)
            self.legend_used.configure(fg_color=used_color)
            self.legend_free.configure(fg_color=COLOR_PRIMARY)

            self.lbl_space_big.configure(text=f"{free} GB")
            self.lbl_space_text.configure(text=f"C: {free} GB / ~{int(total)} GB")

            if self.before_free > 0:
                released = round(max(0, free - self.before_free), 2)
            else:
                released = 0
            self.lbl_space_delta.configure(
                text=f"清理前 {self.before_free} GB  |  本次释放 +{released} GB  |  当前 {free} GB"
            )
        except Exception:
            pass

    def _round_rect(self, canvas, x1, y1, x2, y2, r, **kw):
        """Canvas 圆角矩形"""
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
                  x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return canvas.create_polygon(points, smooth=True, **kw)

    def _draw_space_bar(self, pct, used_color):
        """绘制空间条：左侧=已用，右侧=可用（绿色）"""
        c = self.space_canvas
        c.delete("all")
        w = c.winfo_width()
        if w <= 1:
            w = 400  # 未布局完成时兜底
        h = 14
        r = 7
        # 背景整条为绿色（可用空间）
        self._round_rect(c, 0, 0, w, h, r, fill=COLOR_PRIMARY, outline="")
        # 左侧覆盖已用部分
        used_w = int(w * pct / 100)
        if used_w > 0:
            self._round_rect(c, 0, 0, used_w, h, r, fill=used_color, outline="")

    def _poll_log_queue(self):
        """轮询日志队列，更新 GUI"""
        cnt = 0
        while cnt < 20:
            try:
                msg_type, text = _log_queue.get_nowait()
                if msg_type == 'space_update':
                    try:
                        self.current_free = float(text)
                    except ValueError:
                        pass
                    self._update_space()
                else:
                    self._log(msg_type, text)
                cnt += 1
            except queue.Empty:
                break
        self.root.after(100, self._poll_log_queue)

    def _toggle_all(self, state):
        for var in self.stage_vars:
            var.set(1 if state else 0)

    def _copy_log(self):
        text = self.log_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.lbl_status.configure(text="日志已复制到剪贴板")
        self.root.after(3000, lambda: self.lbl_status.configure(text="就绪"))

    # ── 在线更新 ──────────────────────────────────
    def _check_update(self):
        """手动检查更新（后台线程，不卡界面）"""
        global _checking_update
        if _is_running:
            self._log("yellow", "清理进行中，请稍后再检查更新")
            return
        if _checking_update:
            self._log("yellow", "正在检查更新中，请稍候")
            return
        _checking_update = True
        self.btn_update.configure(state="disabled")
        self.lbl_status.configure(text="正在检查更新...")
        threading.Thread(target=self._check_update_worker, args=(False,), daemon=True).start()

    def _auto_check_update(self):
        """启动后自动检查更新（静默，仅发现新版本时提示）"""
        global _checking_update
        if _is_running or _checking_update:
            return
        _checking_update = True
        threading.Thread(target=self._check_update_worker, args=(True,), daemon=True).start()

    def _check_update_worker(self, auto=False):
        """后台线程：检查更新。auto=True 为启动自动检查，失败/无更新时静默"""
        try:
            result = updater.check_update()
            if result is None:
                if not auto:
                    self._log_via_queue("red", "检查更新失败：Gitee 和 GitHub 都连不上")
                    self._log_via_queue("gray", "请检查网络后重试")
                self._set_update_btn_ready()
                return
            source, um, info = result
            if source == "dev":
                if not auto:
                    self._log_via_queue("yellow", "当前为开发模式，打包安装后才能使用在线更新")
                self._set_update_btn_ready()
                return
            if info is None:
                if not auto:
                    self._log_via_queue("green", f"已是最新版本（{source} 源）")
                self._set_update_btn_ready()
                return
            new_ver = info.TargetFullRelease.Version
            if not auto:
                self._log_via_queue("cyan", f"发现新版本 {new_ver}（{source} 源）")
            self.root.after(0, lambda: self._ask_download(um, info))
        except Exception as e:
            if not auto:
                self._log_via_queue("red", f"检查更新出错：{e}")
            self._set_update_btn_ready()

    def _ask_download(self, um, info):
        """主线程：询问是否下载更新"""
        new_ver = info.TargetFullRelease.Version
        notes = info.TargetFullRelease.NotesMarkdown or ""
        msg = f"发现新版本 {new_ver}\n\n是否现在下载并安装？"
        if notes:
            msg += f"\n\n更新内容：\n{notes[:500]}"
        if self._ask_yes_no("发现新版本", msg):
            self.lbl_status.configure(text="正在下载更新...")
            threading.Thread(target=self._download_worker, args=(um, info), daemon=True).start()
        else:
            self._set_update_btn_ready()

    def _download_worker(self, um, info):
        """后台线程：下载更新"""
        try:
            def progress(*args):
                # 兼容不同参数格式：可能是百分比，也可能是 (已下载, 总大小)
                if len(args) == 1 and isinstance(args[0], (int, float)):
                    pct = int(args[0])
                    self._log_via_queue("gray", f"下载进度：{pct}%")
                elif len(args) >= 2:
                    done, total = args[0], args[1]
                    if total:
                        pct = int(done * 100 / total)
                        self._log_via_queue("gray", f"下载进度：{pct}%")
            updater.download_update(um, info, progress)
            self._log_via_queue("green", "下载完成，正在应用更新...")
            self.root.after(0, lambda: self._apply_update(um, info))
        except Exception as e:
            self._log_via_queue("red", f"下载更新失败：{e}")
            self._set_update_btn_ready()

    def _apply_update(self, um, info):
        """主线程：应用更新并重启"""
        if self._ask_yes_no("更新就绪", "更新已下载完成，是否立即重启程序完成更新？"):
            try:
                updater.apply_update(um, info)
            except Exception as e:
                self._log("red", f"应用更新失败：{e}")
                self._set_update_btn_ready()
        else:
            self._log("yellow", "更新已下载，下次启动时自动应用")
            self._set_update_btn_ready()

    def _set_update_btn_ready(self):
        """恢复检查更新按钮"""
        global _checking_update
        _checking_update = False
        self.root.after(0, lambda: (self.btn_update.configure(state="normal"),
                                    self.lbl_status.configure(text="就绪")))

    # ── 清理流程控制 ──────────────────────────────
    def _set_ui_running(self, running):
        global _is_running
        _is_running = running
        if running:
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.lbl_status.configure(text="正在清理...")
        else:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self._update_space()

    def _start_cleanup(self):
        if not CleanC.is_admin():
            self._show_info("权限不足", "请以管理员身份运行此程序！")
            return

        # 读取用户勾选的阶段
        selected = [v.get() == 1 for v in self.stage_vars]
        if not any(selected):
            self._log("yellow", "[!] 未选择任何清理阶段")
            return

        # 清空可能残留的预置输入，避免污染本次运行（上次停止/中断可能遗留）
        while not _input_queue.empty():
            try:
                _input_queue.get_nowait()
            except queue.Empty:
                break

        self._set_ui_running(True)
        _stop_flag.clear()
        CleanC.STOP_FLAG.clear()
        self.progress_bar.set(0)
        self.need_reboot = False

        # 清空旧日志（保留前 200 行标题）
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        self._log("magenta", "=" * 44)
        self._log("magenta", "  C盘深度清理工具")
        self._log("magenta", "  作者：-_Hex  本程序完全开源免费")
        self._log("magenta", "=" * 44)

        self.before_free = CleanC.get_free_space_gb("C:")
        self.current_free = self.before_free
        self.cleaned_total = 0
        self._log("gray", f"   [i] 清理前 C 盘剩余: {self.before_free} GB")
        CleanC.LOG_LINES.clear()
        CleanC.LOG_LINES.append(f"C盘清理开始，初始剩余 {self.before_free} GB")

        self._update_space()

        # 启动后台清理线程
        thread = threading.Thread(target=self._run_cleanup, args=(selected,), daemon=True)
        thread.start()

    def _stop_cleanup(self):
        _stop_flag.set()
        CleanC.STOP_FLAG.set()
        self._log("yellow", "[!] 正在停止...")
        self.lbl_status.configure(text="正在停止...")

    def _run_cleanup(self, selected):
        """后台线程：执行清理阶段"""
        global _is_running

        # 劫持输出
        _hijack_output()
        builtins.print = _gui_print
        builtins.input = _gui_input
        os.system = _gui_os_system
        CleanC.AUTO_MODE = True

        total_stages = sum(selected)
        completed = 0

        stage_funcs = [
            (CleanC.stage1_builtin,        "第一阶段", 1),
            (CleanC.stage2_hibernate,       "第二阶段", 2),
            (CleanC.stage3_gpu_drivers,     "第三阶段", 3),
            (CleanC.stage4_virtual_memory,  "第四阶段", 4),
            (CleanC.stage5_wiztree,         "第五阶段", 5),
            (CleanC.stage6_driver_store,    "第六阶段", 6),
            (CleanC.stage7_temp_cache,      "第七阶段", 7),
        ]

        for func, label, idx in stage_funcs:
            if _stop_flag.is_set():
                self._log_via_queue("yellow", "[!] 已停止")
                break
            if not selected[idx - 1]:
                continue

            # 阶段 3：按用户选择的显卡品牌清理（临时关闭 AUTO_MODE 让选择生效）
            if idx == 3:
                CleanC.AUTO_MODE = False
                _input_queue.put(self.gpu_choice)

            # 阶段 4：虚拟内存需要手动交互，暂时关闭 AUTO_MODE
            if idx == 4 and self.vm_enabled:
                CleanC.AUTO_MODE = False
                _input_queue.put("y")        # 是否手动设置
                _input_queue.put(self.vm_drive)
                _input_queue.put(self.vm_min)
                _input_queue.put(self.vm_max)
                _input_queue.put("y")        # 确认应用
            elif idx == 4:
                CleanC.AUTO_MODE = True

            try:
                result = func()
                self.need_reboot |= bool(result)
            except Exception as e:
                _log_queue.put(('red', f"   [X] {label} 执行异常: {e}"))

            # 阶段 3 结束后恢复自动模式，避免影响后续阶段
            if idx == 3:
                CleanC.AUTO_MODE = True

            # 显示空间变化
            self.current_free = CleanC.get_free_space_gb("C:")
            delta = round(self.current_free - (self.before_free + self.cleaned_total), 2)
            if delta >= 0.01:
                _log_queue.put(('green', f"      {label} 释放 +{delta} GB"))
                self.cleaned_total += delta
            _log_queue.put(('space_update', str(self.current_free)))

            completed += 1
            self.progress_value = int(completed / max(total_stages, 1) * 100)
            self.root.after(0, lambda v=self.progress_value: self.progress_bar.set(v / 100))

        # 结束
        CleanC.write_clean_log()
        total_released = round(max(0, self.current_free - self.before_free), 2)
        _log_queue.put(('green', f"\n  全部完成！共释放约 {total_released} GB"))
        if self.need_reboot:
            _log_queue.put(('yellow', "\n  [!] 虚拟内存配置已修改，请手动重启计算机以生效。"))

        # 手动命令确认（在 GUI 线程中展示）
        if CleanC.MANUAL_COMMANDS:
            self.root.after(500, self._show_manual_commands)

        # 恢复原始函数
        builtins.print = _original_print
        builtins.input = _original_input
        os.system = _original_os_system

        self.root.after(0, lambda: self._set_ui_running(False))
        self.root.after(0, lambda: self.lbl_status.configure(
            text=f"完成 — 释放 {total_released} GB"
        ))

    def _log_via_queue(self, color, text):
        _log_queue.put((color, text))

    def _run_manual_cleanup(self, selected):
        """后台线程静默执行手动清理项，进度写入日志区，完成后弹提示"""
        total = len(selected)
        self._log_via_queue(COLOR_PRIMARY, f"开始执行 {total} 项清理操作...")
        for i, cmd in enumerate(selected, 1):
            self._log_via_queue(COLOR_TEXT, f"[{i}/{total}] 正在执行: {cmd['title']}")
            try:
                CleanC.run_cmd(cmd["command"], capture=True, wait=True)
                self._log_via_queue(COLOR_PRIMARY, f"完成: {cmd['title']}")
            except Exception as e:
                self._log_via_queue("#e06c75", f"失败: {cmd['title']} ({e})")
        self._log_via_queue(COLOR_PRIMARY, "全部操作已完成")
        self.after(0, lambda: self._show_info("完成", "全部操作已执行完成，详见日志区。"))

    def _open_manual_path(self, path):
        """打开手动清理项的目标文件夹（自动展开环境变量、跳过通配符段）"""
        import os
        p = os.path.expandvars(path)
        # 逐级向上找最深的已存在目录（路径含 * 通配符时）
        while p and not os.path.isdir(p):
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
        if p and os.path.isdir(p):
            os.startfile(p)
        else:
            self._show_info("提示", "未找到目标文件夹")

    def _show_manual_commands(self):
        """在 GUI 内展示手动命令确认对话框"""
        commands = CleanC.MANUAL_COMMANDS
        if not commands:
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("待执行操作确认")
        dlg.geometry("760x560")
        dlg.minsize(560, 360)
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="以下操作建议执行：", font=("Microsoft YaHei UI", 13, "bold"),
                     text_color=COLOR_TEXT).pack(pady=(14, 6), padx=20, anchor="w")

        scroll = ctk.CTkScrollableFrame(dlg, fg_color=COLOR_CARD, corner_radius=8,
                                        border_width=1, border_color=COLOR_BORDER)
        scroll.pack(fill="both", expand=True, padx=16, pady=6)

        vars_list = []
        last_cat = ""
        for cmd in commands:
            var = ctk.BooleanVar(value=True)
            vars_list.append(var)
            if cmd["category"] != last_cat:
                last_cat = cmd["category"]
                ctk.CTkLabel(scroll, text=f"▎{last_cat}", font=("Microsoft YaHei UI", 11, "bold"),
                             text_color=COLOR_PRIMARY).pack(pady=(8, 2), anchor="w")
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", anchor="w", pady=2, padx=8)
            ctk.CTkCheckBox(row, text=cmd["title"], variable=var,
                            font=("Microsoft YaHei UI", 10), text_color=COLOR_TEXT,
                            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                            corner_radius=6).pack(side="left")
            _path = cmd.get("path", "")
            if _path:
                ctk.CTkButton(row, text="打开文件夹", width=88, height=24,
                              command=lambda p=_path: self._open_manual_path(p),
                              fg_color=COLOR_CARD_ALT, hover_color="#3a3d44",
                              corner_radius=6, font=("Microsoft YaHei UI", 9)
                              ).pack(side="left", padx=(8, 0))
            _note = cmd["description"].split("。", 1)[1] if "。" in cmd["description"] else ""
            if _note:
                ctk.CTkLabel(row, text=_note, font=("Microsoft YaHei UI", 9),
                             text_color=COLOR_TEXT_DIM).pack(side="left", padx=(8, 0))

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=10)

        def do_execute():
            selected = [commands[i] for i, v in enumerate(vars_list) if v.get()]
            if not selected:
                self._show_info("提示", "未选择任何操作")
                return
            dlg.destroy()
            threading.Thread(target=self._run_manual_cleanup,
                             args=(selected,), daemon=True).start()

        select_all_var = ctk.BooleanVar(value=True)
        def toggle_all():
            val = select_all_var.get()
            for v in vars_list:
                v.set(val)

        ctk.CTkCheckBox(btn_frame, text="全选", variable=select_all_var, command=toggle_all,
                        font=("Microsoft YaHei UI", 10), text_color=COLOR_TEXT,
                        fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER
                        ).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="跳过", command=dlg.destroy,
                      fg_color=COLOR_CARD_ALT, hover_color="#3a3d44", corner_radius=8,
                      font=("Microsoft YaHei UI", 11)).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="执行选中项", command=do_execute,
                      fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, corner_radius=8,
                      font=("Microsoft YaHei UI", 11, "bold")).pack(side="right", padx=5)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    # ── 启动 ──────────────────────────────────────
    def run(self):
        if not CleanC.is_admin():
            self._show_info("权限不足", "请以管理员身份运行此程序！\n\n右键 exe → 以管理员身份运行")
            return
        # 启动 1.5 秒后自动检查更新（静默，发现新版本才提示）
        self.root.after(1500, self._auto_check_update)
        self.root.mainloop()


if __name__ == "__main__":
    updater.init_velopack()
    gui = CleanCGUI()
    gui.run()
