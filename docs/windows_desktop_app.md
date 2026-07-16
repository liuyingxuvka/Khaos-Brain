# Windows Desktop App

## 中文

这个桌面入口只是可选的卡片浏览器。Chaos Brain 的检索、反馈、Sleep、Dream、系统更新和升级验收全部可由 AI 自动完成，不依赖人阅读文件或打开这个界面。

推荐的人类入口有三层：

- 明确使用当前源码入口：`python scripts/open_khaos_brain_ui.py --repo-root . --runtime source`
- 打包后打开：双击 `dist/KhaosBrain.exe`，或通过下面的桌面快捷方式打开。
- 让 Codex 打开：使用 `$khaos-brain-open-ui`。

### 打包 exe

第一次打包前安装 PyInstaller：

```powershell
python -m pip install --user pyinstaller
```

然后构建：

```powershell
python scripts/build_desktop_exe.py --repo-root . --json
```

构建结果是：

```text
dist/KhaosBrain.exe
```

这个 exe 只打包桌面查看器代码和公开 UI 图标资源。它不会把 `kb/private/`、`kb/history/`、`kb/candidates/` 或任何真实经验卡片封进二进制。运行时仍然通过 `--repo-root` 读取当前仓库里的文件型 KB。

### 创建桌面快捷方式

```powershell
python scripts/install_desktop_shortcut.py --repo-root . --runtime release --json
```

快捷方式只绑定明确选择的当前入口。`--runtime release` 精确要求 `dist/KhaosBrain.exe`；文件不存在就失败，不会改走 Python。开发环境如确实需要源码快捷方式，必须明确使用 `--runtime source`。默认不传语言参数，让应用沿用 UI 中保存的显示语言；需要固定语言时可以加 `--language en` 或 `--language zh-CN`。

显示语言只影响桌面 UI。`--json` 检查、安装器、维护自动化和 GitHub 自动化输出默认是稳定的机器 JSON，不要求 Windows 控制台先切换到 UTF-8。

## English

The desktop entry is an optional card browser. Chaos Brain retrieval, feedback, Sleep, Dream, system update, and upgrade validation run automatically and do not depend on a person reading files or opening this UI.

Recommended human entry points:

- Select the current source entry explicitly: `python scripts/open_khaos_brain_ui.py --repo-root . --runtime source`
- Open after packaging: double-click `dist/KhaosBrain.exe`, or use the desktop shortcut below.
- Ask Codex to open it: use `$khaos-brain-open-ui`.

### Build the exe

Install PyInstaller once:

```powershell
python -m pip install --user pyinstaller
```

Build:

```powershell
python scripts/build_desktop_exe.py --repo-root . --json
```

Output:

```text
dist/KhaosBrain.exe
```

The exe bundles only viewer code and public UI icon assets. It does not bundle `kb/private/`, `kb/history/`, `kb/candidates/`, or real memory cards. At runtime it still reads the file-based KB from `--repo-root`.

### Create a desktop shortcut

```powershell
python scripts/install_desktop_shortcut.py --repo-root . --runtime release --json
```

The shortcut binds exactly one selected current entry. `--runtime release` requires the exact `dist/KhaosBrain.exe` path and fails if it is missing; it never switches to Python. A development source shortcut must be requested explicitly with `--runtime source`. By default the shortcut omits the language argument so the app can use the saved display setting; pass `--language en` or `--language zh-CN` only when a fixed language is needed.

The display language affects the desktop UI only. `--json` checks, installer output, maintenance automation, and GitHub automation output use stable machine JSON and do not require switching the Windows console to UTF-8 first.
