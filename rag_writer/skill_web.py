#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SKILL.md 写作服务 — 独立 Flask 应用

将 SKILL.md 写作风格库作为 system prompt 注入 LLM，
复用 RAG 检索 + 补充资料加载，提供简洁的单页写作界面。
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime

# 清除代理环境变量
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(var, None)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, render_template_string

from rag_writer.engine import RAGWriter, create_writer
from rag_writer.llm_client import create_llm_client
from rag_writer.supplementary_loader import SupplementaryLoader
from rag_writer.skill_prompt import SkillPromptBuilder, load_skill_md
from rag_writer.config import settings
from rag_writer.document_parser import extract_topic_from_text

app = Flask(__name__)

# 全局实例（懒加载）
_writer = None
_skill_builder = None

SKILL_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SKILL.md 写作服务</title>
<style>
    :root {
        --bg: #f8f9fa; --card-bg: #ffffff; --text: #2c3e50;
        --text-secondary: #666; --border: #e0e0e0; --accent: #e67e22;
        --accent-hover: #d35400; --danger: #e74c3c; --success: #27ae60;
        --radius: 8px; --shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
    .container { max-width: 900px; margin: 0 auto; padding: 24px 16px; }

    header { text-align: center; margin-bottom: 24px; }
    header h1 { font-size: 22px; color: var(--accent); }
    header p { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

    .card { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 24px; margin-bottom: 16px; border: 1px solid var(--border); }

    .form-group { margin-bottom: 16px; }
    .form-group:last-child { margin-bottom: 0; }
    label { display: block; font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #333; }
    label .hint { font-weight: 400; color: #999; font-size: 12px; }

    input[type="text"], textarea, select {
        width: 100%; padding: 10px 12px; border: 1px solid var(--border);
        border-radius: 6px; font-size: 14px; font-family: inherit;
        transition: border-color 0.2s; background: #fafafa;
    }
    input:focus, textarea:focus, select:focus { outline: none; border-color: var(--accent); background: #fff; }
    textarea { resize: vertical; min-height: 80px; }

    .row { display: flex; gap: 12px; }
    .row > * { flex: 1; }

    .btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        padding: 10px 24px; border: none; border-radius: 6px; font-size: 15px;
        font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: inherit;
    }
    .btn-primary { background: var(--accent); color: #fff; width: 100%; }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-sm { padding: 6px 12px; font-size: 13px; }

    /* 补充资料 */
    .supp-tabs { display: flex; gap: 6px; margin-bottom: 12px; }
    .supp-tab {
        padding: 6px 16px; border: 1px solid var(--border); border-radius: 20px;
        background: #fff; cursor: pointer; font-size: 13px; transition: all 0.2s;
    }
    .supp-tab:hover { background: #f0f0f0; }
    .supp-tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    .supp-panel { display: none; }
    .supp-panel.active { display: block; }
    .supp-list { margin-top: 10px; }
    .supp-item {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 12px; background: #f8f9fa; border-radius: 6px; margin-bottom: 6px; font-size: 13px;
    }
    .supp-item .remove { color: var(--danger); cursor: pointer; font-weight: bold; padding: 2px 6px; }
    .supp-empty { text-align: center; padding: 16px; color: #999; font-size: 13px; }

    /* 输出区 */
    .result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .result-meta { font-size: 12px; color: var(--text-secondary); }
    .result-meta span { margin-right: 16px; }

    .article-content {
        background: #fafafa; border: 1px solid var(--border); border-radius: var(--radius);
        padding: 24px; font-size: 15px; line-height: 1.8; white-space: pre-wrap;
        max-height: 70vh; overflow-y: auto;
    }
    .article-content h1 { font-size: 20px; margin: 16px 0 12px; }
    .article-content h2 { font-size: 17px; margin: 14px 0 10px; }
    .article-content h3 { font-size: 15px; margin: 12px 0 8px; }
    .article-content p { margin: 8px 0; }

    .sources-box { margin-top: 16px; }
    .sources-box summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); }
    .sources-box ul { margin-top: 8px; font-size: 13px; color: #555; padding-left: 20px; }
    .sources-box li { margin-bottom: 4px; }

    .loading { text-align: center; padding: 40px; }
    .spinner { display: inline-block; width: 32px; height: 32px; border: 3px solid #eee; border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .error { background: #fdf2f2; color: var(--danger); padding: 16px; border-radius: var(--radius); font-size: 13px; white-space: pre-wrap; }
    .hidden { display: none; }

    .footer { text-align: center; margin-top: 24px; font-size: 12px; color: #aaa; }
</style>
</head>
<body>
<div class="container">

<header>
    <h1>SKILL.md 写作服务</h1>
    <p>祝佳音（触乐278篇）+ 托马斯之颅（知乎+公众号107篇）双视角风格蒸馏 · 9模板 · 9开篇 · 7结尾</p>
</header>

<!-- 输入表单 -->
<div class="card" id="inputCard">
    <form id="writeForm">
        <div class="form-group">
            <label>稿件类型 <span class="hint">（决定推荐风格和模板）</span></label>
            <select id="articleType">
                <option value="">自动判断</option>
                <option value="行业趋势">行业趋势/财报分析</option>
                <option value="深度人物">深度人物/访谈</option>
                <option value="热点评论">热点评论/观点文</option>
                <option value="游戏评测">游戏评测/产品文</option>
                <option value="从业者职场">从业者生存/职场</option>
                <option value="文化评论">文化评论/杂谈</option>
                <option value="市场数据">市场数据/报告解读</option>
                <option value="突发热点">突发热点/快评</option>
            </select>
        </div>

        <div class="form-group">
            <label>话题/主题 <span style="color:red">*</span></label>
            <input type="text" id="topic" placeholder="例如：米哈游新作《星布谷地》拿到版号意味着什么" required>
        </div>

        <div class="form-group">
            <label>背景信息 <span class="hint">（选填）</span></label>
            <textarea id="background" rows="3" placeholder="提供话题的来龙去脉、行业背景等..."></textarea>
        </div>

        <div class="form-group">
            <label>具体要求 <span class="hint">（选填）</span></label>
            <textarea id="requirements" rows="3" placeholder="对文章的具体要求，如角度、调性、需要覆盖的要点..."></textarea>
        </div>

        <div class="row">
            <div class="form-group">
                <label>关键词 <span class="hint">（逗号分隔）</span></label>
                <input type="text" id="keywords" placeholder="米哈游, 版号, 星布谷地">
            </div>
            <div class="form-group">
                <label>字数要求</label>
                <input type="text" id="length" placeholder="2000-3000字">
            </div>
            <div class="form-group">
                <label>检索数量</label>
                <select id="topK">
                    <option value="3">3 篇</option>
                    <option value="5" selected>5 篇</option>
                    <option value="8">8 篇</option>
                    <option value="10">10 篇</option>
                </select>
            </div>
        </div>

        <!-- 补充资料 -->
        <div class="form-group">
            <label>补充资料 <span class="hint">（选填，文件/链接/文本）</span></label>
            <div class="supp-tabs">
                <button type="button" class="supp-tab active" onclick="switchSuppTab('files')">上传文件</button>
                <button type="button" class="supp-tab" onclick="switchSuppTab('urls')">添加链接</button>
                <button type="button" class="supp-tab" onclick="switchSuppTab('text')">粘贴文本</button>
            </div>
            <div id="supp-files" class="supp-panel active">
                <input type="file" id="fileInput" multiple accept=".txt,.docx,.pdf,.xlsx,.xls" onchange="addFiles(this)" style="font-size:13px">
                <div style="font-size:12px;color:#999;margin-top:4px">支持 TXT, DOCX, PDF, Excel</div>
            </div>
            <div id="supp-urls" class="supp-panel">
                <div style="display:flex;gap:8px">
                    <input type="text" id="urlInput" placeholder="输入文章链接（微信/网页）" style="flex:1">
                    <button type="button" class="btn btn-sm" onclick="addUrl()" style="background:var(--accent);color:#fff">添加</button>
                </div>
            </div>
            <div id="supp-text" class="supp-panel">
                <div style="display:flex;gap:8px;margin-bottom:8px">
                    <input type="text" id="textTitle" placeholder="资料标题" style="flex:1">
                    <button type="button" class="btn btn-sm" onclick="addText()" style="background:var(--accent);color:#fff">添加</button>
                </div>
                <textarea id="textContent" rows="4" placeholder="粘贴文本内容..."></textarea>
            </div>
            <div class="supp-list" id="suppList">
                <div class="supp-empty">暂无补充资料</div>
            </div>
        </div>

        <button type="submit" class="btn btn-primary" id="submitBtn">
            开始写作
        </button>
    </form>
</div>

<!-- 输出区 -->
<div class="card hidden" id="outputCard">
    <div class="loading hidden" id="loadingArea">
        <div class="spinner"></div>
        <p style="margin-top:12px;color:#666">正在检索资料并生成文章...</p>
    </div>
    <div class="hidden" id="resultArea">
        <div class="result-header">
            <div class="result-meta" id="resultMeta"></div>
            <div>
                <button class="btn btn-sm" onclick="copyArticle()" style="background:#eee">复制</button>
                <button class="btn btn-sm" onclick="downloadArticle()" style="background:#eee">下载</button>
                <button class="btn btn-sm" onclick="backToInput()" style="background:#eee">返回修改</button>
            </div>
        </div>
        <div class="article-content" id="articleContent"></div>
        <details class="sources-box" id="sourcesBox">
            <summary>参考知识来源 (<span id="sourceCount">0</span> 条)</summary>
            <ul id="sourceList"></ul>
        </details>
    </div>
    <div class="hidden" id="errorArea"></div>
</div>

<div class="footer">Powered by SKILL.md v1.0 · 职业游戏行业写手风格模型</div>

</div>

<script>
    let suppMaterials = [];

    function switchSuppTab(type) {
        document.querySelectorAll('.supp-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.supp-panel').forEach(p => p.classList.remove('active'));
        event.target.classList.add('active');
        document.getElementById('supp-' + type).classList.add('active');
    }

    function renderSuppList() {
        const el = document.getElementById('suppList');
        if (suppMaterials.length === 0) {
            el.innerHTML = '<div class="supp-empty">暂无补充资料</div>';
            return;
        }
        const labels = { file: '文件', url: '链接', text: '文本' };
        el.innerHTML = suppMaterials.map((m, i) => `
            <div class="supp-item">
                <span><strong>${m.title}</strong> (${labels[m.type] || m.type})</span>
                <span class="remove" onclick="removeSupp(${i})" title="移除">x</span>
            </div>
        `).join('');
    }

    function addFiles(input) {
        for (const file of input.files) {
            const reader = new FileReader();
            reader.onload = function(e) {
                suppMaterials.push({ type: 'file', source: e.target.result, title: file.name, name: file.name });
                renderSuppList();
            };
            reader.readAsDataURL(file);
        }
        input.value = '';
    }

    function addUrl() {
        const url = document.getElementById('urlInput').value.trim();
        if (!url) return;
        suppMaterials.push({ type: 'url', source: url, title: url.length > 60 ? url.substring(0, 60) + '...' : url });
        document.getElementById('urlInput').value = '';
        renderSuppList();
    }

    function addText() {
        const title = document.getElementById('textTitle').value.trim() || '用户粘贴文本';
        const content = document.getElementById('textContent').value.trim();
        if (!content) return;
        suppMaterials.push({ type: 'text', source: content, title: title });
        document.getElementById('textTitle').value = '';
        document.getElementById('textContent').value = '';
        renderSuppList();
    }

    function removeSupp(i) { suppMaterials.splice(i, 1); renderSuppList(); }

    document.getElementById('writeForm').addEventListener('submit', async function(e) {
        e.preventDefault();

        const topic = document.getElementById('topic').value.trim();
        if (!topic) { alert('请输入话题/主题'); return; }

        document.getElementById('outputCard').classList.remove('hidden');
        document.getElementById('loadingArea').classList.remove('hidden');
        document.getElementById('resultArea').classList.add('hidden');
        document.getElementById('errorArea').classList.add('hidden');
        document.getElementById('submitBtn').disabled = true;

        try {
            const resp = await fetch('/api/write', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic: topic,
                    background: document.getElementById('background').value.trim(),
                    requirements: document.getElementById('requirements').value.trim(),
                    keywords: document.getElementById('keywords').value.split(',').map(s => s.trim()).filter(Boolean),
                    length: document.getElementById('length').value.trim(),
                    article_type: document.getElementById('articleType').value,
                    top_k: parseInt(document.getElementById('topK').value) || 5,
                    supplementary_sources: suppMaterials.map(m => m.source),
                }),
            });

            const data = await resp.json();
            document.getElementById('loadingArea').classList.add('hidden');

            if (data.error) {
                document.getElementById('errorArea').classList.remove('hidden');
                document.getElementById('errorArea').innerHTML = '<div class="error">' + data.error + '</div>';
                document.getElementById('submitBtn').disabled = false;
                return;
            }

            document.getElementById('resultArea').classList.remove('hidden');
            document.getElementById('resultMeta').innerHTML =
                '<span>模型: ' + data.model + '</span>' +
                '<span>耗时: ' + data.generation_time.toFixed(1) + 's</span>' +
                '<span>知识来源: ' + data.knowledge_count + ' 条</span>' +
                (data.supplementary_count ? '<span>补充资料: ' + data.supplementary_count + ' 份</span>' : '') +
                '<span>Token: ' + JSON.stringify(data.usage) + '</span>';
            document.getElementById('articleContent').textContent = data.article;
            document.getElementById('sourceCount').textContent = data.knowledge_sources.length;
            document.getElementById('sourceList').innerHTML = data.knowledge_sources.map((s, i) =>
                '<li><strong>' + s.title + '</strong> — ' + s.author + ' | ' + s.date +
                (s.url ? ' <a href="' + s.url + '" target="_blank">链接</a>' : '') +
                (s.source ? ' (' + s.source + ')' : '') +
                '</li>'
            ).join('');
            document.getElementById('inputCard').classList.add('hidden');
        } catch (err) {
            document.getElementById('loadingArea').classList.add('hidden');
            document.getElementById('errorArea').classList.remove('hidden');
            document.getElementById('errorArea').innerHTML = '<div class="error">请求失败: ' + err.message + '</div>';
        }

        document.getElementById('submitBtn').disabled = false;
    });

    function copyArticle() {
        const text = document.getElementById('articleContent').textContent;
        navigator.clipboard.writeText(text).then(() => alert('已复制到剪贴板'));
    }

    function downloadArticle() {
        const text = document.getElementById('articleContent').textContent;
        const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'skill-article-' + new Date().toISOString().slice(0, 10) + '.md';
        a.click();
    }

    function backToInput() {
        document.getElementById('inputCard').classList.remove('hidden');
        document.getElementById('outputCard').classList.add('hidden');
        document.getElementById('resultArea').classList.add('hidden');
        document.getElementById('errorArea').classList.add('hidden');
    }
</script>
</body>
</html>
"""


def get_writer():
    """创建 RAGWriter 实例（仅用于 retrieve_knowledge）"""
    return create_writer()


def get_skill_builder():
    """获取 SkillPromptBuilder 单例"""
    global _skill_builder
    if _skill_builder is None:
        _skill_builder = SkillPromptBuilder()
    return _skill_builder


@app.route("/")
def index():
    """渲染写作界面"""
    return render_template_string(SKILL_HTML_TEMPLATE)


@app.route("/api/status", methods=["GET"])
def api_status():
    """健康检查"""
    try:
        llm_client = create_llm_client()
        return jsonify({
            "status": "ok",
            "skill_version": "1.0",
            "llm_provider": settings.llm.provider,
            "llm_model": settings.llm.model,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/write", methods=["POST"])
def api_write():
    """核心写作接口"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "话题/主题不能为空"}), 400

    try:
        writer = get_writer()
        llm_client = create_llm_client()
        skill_builder = get_skill_builder()

        requirements = data.get("requirements", "").strip()
        background = data.get("background", "").strip()
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        length = data.get("length", "").strip()
        article_type = data.get("article_type", "").strip() or None
        top_k = int(data.get("top_k", 5))
        supplementary_sources = data.get("supplementary_sources", [])

        start_time = time.time()

        # 1. RAG 检索
        search_query = f"{topic} {' '.join(keywords)}"
        knowledge_items = writer.retrieve_knowledge(search_query, top_k=top_k)

        # 2. 加载补充资料
        supplementary_count = 0
        if supplementary_sources:
            print(f"加载 {len(supplementary_sources)} 份补充资料...")
            loader = SupplementaryLoader()
            supplementary_materials = loader.load(supplementary_sources)
            supplementary_count = len(supplementary_materials)
            for mat in supplementary_materials:
                knowledge_items.append(mat.to_knowledge_context())

        # 3. 构建提示词
        prompt = skill_builder.build_prompt(
            topic=topic,
            requirements=requirements,
            keywords=keywords,
            length=length,
            background=background,
            article_type=article_type,
            knowledge_items=knowledge_items,
        )

        # 4. 调用 LLM
        print(f"正在生成文章 (SKILL.md style)...")
        response = llm_client.generate_with_system(
            prompt["system"],
            prompt["user"],
        )

        generation_time = time.time() - start_time

        # 5. 构建来源信息
        db_count = len(knowledge_items) - supplementary_count
        knowledge_sources = []
        for k in knowledge_items[:db_count]:
            knowledge_sources.append({
                "title": k.title if hasattr(k, 'title') else k.get("title", ""),
                "author": k.author if hasattr(k, 'author') else k.get("author", ""),
                "date": k.date if hasattr(k, 'date') else k.get("date", ""),
                "url": k.url if hasattr(k, 'url') else k.get("url", ""),
            })

        return jsonify({
            "article": response.content,
            "topic": topic,
            "model": response.model,
            "knowledge_count": db_count,
            "knowledge_sources": knowledge_sources,
            "generation_time": generation_time,
            "usage": response.usage,
            "supplementary_count": supplementary_count,
        })

    except Exception as e:
        return jsonify({
            "error": str(e) + "\n" + traceback.format_exc(),
        }), 500


def main():
    """直接运行入口"""
    print("启动 SKILL.md 写作服务...")
    print("访问地址: http://localhost:5004")
    app.run(host="0.0.0.0", port=5004, debug=False)


if __name__ == "__main__":
    main()
