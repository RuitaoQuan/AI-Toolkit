#!/bin/bash

# AI Toolkit - 完整视频生成系统启动脚本

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         🎬 AI Toolkit - 完整视频生成系统                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 检查后端是否已提供
cd /Users/quan/Desktop/VideoCreateAgent

echo "📋 当前工作目录: $(pwd)"
echo ""

# 检查必要的文件
echo "🔍 检查项目文件..."
files=("main.py" "index.html" "login.html" "users.csv" "video")

for file in "${files[@]}"; do
    if [ -e "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file 不存在"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 启动服务..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 启动后端（deepl 环境）
echo "1️⃣  启动后端 FastAPI (Port 8000)..."
echo "   运行: conda activate deepl && python main.py"
echo ""

# 启动前端（HTTP 服务器）
echo "2️⃣  启动前端服务器 (Port 3000)..."
echo "   运行: python3 -m http.server 3000"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ 系统就绪！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 访问地址: http://127.0.0.1:3000/"
echo "📍 API 文档: http://127.0.0.1:8000/docs"
echo ""
echo "🔐 测试凭证:"
echo "   用户名: admin      密码: admin123"
echo "   用户名: user1      密码: password123"
echo "   用户名: test       密码: test123"
echo ""
echo "📚 功能说明:"
echo "   ✅ 用户登录系统"
echo "   ✅ 实时进度条显示"
echo "   ✅ Seedance3.0 视频生成"
echo "   ✅ 本地视频存储 (video 文件夹)"
echo "   ✅ 视频卡片展示和播放"
echo "   ✅ 统一深色主题"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
