@echo off
REM 停止 RAG 写作系统服务
cd /d "%~dp0"
echo ========================================
echo   停止 RAG 写作系统
echo ========================================
pm2 stop rag-writer
echo.
echo 服务已停止
pause
