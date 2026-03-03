@echo off
chcp 65001 >nul 2>&1
:: ============================================================
::  Check_in_system_aws — 一鍵安裝腳本（Windows）
::  用法: 雙擊 install.bat 或在終端執行
:: ============================================================

echo.
echo ============================================
echo   Check_in_system_aws 一鍵安裝
echo ============================================
echo.

cd /d "%~dp0"

:: ── 0. 前置檢查 ──
echo [INFO] 檢查必要工具...
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 找不到 docker，請先安裝 Docker Desktop
    echo         https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

:: 判斷 docker compose 版本
docker compose version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set DC=docker compose
) else (
    where docker-compose >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set DC=docker-compose
    ) else (
        echo [ERROR] 找不到 docker-compose，請確認 Docker Desktop 已安裝
        pause
        exit /b 1
    )
)

:: ── 1. 建立 .env ──
if not exist .env (
    echo [INFO] 未偵測到 .env，從 .env.example 複製...
    if exist .env.example (
        copy .env.example .env >nul
        echo [INFO] .env 已建立，請視需要修改 DJANGO_SECRET_KEY
    ) else (
        echo [ERROR] 找不到 .env.example，請手動建立 .env
        pause
        exit /b 1
    )
) else (
    echo [INFO] .env 已存在，跳過
)

:: ── 2. 建置 & 啟動容器 ──
echo [INFO] 建置 Docker 映像...
%DC% build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker build 失敗
    pause
    exit /b 1
)

echo [INFO] 啟動容器（背景執行）...
%DC% up -d
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker 啟動失敗
    pause
    exit /b 1
)

:: ── 3. 等待 DB 就緒 ──
echo [INFO] 等待 PostgreSQL 就緒...
set RETRIES=30
:wait_db
%DC% exec -T db pg_isready -U timelog_user -d timelog_db >nul 2>&1
if %ERRORLEVEL% equ 0 goto db_ready
set /a RETRIES=%RETRIES%-1
if %RETRIES% leq 0 (
    echo [ERROR] PostgreSQL 啟動逾時
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_db

:db_ready
echo [INFO] PostgreSQL 已就緒

:: ── 4. Django 初始化 ──
echo [INFO] 執行 migrations...
%DC% exec -T web python manage.py makemigrations core
%DC% exec -T web python manage.py migrate

echo [INFO] 建立權限群組...
%DC% exec -T web python manage.py setup_groups

:: ── 5. 建立示範資料 ──
echo [INFO] 建立示範帳號與資料...
%DC% exec -T web python manage.py seed_demo_data

:: ── 6. 完成 ──
echo.
echo ============================================
echo   安裝完成！
echo ============================================
echo.
echo   應用網址:  http://localhost:8000
echo.
echo   示範帳號（密碼皆為 demo1234）:
echo   ─────────────────────────────────────
echo   admin    (超級管理員) — 總公司層級
echo   mami01   (媽咪/店長)  — Demo 一店
echo   mami02   (媽咪/店長)  — Demo 二店
echo   agent01  (經紀人)     — Demo 一店
echo   staff01  (員工)       — Demo 一店
echo   staff02  (員工)       — Demo 一店
echo   staff03  (員工)       — Demo 二店
echo   ─────────────────────────────────────
echo.
echo   常用指令:
echo   查看 logs:     %DC% logs -f web
echo   停止服務:      %DC% down
echo   重新啟動:      %DC% restart
echo.
pause
