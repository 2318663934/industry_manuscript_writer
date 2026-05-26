@echo off
REM 启动 RAG 写作系统服务（确保干净启动）
cd /d "%~dp0"
echo ========================================
echo   启动 RAG 写作系统
echo ========================================

REM 1. 停止并清理已有的 PM2 进程
echo [1/3] 清理已有服务...
pm2 stop rag-writer 2>nul
pm2 delete rag-writer 2>nul

REM 2. 强制清理 5003 端口残留进程
echo [2/3] 清理端口 5003 残留...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5003.*LISTENING" 2^>nul') do (
    echo   终止进程 PID=%%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul

REM 3. 启动服务
echo [3/3] 启动服务...
pm2 start ecosystem.config.json

echo.
echo 服务已启动，访问: http://localhost:5003
pause
