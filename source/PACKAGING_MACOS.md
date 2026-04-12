# macOS 打包说明

本文档说明如何在 macOS 上构建和打包 DocTranslationTool。

## 前置要求

1. **Python 3.10+**
   ```bash
   python3 --version
   ```

2. **安装依赖**
   ```bash
   python3 -m pip install -e ".[build]"
   ```

## 构建步骤

### 1. 运行构建脚本

```bash
cd /path/to/doc_translation_tool_source\ 2/source
bash scripts/build_macos.sh
```

或者指定特定的 Python 版本：

```bash
PYTHON=/usr/local/bin/python3.11 bash scripts/build_macos.sh
```

### 2. 构建产物

构建完成后，会生成以下内容：

- `../releases/macos/DocTranslationTool/` - 发布目录
  - `DocTranslationTool.app` - macOS 应用程序包（双击启动）
  - `.env` - 配置文件（需要编辑 API 密钥）
  - 文档文件（README.md、使用指南.md 等）

- `../releases/macos/DocTranslationTool-macos.zip` - 压缩包（用于分发）

### 3. 测试应用

```bash
# 直接运行 .app
open ../releases/macos/DocTranslationTool/DocTranslationTool.app

# 或者从命令行运行（可以看到日志输出）
../releases/macos/DocTranslationTool/DocTranslationTool.app/Contents/MacOS/DocTranslationTool
```

## 从源码运行（开发模式）

如果不需要打包，可以直接从源码运行：

```bash
# 安装依赖
python3 -m pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API 密钥

# 运行应用
python3 app.py
```

## 常见问题

### PyInstaller 未安装

```bash
python3 -m pip install pyinstaller
```

### 权限问题

如果遇到权限错误，确保脚本有执行权限：

```bash
chmod +x scripts/build_macos.sh
```

### 应用无法打开（安全提示）

macOS 可能会阻止未签名的应用。解决方法：

1. 右键点击 `DocTranslationTool.app`
2. 选择"打开"
3. 在弹出的对话框中点击"打开"

或者使用命令行：

```bash
xattr -cr ../releases/macos/DocTranslationTool/DocTranslationTool.app
```

### PySide6 相关错误

确保安装了完整的 PySide6：

```bash
pip3 install --upgrade PySide6
```

## 构建脚本说明

`scripts/build_macos.sh` 执行以下操作：

1. 清理旧的构建产物
2. 使用 PyInstaller 构建 .app 包
3. 复制配置文件和文档
4. 精简 Qt 翻译文件（只保留中英文）
5. 移除不需要的 Qt 插件（减小体积）
6. 创建最终的发布目录和压缩包

## 分发

将 `../releases/macos/DocTranslationTool-macos.zip` 分发给用户，用户解压后：

1. 双击 `DocTranslationTool.app` 启动应用
2. 编辑 `.env` 文件配置 API 密钥
3. 参考 `使用指南.md` 使用工具

## 代码签名（可选）

如果需要分发给更多用户，建议进行代码签名：

```bash
# 需要 Apple Developer 账号和证书
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  ../releases/macos/DocTranslationTool/DocTranslationTool.app
```

## 创建 DMG 安装包（可选）

可以使用 `create-dmg` 工具创建更专业的安装包：

```bash
# 安装 create-dmg
brew install create-dmg

# 创建 DMG
create-dmg \
  --volname "DocTranslationTool" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --app-drop-link 450 185 \
  "../releases/macos/DocTranslationTool.dmg" \
  "../releases/macos/DocTranslationTool/"
```
