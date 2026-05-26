# -*- coding: utf-8 -*-
import sys
import os

# 清除代理
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(var, None)

# 使用 urllib 直接发送请求（绕过代理）
import json
import urllib.request

data = json.dumps({'topic': 'AI测试', 'requirements': '测试', 'keywords': [], 'top_k': 3, 'supplementary_sources': [], 'use_skill': True}).encode('utf-8')
req = urllib.request.Request('http://localhost:5003/api/generate_blueprint', data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        print('Status:', resp.status)
        result = resp.read().decode('utf-8')
        print('Response length:', len(result))
        print('Response:', result[:3000])
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    print('Response body:', e.read().decode('utf-8')[:5000])
except Exception as e:
    print('Error:', type(e).__name__, e)