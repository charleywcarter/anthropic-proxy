#!/bin/bash
set -e

# =============================================================================
# ComfyUI + Wan 2.2 Setup Script for RunPod (4090 / 24GB VRAM)
# =============================================================================
# Usage: Copy-paste this entire script into your RunPod terminal, or:
#   curl -sL <raw-url> | bash
#
# What this installs:
#   - ComfyUI (latest)
#   - ComfyUI Manager
#   - Kijai's WanVideoWrapper (best Wan integration)
#   - Wan 2.2 TI2V-5B model (text+image to video, optimized for 24GB)
#   - Wan 2.2 14B FP8 models (high+low noise experts, for quality runs)
#   - Flux 2 Klein 4B (fast image generation + editing, fits 24GB)
#   - UMT5-XXL text encoder (FP8)
#   - Qwen3-4B text encoder (for Flux 2 Klein)
#   - Wan 2.1 VAE + Flux VAE
#   - CivitAI integration nodes
# =============================================================================

COMFY_DIR="/workspace/ComfyUI"
MODELS_DIR="$COMFY_DIR/models"

echo "============================================"
echo "  ComfyUI + Wan 2.2 Setup for RunPod"
echo "============================================"
echo ""

# --- Step 1: System dependencies ---
echo "[1/7] Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq git wget aria2 python3-venv > /dev/null 2>&1
echo "  Done."

# --- Step 2: Clone ComfyUI ---
echo "[2/7] Setting up ComfyUI..."
if [ -d "$COMFY_DIR" ]; then
    echo "  ComfyUI already exists at $COMFY_DIR, pulling latest..."
    cd "$COMFY_DIR" && git pull --quiet
else
    git clone --quiet https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
fi
cd "$COMFY_DIR"

# --- Step 3: Python environment ---
echo "[3/7] Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install --quiet -r requirements.txt
echo "  Done."

# --- Step 4: Custom nodes ---
echo "[4/7] Installing custom nodes..."
cd "$COMFY_DIR/custom_nodes"

# ComfyUI Manager
if [ ! -d "ComfyUI-Manager" ]; then
    git clone --quiet https://github.com/ltdrdata/ComfyUI-Manager.git
else
    cd ComfyUI-Manager && git pull --quiet && cd ..
fi

# Kijai's WanVideoWrapper (best Wan 2.2 support)
if [ ! -d "ComfyUI-WanVideoWrapper" ]; then
    git clone --quiet https://github.com/kijai/ComfyUI-WanVideoWrapper.git
    pip install --quiet -r ComfyUI-WanVideoWrapper/requirements.txt
else
    cd ComfyUI-WanVideoWrapper && git pull --quiet && cd ..
    pip install --quiet -r ComfyUI-WanVideoWrapper/requirements.txt
fi

# CivitAI Nodes (official - browse/download models from CivitAI)
if [ ! -d "civitai_comfy_nodes" ]; then
    git clone --quiet https://github.com/civitai/civitai_comfy_nodes.git
    if [ -f "civitai_comfy_nodes/requirements.txt" ]; then
        pip install --quiet -r civitai_comfy_nodes/requirements.txt
    fi
else
    cd civitai_comfy_nodes && git pull --quiet && cd ..
fi

# Civicomfy (search, download, organize CivitAI models from within ComfyUI)
if [ ! -d "Civicomfy" ]; then
    git clone --quiet https://github.com/MoonGoblinDev/Civicomfy.git
    if [ -f "Civicomfy/requirements.txt" ]; then
        pip install --quiet -r Civicomfy/requirements.txt
    fi
else
    cd Civicomfy && git pull --quiet && cd ..
fi

echo "  Done."

# --- Step 5: Create model directories ---
echo "[5/7] Creating model directories..."
mkdir -p "$MODELS_DIR/diffusion_models"
mkdir -p "$MODELS_DIR/text_encoders"
mkdir -p "$MODELS_DIR/vae"
mkdir -p "$MODELS_DIR/clip"
mkdir -p "$MODELS_DIR/clip_vision"
echo "  Done."

