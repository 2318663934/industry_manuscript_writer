@echo off
REM 从 PM2 中删除 RAG 写作系统
cd /d "%~dp0"
echo ========================================
echo   删除 RAG 写作系统进程
echo ========================================
pm2 delete rag-writer
echo.
echo 服务已从 PM2 中删除
pause
