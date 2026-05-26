#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作系统命令行工具
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import main

if __name__ == "__main__":
    main()
