@echo off
REM 重启 RAG 写作系统服务（彻底清理旧进程）
cd /d "%~dp0"
echo ========================================
echo   重启 RAG 写作系统
echo ========================================

REM 1. PM2 停止
echo [1/4] PM2 停止服务...
pm2 stop rag-writer 2>nul

REM 2. PM2 删除（释放进程引用）
echo [2/4] PM2 删除旧进程...
pm2 delete rag-writer 2>nul

REM 3. 强制清理 5003 端口上的残留进程
echo [3/4] 清理端口 5003 残留...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5003.*LISTENING" 2^>nul') do (
    echo   终止进程 PID=%%a
    taskkill /F /PID %%a 2>nul
)

REM 等待端口释放
timeout /t 3 /nobreak >nul

REM 4. 重新启动
echo [4/4] 启动服务...
pm2 start ecosystem.config.json

echo.
echo 服务已重启，访问: http://localhost:5003
echo 查看状态: pm2 status
pause
