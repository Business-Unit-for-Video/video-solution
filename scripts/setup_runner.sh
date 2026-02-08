#!/bin/bash
# GPU Self-Hosted Runner Setup Script

set -e

echo "🚀 Setting up GitHub Actions Self-Hosted Runner with GPU support"

# 检查是否有 root 权限
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root (sudo)"
    exit 1
fi

# 1. 安装 NVIDIA Driver 和 CUDA（如果未安装）
echo "📦 Installing NVIDIA Driver and CUDA Toolkit..."
if ! command -v nvidia-smi &> /dev/null; then
    ubuntu-drivers devices
    ubuntu-drivers autoinstall
    
    # 安装 CUDA Toolkit
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
    dpkg -i cuda-keyring_1.1-1_all.deb
    apt-get update
    apt-get install -y cuda-toolkit-12-1
    
    echo "✓ NVIDIA Driver installed. Please reboot and run this script again."
    exit 0
fi

# 2. 安装系统依赖
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y \
    curl \
    jq \
    git \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev

# 3. 创建 runner 用户
if ! id "runner" &>/dev/null; then
    useradd -m -s /bin/bash runner
    usermod -aG docker runner  # 如果使用 Docker
    echo "✓ Created runner user"
fi

# 4. 下载并配置 GitHub Actions Runner
RUNNER_VERSION="2.313.0"  # 更新到最新版本
RUNNER_DIR="/home/runner/actions-runner"

sudo -u runner mkdir -p $RUNNER_DIR
cd $RUNNER_DIR

echo "📥 Downloading GitHub Actions Runner..."
sudo -u runner curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
    -L https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

sudo -u runner tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# 5. 配置 Runner（需要手动提供 token）
echo ""
echo "================================================"
echo "🔑 Runner Configuration"
echo "================================================"
echo ""
echo "To configure the runner, you need:"
echo "1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/settings/actions/runners/new"
echo "2. Copy the token"
echo "3. Run as 'runner' user:"
echo ""
echo "   cd $RUNNER_DIR"
echo "   ./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN --labels self-hosted,gpu,cuda"
echo ""
echo "4. Install as a service:"
echo "   sudo ./svc.sh install runner"
echo "   sudo ./svc.sh start"
echo ""

# 6. 安装 Python 依赖
echo "📦 Installing Python dependencies..."
sudo -u runner pip3 install --upgrade pip
sudo -u runner pip3 install \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 \
    whisperx \
    yt-dlp \
    ffmpeg-python

# 7. 验证安装
echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Verification:"
nvidia-smi
python3 -c "import torch; print(f'PyTorch CUDA available: {torch.cuda.is_available()}')"
echo ""
echo "📖 Next steps: Configure the runner using the instructions above"
