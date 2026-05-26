# -*- coding: utf-8 -*-
import sys
import os

# 清除代理
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(var, None)

# 直接测试_parse_blueprint
import json
import re

# 模拟一个无法解析的响应
test_content = "这不是有效的JSON格式"

def _parse_blueprint(json_str: str):
    text = json_str.strip()
    json_blocks = re.findall(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    brace_start = text.find('{')
    if brace_start != -1:
        for brace_end in range(len(text), brace_start, -1):
            candidate = text[brace_start:brace_end]
            try:
                data = json.loads(candidate)
                if "topic" in data and "sections" in data:
                    json_blocks.append(candidate)
                    break
            except json.JSONDecodeError:
                continue

    for json_text in json_blocks:
        try:
            data = json.loads(json_text)
            return data
        except (json.JSONDecodeError, Exception) as e:
            continue

    print(f"[DEBUG] 无法解析，共尝试 {len(json_blocks)} 个JSON块")
    print(f"[DEBUG] 原始内容: {text[:500]}")
    raise ValueError(f"无法解析策略蓝图JSON，LLM原始返回: {text[:500]}")

try:
    _parse_blueprint(test_content)
except ValueError as e:
    print(f"Caught error: {e}")