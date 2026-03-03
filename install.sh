#!/usr/bin/env bash
# ============================================================
#  Check_in_system_aws — 一鍵安裝腳本（Linux / macOS / AWS）
#  用法: chmod +x install.sh && ./install.sh
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 0. 前置檢查 ──
info "檢查必要工具..."
command -v docker   >/dev/null 2>&1 || error "找不到 docker，請先安裝: https://docs.docker.com/engine/install/"
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || error "找不到 docker-compose"

# 判斷使用 docker-compose 還是 docker compose
if command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    DC="docker compose"
fi

# ── 1. 建立 .env ──
if [ ! -f .env ]; then
    info "未偵測到 .env，從 .env.example 複製..."
    if [ -f .env.example ]; then
        cp .env.example .env
        # 自動產生隨機 SECRET_KEY
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50 | tr -d '\n/+=' | head -c 50)
        sed -i "s|replace-with-50-char-random-string|${SECRET_KEY}|g" .env
        info ".env 已建立（SECRET_KEY 已自動產生）"
    else
        error "找不到 .env.example，請手動建立 .env"
    fi
else
    info ".env 已存在，跳過"
fi

# ── 2. 建置 & 啟動容器 ──
info "建置 Docker 映像..."
$DC build

info "啟動容器（背景執行）..."
$DC up -d

# ── 3. 等待 DB 就緒 ──
info "等待 PostgreSQL 就緒..."
RETRIES=30
until $DC exec -T db pg_isready -U timelog_user -d timelog_db >/dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        error "PostgreSQL 啟動逾時，請檢查 docker logs"
    fi
    sleep 1
done
info "PostgreSQL 已就緒"

# ── 4. Django 初始化 ──
info "執行 migrations..."
$DC exec -T web python manage.py makemigrations core
$DC exec -T web python manage.py migrate

info "建立權限群組..."
$DC exec -T web python manage.py setup_groups

# ── 5. 建立示範資料 ──
info "建立示範帳號與資料..."
$DC exec -T web python manage.py seed_demo_data

# ── 6. 完成 ──
PORT=$(grep -oP 'PORT=\K[0-9]+' .env 2>/dev/null || echo "8000")
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  安裝完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  應用網址:  http://localhost:${PORT}"
echo ""
echo "  示範帳號（密碼皆為 demo1234）:"
echo "  ─────────────────────────────────────"
echo "  admin    (超級管理員) — 總公司層級"
echo "  mami01   (媽咪/店長)  — Demo 一店"
echo "  mami02   (媽咪/店長)  — Demo 二店"
echo "  agent01  (經紀人)     — Demo 一店"
echo "  staff01  (員工)       — Demo 一店"
echo "  staff02  (員工)       — Demo 一店"
echo "  staff03  (員工)       — Demo 二店"
echo "  ─────────────────────────────────────"
echo ""
echo "  常用指令:"
echo "  查看 logs:     $DC logs -f web"
echo "  停止服務:      $DC down"
echo "  重新啟動:      $DC restart"
echo ""
