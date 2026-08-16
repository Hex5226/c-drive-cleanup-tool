# CleanC - C盘深度清理工具 v3.2.2

Windows C 盘空间深度清理工具，内置 WizTree 磁盘分析。

作者：-_Hex  |  完全开源免费

## 功能概览

- **第一阶段**：Windows 内置清理（DISM 组件清理 + 系统映像修复）
- **第二阶段**：休眠文件清理（关闭休眠释放 hiberfil.sys）
- **第三阶段**：显卡驱动安装残留清理（NVIDIA / AMD / Intel）
- **第四阶段**：虚拟内存配置优化（迁移到其他盘符）
- **第五阶段**：WizTree 空间分析（图形化展示磁盘占用）
- **第六阶段**：驱动仓库空间分析（识别可删除的旧版本驱动）
- **第七阶段**：临时文件与缓存深度清理（Temp / Prefetch / 更新缓存 / 浏览器缓存 / 着色器缓存等 30+ 类）

## 运行要求

- Windows 10 / 11
- 管理员权限
- Python 3.11+（源码运行）或直接使用 exe 版本

## 运行方式

### GUI 版本
```
python CleanC_GUI.py
```

### 命令行版本
```
python CleanC.py
```

## 打包为 exe

```
pip install pyinstaller
# onedir 打包（Velopack 在线更新要求 onedir，不能用 onefile）
pyinstaller --clean --noconfirm CleanC_onedir.spec
# 再运行 vpk pack 生成安装包/更新包（见 一键打包.ps1）
```

打包后需将 WizTree 放入 `CleanC_Project\WizTree\` 目录下，或首次运行时自动下载。

## 免责声明

本工具对系统文件进行操作，使用前请备份重要数据。作者不对因使用本工具造成的任何数据丢失承担责任。

## 开源协议

MIT License
