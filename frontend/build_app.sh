#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

APP_NAME="F50Monitor"
APP_DIR="${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"

echo "=== 正在构建 macOS App 包 ==="

# 清理旧的 app
rm -rf "${APP_DIR}"
mkdir -p "${MACOS_DIR}"

echo "1. 编译 Swift 前端 (直连 192.168.0.1:9090)..."
swiftc main.swift -o ${APP_NAME}
if [ $? -ne 0 ]; then
    echo "Swift 前端编译失败！"
    exit 1
fi
# 将 Swift 产物放入 MacOS 目录
mv ${APP_NAME} "${MACOS_DIR}/"

echo "2. 生成 Info.plist..."
cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>F50Monitor</string>
    <key>CFBundleIdentifier</key>
    <string>com.bear.F50Monitor</string>
    <key>CFBundleName</key>
    <string>F50Monitor</string>
    <key>CFBundleDisplayName</key>
    <string>F50状态</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
EOF

echo "=== 构建完成！ ==="

# 3. 拷贝图标
if [ -f "AppIcon.icns" ]; then
    mkdir -p "$APP_DIR/Contents/Resources"
    cp AppIcon.icns "$APP_DIR/Contents/Resources/"
fi

# 4. 刷新图标缓存
touch "$APP_DIR"
echo "Mac 客户端构建成功！位于：${DIR}/${APP_DIR}"
echo "请确保面具模块已经在 F50 上安装并运行。"
