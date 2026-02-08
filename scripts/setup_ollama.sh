#!/bin/bash
# Ollama 安装和配置脚本

set -e

echo "🚀 Setting up Ollama (Free Local LLM)"
echo ""

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# 1. 安装 Ollama
if ! command -v ollama &> /dev/null; then
    echo "📥 Installing Ollama..."
    
    if [ "$OS" == "linux" ]; then
        curl -fsSL https://ollama.com/install.sh | sh
    elif [ "$OS" == "macos" ]; then
        echo "Please install Ollama from: https://ollama.com/download"
        echo "Or use: brew install ollama"
        exit 0
    fi
    
    echo "✓ Ollama installed"
else
    echo "✓ Ollama already installed"
fi

# 2. 启动 Ollama 服务（后台）
echo ""
echo "🔄 Starting Ollama service..."
if [ "$OS" == "linux" ]; then
    # 作为系统服务启动
    if command -v systemctl &> /dev/null; then
        sudo systemctl start ollama
        sudo systemctl enable ollama
        echo "✓ Ollama service started (systemd)"
    else
        # 后台启动
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        echo "✓ Ollama service started (background)"
    fi
elif [ "$OS" == "macos" ]; then
    ollama serve > /tmp/ollama.log 2>&1 &
    echo "✓ Ollama service started"
fi

sleep 3  # 等待服务启动

# 3. 拉取推荐模型
echo ""
echo "📦 Downloading recommended models..."
echo ""

# 中文优化模型（推荐）
echo "1/3: Downloading qwen2.5:14b (中文优化，14GB)..."
ollama pull qwen2.5:14b

# 轻量级模型（快速测试）
echo "2/3: Downloading qwen2.5:7b (轻量级，4.7GB)..."
ollama pull qwen2.5:7b

# 英文模型（可选）
echo "3/3: Downloading llama3.1:8b (英文优化，4.7GB)..."
ollama pull llama3.1:8b

# 4. 测试连接
echo ""
echo "🧪 Testing Ollama connection..."
response=$(curl -s http://localhost:11434/api/generate \
    -d '{
        "model": "qwen2.5:7b",
        "prompt": "你好",
        "stream": false
    }')

if [ $? -eq 0 ]; then
    echo "✓ Ollama is working!"
else
    echo "❌ Ollama connection failed"
    exit 1
fi

# 5. 显示模型列表
echo ""
echo "📋 Installed models:"
ollama list

echo ""
echo "================================================"
echo "✅ Ollama Setup Complete!"
echo "================================================"
echo ""
echo "📖 Usage:"
echo "  - Default model: qwen2.5:14b (best quality)"
echo "  - Fast model: qwen2.5:7b (faster, lower quality)"
echo "  - English model: llama3.1:8b"
echo ""
echo "🔧 Commands:"
echo "  - Check status: ollama list"
echo "  - Stop service: sudo systemctl stop ollama"
echo "  - View logs: tail -f /tmp/ollama.log"
echo ""
echo "💡 Test in Python:"
echo "  python -c \"import requests; print(requests.post('http://localhost:11434/api/generate', json={'model': 'qwen2.5:7b', 'prompt': '你好', 'stream': False}).json())\""
echo ""
