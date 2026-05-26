@echo off
REM 查看 RAG 写作系统服务状态
cd /d "%~dp0"
echo ========================================
echo   RAG 写作系统状态
echo ========================================
pm2 status
echo.
echo 详细信息:
pm2 describe rag-writer
pause
