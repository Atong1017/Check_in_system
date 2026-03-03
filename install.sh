#!/bin/bash
echo "=========================================="
echo "    Check In System 一鍵安裝腳本    "
echo "=========================================="

echo "[1/4] 啟動 Docker 容器..."
docker compose down
docker compose up -d --build

echo "[2/4] 等待資料庫啟動完成..."
sleep 5

echo "[3/4] 執行資料庫遷移與權限建置..."
docker compose exec web python manage.py makemigrations core
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_groups

echo "[4/4] 建立測試資料庫與模擬帳號..."
docker compose exec web python manage.py setup_mock_data

echo "=========================================="
echo "安裝與資料建置完成！"
echo "您可以開啟瀏覽器登入體驗了 (預設 http://主機IP:5010)"
echo "超級管理員: superuser / admin1234"
echo "總經理: boss / password123"
echo "店長: mami / password123"
echo "經紀人: agent / password123"
echo "員工: staff / password123"
echo "=========================================="