# --- Step 6: Download models ---
echo "[6/7] Downloading models (this will take a while)..."
echo ""

# Helper function for downloading with aria2 (faster than wget)
download_model() {
    local url="$1"
    local dest="$2"
    local name="$3"
    if [ -f "$dest" ]; then
        echo "  [$name] Already exists, skipping."
    else
        echo "  [$name] Downloading..."
        aria2c -x 16 -s 16 --quiet --dir="$(dirname "$dest")" --out="$(basename "$dest")" "$url"
        echo "  [$name] Done."
    fi
}

# Wan 2.2 TI2V-5B (FP16 - fits on 4090, best quality-to-VRAM ratio)
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" \
    "$MODELS_DIR/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" \
    "Wan 2.2 TI2V-5B (FP16)"

# Wan 2.2 14B High Noise Expert (FP8 - for quality runs)
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors" \
    "$MODELS_DIR/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors" \
    "Wan 2.2 14B High Noise Expert (FP8)"

# Wan 2.2 14B Low Noise Expert (FP8 - for quality runs)
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" \
    "$MODELS_DIR/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" \
    "Wan 2.2 14B Low Noise Expert (FP8)"

# UMT5-XXL Text Encoder (FP8 - required for all Wan models)
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
    "$MODELS_DIR/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
    "UMT5-XXL Text Encoder (FP8)"

# Wan VAE
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
    "$MODELS_DIR/vae/wan_2.1_vae.safetensors" \
    "Wan 2.1 VAE"

# CLIP Vision (for image-to-video with TI2V-5B)
download_model \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors" \
    "$MODELS_DIR/clip_vision/clip_vision_h.safetensors" \
    "CLIP Vision H (for I2V)"

# --- Flux 2 Klein 4B (image generation + editing, fits 24GB) ---
# Note: 9B needs ~29GB, won't fit on 4090. 4B fits comfortably at ~13GB.
download_model \
    "https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/resolve/main/flux2-klein-4B.safetensors" \
    "$MODELS_DIR/diffusion_models/flux2-klein-4B.safetensors" \
    "Flux 2 Klein 4B"

# Qwen3-4B Text Encoder (required for Flux 2 Klein 4B)
download_model \
    "https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/resolve/main/qwen3_4b_fp16.safetensors" \
    "$MODELS_DIR/text_encoders/qwen3_4b_fp16.safetensors" \
    "Qwen3-4B Text Encoder (for Flux 2 Klein)"

# Flux VAE (shared across Flux models)
download_model \
    "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" \
    "$MODELS_DIR/vae/flux_ae.safetensors" \
    "Flux VAE"

echo ""
echo "  All models downloaded."

# --- Step 7: Start ComfyUI ---
echo "[7/7] Starting ComfyUI..."
echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  ComfyUI is installed at: $COMFY_DIR"
echo ""
echo "  Models installed:"
echo "    - Wan 2.2 TI2V-5B (FP16) - text+image to video, 720p"
echo "    - Wan 2.2 14B MoE (FP8)  - higher quality, slower"
echo "    - Flux 2 Klein 4B         - fast image gen + editing"
echo "    - UMT5-XXL text encoder   - for Wan models"
echo "    - Qwen3-4B text encoder   - for Flux 2 Klein"
echo "    - Wan 2.1 VAE + Flux VAE"
echo "    - CLIP Vision H"
echo ""
echo "  Custom nodes:"
echo "    - ComfyUI Manager"
echo "    - Kijai WanVideoWrapper"
echo "    - CivitAI Nodes (official)"
echo "    - Civicomfy (model browser)"
echo ""
echo "  Starting ComfyUI on port 8188..."
echo "  Access it via your RunPod proxy URL."
echo ""

cd "$COMFY_DIR"
source venv/bin/activate
python main.py --listen 0.0.0.0 --port 8188
