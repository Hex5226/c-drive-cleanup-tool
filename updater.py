# -*- coding: utf-8 -*-
"""
CleanC 在线更新模块 (Velopack)
主源: Gitee  备源: GitHub
Gitee 连不上时自动切 GitHub，两个都失败才报错
"""

import velopack
from velopack import App, UpdateManager, GiteaSource, GithubSource

# ── 更新源配置 ──────────────────────────────
# 注册好 Gitee / GitHub 后，把下面两个地址改成你自己的仓库
GITEE_REPO = "https://gitee.com/Hex5226/c-drive-cleanup-tool"
GITHUB_REPO = "https://github.com/Hex5226/c-drive-cleanup-tool"


def init_velopack():
    """程序启动时调用一次，处理 Velopack 的安装/更新参数"""
    try:
        App().run()
    except Exception:
        pass


def get_current_version():
    """读当前版本号，读不到就返回 0.0.0"""
    try:
        um = UpdateManager(GiteaSource(GITEE_REPO))
        return um.get_current_version()
    except Exception:
        return "0.0.0"


def check_update():
    """检查更新。
    返回 (源名, UpdateManager, UpdateInfo 或 None)：
      - 有更新: info 不为 None
      - 无更新: info 为 None
      - 开发模式(未安装): 返回 ("dev", None, None)
      - 所有源都失败: 返回 None
    """
    sources = [
        ("Gitee", GiteaSource(GITEE_REPO)),
        ("GitHub", GithubSource(GITHUB_REPO)),
    ]
    for name, source in sources:
        try:
            um = UpdateManager(source)
            info = um.check_for_updates()
            return name, um, info
        except RuntimeError as e:
            # 未安装(开发模式直接跑源码)时 Velopack 找不到 manifest
            if "not properly installed" in str(e):
                return "dev", None, None
            continue
        except Exception:
            continue
    return None


def download_update(um, info, progress_callback=None):
    """下载更新包，progress_callback 可选，用于显示进度"""
    um.download_updates(info, progress_callback)


def apply_update(um, info):
    """应用更新并自动重启程序"""
    um.apply_updates_and_restart(info)
