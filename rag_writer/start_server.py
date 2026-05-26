#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动RAG写作系统Web服务"""
import os
import sys

# 清除代理环境变量
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(var, None)

# 设置 HuggingFace 镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 添加项目根目录到路径
sys.path.insert(0, 'e:/行业稿件写作/code')
sys.path.insert(0, 'e:/行业稿件写作/code/rag_writer')

import rag_writer.web_demo as wd

if __name__ == '__main__':
    print("启动RAG写作系统Web服务...")
    print("访问地址: http://localhost:5000")
    wd.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)