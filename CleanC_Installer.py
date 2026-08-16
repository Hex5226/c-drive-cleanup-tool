# -*- coding: utf-8 -*-
"""
CleanC 安装向导
- 启动时检测非 C 盘固定磁盘，默认安装路径为第一个非系统盘下的 CleanC 目录（如 D:\CleanC）
- GUI 提供路径输入框 + 浏览按钮 + 安装/关闭按钮 + 进度条
- 点安装后把内嵌的 CleanC-win-Setup.exe 复制到临时目录，
  调用 "Setup.exe --silent --installto 目标路径" 执行安装，等待完成并提示结果
- 全程不弹任何 PowerShell/cmd 控制台窗口（所有 subprocess 均加 CREATE_NO_WINDOW）
- 窗口左上角/任务栏图标使用内嵌的 CleanC.ico（--add-data 打包进 exe）
"""
import base64
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "CleanC"
SETUP_EXE_NAME = "CleanC-win-Setup.exe"
ICON_NAME = "CleanC.ico"

DRIVE_FIXED = 3  # DRIVE_FIXED = 固定磁盘

# 0x08000000：不创建控制台窗口（隐藏所有 PowerShell/cmd 黑框）
CREATE_NO_WINDOW = 0x08000000


def get_fixed_drives():
    """返回所有固定磁盘盘符列表（如 ['C:', 'D:', 'E:']）"""
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            letter = chr(ord('A') + i)
            root = f"{letter}:\\"
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
            if drive_type == DRIVE_FIXED:
                drives.append(f"{letter}:")
    return drives


def default_install_path():
    """默认安装路径：第一个非 C 盘固定磁盘下的 CleanC 目录"""
    for drive in get_fixed_drives():
        if drive.upper() != "C:":
            return f"{drive}\\{APP_NAME}"
    return f"C:\\{APP_NAME}"


