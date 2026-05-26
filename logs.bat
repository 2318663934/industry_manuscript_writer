@echo off
REM 查看 RAG 写作系统实时日志
cd /d "%~dp0"
echo ========================================
echo   RAG 写作系统日志 (Ctrl+C 退出)
echo ========================================
pm2 logs rag-writer