def resource_path(relative):
    """PyInstaller 打包后内嵌资源路径（--add-data/--add-binary 放入 _MEIPASS 根目录）"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


class InstallerApp:
    def __init__(self, root):
        self.root = root
        root.title("CleanC 安装向导")
        root.resizable(False, False)

        # 窗口图标：左上角 + 任务栏（打包时 --add-data 内嵌 CleanC.ico）
        try:
            root.iconbitmap(resource_path(ICON_NAME))
        except Exception:
            pass  # 图标缺失时保持默认，不阻塞启动

        main = tk.Frame(root, padx=20, pady=20)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="CleanC 安装向导",
                 font=("Microsoft YaHei", 14, "bold")).pack(anchor="w")
        tk.Label(main, text="选择安装目录，点击“安装”开始安装。",
                 font=("Microsoft YaHei", 9), fg="#666666").pack(anchor="w", pady=(4, 12))

        # 路径选择行
        path_row = tk.Frame(main)
        path_row.pack(fill="x")
        tk.Label(path_row, text="安装路径：", font=("Microsoft YaHei", 10)).pack(side="left")
        self.path_var = tk.StringVar(value=default_install_path())
        self.path_entry = tk.Entry(path_row, textvariable=self.path_var,
                                   width=38, font=("Microsoft YaHei", 10))
        self.path_entry.pack(side="left", padx=(0, 6))
        tk.Button(path_row, text="浏览...", command=self.browse, width=8).pack(side="left")

        # 选项行
        opt_row = tk.Frame(main)
        opt_row.pack(fill="x", pady=(10, 0))
        self.shortcut_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt_row, text="创建桌面和开始菜单快捷方式", variable=self.shortcut_var,
                       font=("Microsoft YaHei", 9)).pack(anchor="w")
        tk.Checkbutton(opt_row, text="安装成功后打开 CleanC", variable=self.launch_var,
                       font=("Microsoft YaHei", 9)).pack(anchor="w")

        # 进度条（安装过程中显示，完成后隐藏）
        self.progress = ttk.Progressbar(main, mode="indeterminate", length=360)
        self.progress.pack(fill="x", pady=(12, 0))

        # 按钮行
        btn_row = tk.Frame(main)
        btn_row.pack(fill="x", pady=(14, 0))
        self.install_btn = tk.Button(btn_row, text="安装", command=self.start_install,
                                     width=10, bg="#4CAF50", fg="white")
        self.install_btn.pack(side="right", padx=(8, 0))
        # 关闭按钮：安装过程中禁用，安装完成后可用
        self.close_btn = tk.Button(btn_row, text="关闭", command=self.root.destroy,
                                   width=10, state="disabled")
        self.close_btn.pack(side="right")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(main, textvariable=self.status_var, font=("Microsoft YaHei", 9),
                 fg="#333333", anchor="w").pack(fill="x", pady=(10, 0))

    def browse(self):
        path = filedialog.askdirectory(title="选择安装目录",
                                       initialdir=self.path_var.get() or "C:\\")
        if path:
            self.path_var.set(path)

    def start_install(self):
        target = self.path_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "请先选择安装路径")
            return
        # 校验：不能是盘符根目录
        if len(target) <= 3 or target.endswith(":\\"):
            messagebox.showwarning("提示", "不能安装到磁盘根目录，请选择子目录，例如 D:\\CleanC")
            return
        # 安装期间锁定界面：禁用安装/关闭按钮、路径输入、浏览、勾选框
        self.install_btn.config(state="disabled")
        self.close_btn.config(state="disabled")
        self.path_entry.config(state="disabled")
        self.progress.start(12)
        create_shortcuts = self.shortcut_var.get()
        launch_app = self.launch_var.get()
        threading.Thread(target=self._do_install,
                         args=(target, create_shortcuts, launch_app), daemon=True).start()

    def _do_install(self, target, create_shortcuts, launch_app):
        """后台线程执行安装；所有 UI 更新/弹窗均通过 root.after 回到主线程"""
        try:
            self._set_status("正在准备安装程序...")
            setup_src = resource_path(SETUP_EXE_NAME)
            if not os.path.isfile(setup_src):
                self._show_error(f"未找到内嵌安装程序：{SETUP_EXE_NAME}")
                return

            # 复制内嵌 Setup.exe 到临时目录
            tmp_dir = tempfile.mkdtemp(prefix="cleanc_install_")
            setup_tmp = os.path.join(tmp_dir, SETUP_EXE_NAME)
            self._set_status("正在复制安装程序到临时目录...")
            shutil.copy2(setup_src, setup_tmp)

            # 确保目标目录存在
            os.makedirs(target, exist_ok=True)

            self._set_status("正在执行安装，请稍候...")
            cmd = [setup_tmp, "--silent", "--installto", target]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True,
                                    creationflags=CREATE_NO_WINDOW)
            try:
                stdout, stderr = proc.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self._show_error("安装超时（180 秒）。请检查安装程序是否被安全软件拦截，或目标路径是否可写。")
                return
            shutil.rmtree(tmp_dir, ignore_errors=True)

            if proc.returncode == 0:
                # 安装本身成功：先弹"安装完成"提示（不因后续步骤失败而误报安装失败）
                self._set_status("安装完成")
                self.root.after(0, lambda: messagebox.showinfo(
                    "安装完成", f"CleanC 已成功安装到：\n{target}"))

                # 后续可选步骤：各自独立捕获，失败只提示、不影响"安装成功"结论
                if create_shortcuts:
                    self._set_status("正在创建快捷方式...")
                    try:
                        self._create_shortcuts(target)
                    except Exception as e:
                        self._set_status("安装完成（快捷方式创建失败）")
                        self.root.after(0, lambda: messagebox.showwarning(
                            "提示", f"安装已完成，但创建快捷方式失败：\n{e}"))
                if launch_app:
                    self._set_status("正在启动 CleanC...")
                    try:
                        self._launch_app(target)
                    except Exception as e:
                        self._set_status("安装完成（启动应用失败）")
                        self.root.after(0, lambda: messagebox.showwarning(
                            "提示", f"安装已完成，但启动 CleanC 失败：\n{e}"))
            else:
                self._set_status("安装失败")
                self.root.after(0, lambda: messagebox.showerror(
                    "安装失败", f"安装程序返回错误码 {proc.returncode}\n{stderr}"))
        except Exception as e:
            self._set_status("安装失败")
            self.root.after(0, lambda: messagebox.showerror("安装失败", str(e)))
        finally:
            # 安装结束：恢复界面，进度条停止，关闭按钮可用（用户可点关闭退出）
            self.root.after(0, self._finish_install)

    def _finish_install(self):
        """安装流程结束后的界面恢复（主线程执行）"""
        self.progress.stop()
        self.path_entry.config(state="normal")
        self.install_btn.config(state="normal")
        self.close_btn.config(state="normal")

    def _create_shortcuts(self, target):
        """用 PowerShell -EncodedCommand 创建桌面和开始菜单快捷方式（UTF-16LE Base64，避免中文乱码）"""
        exe_path = os.path.join(target, "CleanC.exe")
        if not os.path.isfile(exe_path):
            return
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        start_menu = os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                                  "Microsoft", "Windows", "Start Menu", "Programs")

        # 路径可能含单引号：PowerShell 单引号字符串内用 '' 转义
        def ps_quote(p):
            return p.replace("'", "''")

        ps_script = (
            "$ws = New-Object -ComObject WScript.Shell;"
            f"$s1 = $ws.CreateShortcut('{ps_quote(desktop)}\\CleanC.lnk');"
            f"$s1.TargetPath = '{ps_quote(exe_path)}';$s1.Save();"
            f"$s2 = $ws.CreateShortcut('{ps_quote(start_menu)}\\CleanC.lnk');"
            f"$s2.TargetPath = '{ps_quote(exe_path)}';$s2.Save();"
        )
        encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("ascii")
        subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded],
                       capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)

    def _launch_app(self, target):
        """启动安装目录下的 CleanC.exe（CleanC 已 uac_admin，会自动弹 UAC）"""
        exe_path = os.path.join(target, "CleanC.exe")
        if os.path.isfile(exe_path):
            subprocess.Popen([exe_path], creationflags=CREATE_NO_WINDOW)

    def _set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def _show_error(self, text):
        self._set_status("安装失败")
        self.root.after(0, lambda: messagebox.showerror("安装失败", text))
        self.root.after(0, self._finish_install)


def main():
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
