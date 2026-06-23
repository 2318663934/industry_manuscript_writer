#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG写作系统 - 简易Web界面
使用Flask提供Web服务

启动方式:
    pip install flask
    python web_demo.py

访问: http://localhost:5000
"""
import os
import sys
import json
import re
from pathlib import Path

# 清除代理环境变量（解决网络下载模型问题）
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(var, None)

# 设置 HuggingFace 镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

from flask import Flask, send_from_directory, request, jsonify, session
from rag_writer import create_writer
from rag_writer.config import settings

app = Flask(__name__)
app.secret_key = 'rag-writer-secret-key'

# 全局写作引擎
writer = None


def get_writer():
    """获取或创建写作引擎"""
    global writer
    # 每次都创建新实例以确保使用最新代码
    # 注意：这会增加延迟，但确保代码更新生效
    from rag_writer import create_writer
    articles_json = session.get('articles_json')
    use_few_shot = session.get('use_few_shot', False)
    writer = create_writer(articles_json=articles_json, use_few_shot=use_few_shot)
    return writer


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG写作系统 - 多步骤向导</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; }
        h3 { margin-bottom: 16px; color: #333; }
        h4 { margin-top: 12px; color: #555; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .form-group { margin-bottom: 16px; }
        label { display: block; margin-bottom: 6px; font-weight: 600; color: #444; }
        label .badge {
            font-size: 12px;
            font-weight: normal;
            background: #e9ecef;
            padding: 2px 8px;
            border-radius: 4px;
            margin-left: 8px;
        }
        input[type="text"], textarea, select {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #4a90d9;
        }
        textarea { min-height: 120px; resize: vertical; }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #4a90d9;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn:hover { background: #3a7bc8; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #5a6268; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #218838; }
        .btn-sm { padding: 6px 12px; font-size: 14px; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .checkbox-group { display: flex; align-items: center; gap: 8px; }
        .checkbox-group input { width: auto; }
        .status { padding: 12px; background: #e9ecef; border-radius: 6px; margin-bottom: 20px; font-size: 14px; }
        .status-item { display: flex; justify-content: space-between; padding: 4px 0; }
        .row { display: flex; gap: 16px; }
        .col { flex: 1; }
        .error { background: #f8d7da; color: #721c24; padding: 12px; border-radius: 6px; margin-bottom: 16px; }
        .loading { text-align: center; padding: 40px; }
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4a90d9;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* 步骤指示器 */
        .step-indicator {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }
        .step-item {
            display: flex;
            align-items: center;
            margin: 0 20px;
        }
        .step-number {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: #ddd;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-right: 10px;
        }
        .step-item.active .step-number { background: #4a90d9; }
        .step-item.completed .step-number { background: #28a745; }
        .step-label { color: #666; }
        .step-item.active .step-label { color: #4a90d9; font-weight: 600; }
        .step-connector {
            width: 60px;
            height: 2px;
            background: #ddd;
            margin: 0 10px;
        }
        .step-item.completed + .step-connector { background: #28a745; }

        /* 补充资料 */
        .supplementary-section {
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
            background: #fafafa;
        }
        .supplementary-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
        .supplementary-tab {
            padding: 8px 16px;
            border: 1px solid #ddd;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 14px;
        }
        .supplementary-tab:hover { background: #e9ecef; }
        .supplementary-tab.active { background: #4a90d9; color: white; border-color: #4a90d9; }
        .supplementary-panel { display: none; }
        .supplementary-panel.active { display: block; }
        .supplementary-list { margin-top: 12px; }
        .supplementary-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 8px;
        }
        .supplementary-item-info { flex: 1; }
        .supplementary-item-title { font-weight: 600; color: #333; }
        .supplementary-item-meta { font-size: 12px; color: #666; margin-top: 2px; }
        .supplementary-empty { text-align: center; padding: 20px; color: #999; }
        .add-url-row { display: flex; gap: 8px; }
        .add-url-row input { flex: 1; }
        .file-drop-zone {
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
        }
        .file-drop-zone:hover, .file-drop-zone.dragover { border-color: #4a90d9; background: #f0f7ff; }
        .file-drop-zone input { display: none; }
        .file-drop-zone-text { color: #666; font-size: 14px; }
        .file-drop-zone-text strong { color: #4a90d9; }
        .accepted-formats { font-size: 12px; color: #999; margin-top: 8px; }

        /* 大纲展示 */
        .outline-display {
            background: #fafafa;
            padding: 20px;
            border-radius: 6px;
            white-space: pre-wrap;
            line-height: 1.8;
            margin-bottom: 16px;
        }
        .outline-editor {
            width: 100%;
            min-height: 300px;
            font-family: monospace;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
        }
        .section-card {
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
            background: white;
        }
        .section-card:hover { border-color: #4a90d9; }
        .section-title { font-weight: 600; color: #1a1a1a; margin-bottom: 8px; }
        .section-desc { color: #666; font-size: 14px; margin-bottom: 8px; }
        .citation-card {
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 4px 0;
            font-size: 13px;
        }
        .citation-source { color: #4a90d9; }
        .word-estimate { color: #888; font-size: 12px; }

        /* 文章结果 */
        .article-content {
            background: #fafafa;
            padding: 20px;
            border-radius: 6px;
            white-space: pre-wrap;
            line-height: 1.8;
        }
        .sources { margin-top: 20px; padding: 16px; background: #f8f9fa; border-radius: 6px; }
        .source-item { padding: 8px 0; border-bottom: 1px solid #eee; }
        .source-item:last-child { border-bottom: none; }
        .source-title { font-weight: 600; }
        .source-meta { font-size: 13px; color: #666; }

        /* 反馈区 */
        .feedback-section {
            border-top: 1px solid #eee;
            padding-top: 16px;
            margin-top: 16px;
        }
        .feedback-actions {
            display: flex;
            gap: 10px;
            margin-top: 12px;
            flex-wrap: wrap;
        }

        /* === 用户反馈入库 === */
        .feedback-pin-btn {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            margin-left: 8px;
        }
        .feedback-pin-btn:hover {
            background: #ffeaa7;
        }
        .feedback-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 6px;
        }
        .feedback-badge.fact { background: #d4edda; color: #155724; }
        .feedback-badge.style { background: #cce5ff; color: #004085; }
        .feedback-badge.topic { background: #fff3cd; color: #856404; }
        .feedback-badge.none { background: #f8d7da; color: #721c24; }
        .feedback-preview {
            background: #f8f9fa;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 10px 14px;
            margin: 10px 0;
            font-size: 13px;
        }
        .feedback-preview strong { color: #1a7f37; }
        .feedback-modal-bg {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 9999;
            align-items: center;
            justify-content: center;
        }
        .feedback-modal-bg.active { display: flex; }
        .feedback-modal {
            background: #fff;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .feedback-modal h3 { margin: 0 0 12px; color: #1a7f37; }
        .feedback-modal .modal-row {
            margin: 8px 0;
            font-size: 13px;
        }
        .feedback-modal .modal-row label {
            font-weight: 600;
            color: #57606a;
        }
        .feedback-modal .modal-row pre {
            background: #f6f8fa;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
        }
        .feedback-modal .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 16px;
            justify-content: flex-end;
        }
        .feedback-modal textarea {
            width: 100%;
            min-height: 80px;
            border: 1px solid #d0d7de;
            border-radius: 4px;
            padding: 8px;
            font-size: 12px;
            font-family: monospace;
        }
        .feedback-modal .btn-cancel { background: #f6f8fa; color: #57606a; border: 1px solid #d0d7de; padding: 6px 14px; border-radius: 6px; cursor: pointer; }
        .feedback-modal .btn-confirm { background: #1a7f37; color: #fff; border: 1px solid #1a7f37; padding: 6px 14px; border-radius: 6px; cursor: pointer; }

        /* 隐藏/显示 */
        .step-content { display: none; }
        .step-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RAG写作系统</h1>

        <!-- 步骤指示器 -->
        <div class="step-indicator">
            <div class="step-item active" id="step1Indicator">
                <div class="step-number">1</div>
                <span class="step-label">填写任务</span>
            </div>
            <div class="step-connector"></div>
            <div class="step-item" id="step2Indicator">
                <div class="step-number">2</div>
                <span class="step-label">策略蓝图审核</span>
            </div>
            <div class="step-connector"></div>
            <div class="step-item" id="step3Indicator">
                <div class="step-number">3</div>
                <span class="step-label">大纲审核</span>
            </div>
            <div class="step-connector"></div>
            <div class="step-item" id="step4Indicator">
                <div class="step-number">4</div>
                <span class="step-label">生成文章</span>
            </div>
        </div>

        <!-- 系统状态 -->
        <div class="card">
            <h3>系统状态</h3>
            <div class="status" id="status">
                <div class="status-item"><span>加载中...</span></div>
            </div>
        </div>

        <!-- Step 1: 任务填写 -->
        <div class="step-content active" id="step1">
            <div class="card">
                <h3>Step 1: 填写写作任务</h3>
                <form id="taskForm">
                    <div class="form-group">
                        <label for="topic">话题/主题 <span style="color: red;">*</span></label>
                        <input type="text" id="topic" required placeholder="例如: AI大模型在内容创作领域的应用">
                    </div>
                    <div class="form-group">
                        <label for="requirements">具体要求</label>
                        <textarea id="requirements" placeholder="例如: 分析AI大模型如何改变内容创作行业"></textarea>
                    </div>
                    <div class="row">
                        <div class="col">
                            <div class="form-group">
                                <label for="keywords">关键词（用逗号分隔）</label>
                                <input type="text" id="keywords" placeholder="例如: AI, 大模型, 内容创作">
                            </div>
                        </div>
                        <div class="col">
                            <div class="form-group">
                                <label for="length">字数要求</label>
                                <input type="text" id="length" placeholder="例如: 2000字左右">
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col">
                            <div class="form-group">
                                <label for="topK">检索知识数量</label>
                                <select id="topK">
                                    <option value="3">3条</option>
                                    <option value="5" selected>5条</option>
                                    <option value="8">8条</option>
                                    <option value="10">10条</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- 补充资料 -->
                    <div class="form-group">
                        <label>补充资料 <span class="badge">可选</span></label>
                        <div class="supplementary-section">
                            <div class="supplementary-tabs">
                                <button type="button" class="supplementary-tab active" onclick="switchTab('files')">上传文件</button>
                                <button type="button" class="supplementary-tab" onclick="switchTab('urls')">添加链接</button>
                                <button type="button" class="supplementary-tab" onclick="switchTab('text')">粘贴文本</button>
                            </div>
                            <div id="panel-files" class="supplementary-panel active">
                                <div class="file-drop-zone" onclick="document.getElementById('suppFiles').click()">
                                    <input type="file" id="suppFiles" multiple accept=".txt,.docx,.pdf,.xlsx,.xls">
                                    <div class="file-drop-zone-text">
                                        <strong>点击此处</strong> 或拖拽文件到此处<br>支持多文件上传
                                    </div>
                                    <div class="accepted-formats">支持格式: TXT, DOCX, PDF, Excel</div>
                                </div>
                            </div>
                            <div id="panel-urls" class="supplementary-panel">
                                <div class="add-url-row">
                                    <input type="text" id="urlInput" placeholder="输入微信文章链接或其他网页URL">
                                    <button type="button" class="btn btn-sm" onclick="addUrl()">添加</button>
                                </div>
                            </div>
                            <div id="panel-text" class="supplementary-panel">
                                <textarea id="textInput" style="min-height: 100px;" placeholder="在此粘贴文本内容..."></textarea>
                                <div style="margin-top: 8px;">
                                    <input type="text" id="textTitle" placeholder="为此文本添加标题（可选）">
                                    <button type="button" class="btn btn-sm" onclick="addText()" style="margin-top:8px">添加文本</button>
                                </div>
                            </div>
                            <div class="supplementary-list" id="supplementaryList">
                                <div class="supplementary-empty">暂无补充资料</div>
                            </div>
                        </div>
                    </div>

                    <button type="submit" class="btn" id="generateOutlineBtn">生成策略蓝图</button>
                </form>
            </div>
        </div>

        <!-- Step 2: 策略蓝图审核 -->
        <div class="step-content" id="step2">
            <div class="card">
                <h3>Step 2: 策略蓝图审核</h3>
                <div id="blueprintLoading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>正在生成策略蓝图，请稍候...</p>
                </div>
                <div id="blueprintError" class="error" style="display: none;"></div>

                <div id="blueprintSection" style="display: none;">
                    <!-- 蓝图文案预览 -->
                    <div class="form-group">
                        <label>生成的策略蓝图</label>
                        <div class="outline-display" id="blueprintDisplay"></div>
                    </div>

                    <!-- 蓝图反馈区 -->
                    <div class="feedback-section">
                        <div class="form-group">
                            <label for="blueprintFeedbackInput">修改意见</label>
                            <textarea id="blueprintFeedbackInput" placeholder="例如: 希望增加一个关于AI伦理风险的章节、调整章节顺序等"></textarea>
                        </div>
                        <div class="feedback-actions">
                            <button class="btn" onclick="reviseBlueprint()">提交修改意见</button>
                            <button class="btn btn-secondary" onclick="toggleBlueprintEdit()">编辑蓝图</button>
                            <button class="btn btn-secondary" onclick="rollbackBlueprint()">回退版本</button>
                            <button class="btn btn-success" onclick="confirmBlueprint()">确认蓝图，生成大纲</button>
                            <button class="btn btn-secondary" onclick="backToStep1()">返回填写任务</button>
                        </div>
                    </div>

                    <!-- 蓝图版本历史 -->
                    <div id="blueprintHistorySection" style="display: none; margin-top: 16px;">
                        <label>蓝图版本历史</label>
                        <div id="blueprintHistoryList"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 3: 大纲审核 -->
        <div class="step-content" id="step3">
            <div class="card">
                <h3>Step 3: 大纲审核</h3>
                <div id="outlineLoading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>正在生成大纲，请稍候...</p>
                </div>
                <div id="outlineError" class="error" style="display: none;"></div>

                <div id="outlineSection" style="display: none;">
                    <!-- 大纲预览 -->
                    <div class="form-group">
                        <label>生成的大纲（基于策略蓝图）</label>
                        <div class="outline-display" id="outlineDisplay"></div>
                    </div>

                    <!-- 反馈区 -->
                    <div class="feedback-section">
                        <div class="form-group">
                            <label for="feedbackInput">修改意见</label>
                            <textarea id="feedbackInput" placeholder="例如: 希望增加一个关于AI伦理风险的章节、调整章节顺序等"></textarea>
                        </div>
                        <div class="feedback-actions">
                            <button class="btn" onclick="reviseOutline()">提交修改意见</button>
                            <button class="btn btn-secondary" onclick="toggleOutlineEdit()">编辑大纲</button>
                            <button class="btn btn-success" onclick="confirmOutline()">确认大纲，开始写作</button>
                            <button class="btn btn-secondary" onclick="backToBlueprint()">返回策略蓝图</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 4: 生成文章 -->
        <div class="step-content" id="step4">
            <div class="card">
                <h3>Step 4: 生成文章</h3>
                <div id="articleLoading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>正在生成文章，请稍候...</p>
                </div>
                <div id="articleError" class="error" style="display: none;"></div>

                <div id="articleSection" style="display: none;">
                    <div class="form-group">
                        <label>生成的文章</label>
                        <div class="result-meta" id="resultMeta"></div>
                        <div class="article-content" id="articleContent"></div>
                    </div>
                    <div class="sources" id="sourcesSection" style="display: none;">
                        <h4>知识来源</h4>
                        <div id="sources"></div>
                    </div>
                </div>

                <div style="margin-top: 16px;">
                    <button class="btn" onclick="copyArticle()">复制文章</button>
                    <button class="btn btn-secondary" onclick="downloadArticle()">下载文章</button>
                    <button class="btn btn-secondary" onclick="backToOutline()">返回修改大纲</button>
                    <button class="btn btn-success" onclick="regenerateArticle()">重新生成文章</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // ============ 状态管理 ============
        const wizardState = {
            currentStep: 1,
            taskData: {},
            outlineData: null,
            blueprintData: null,
            blueprintHistory: [],  // 蓝图版本历史
            blueprintConfirmed: false,  // 蓝图是否已确认
            revisionCount: 0,
            isLoading: false,
            isOutlineEditMode: false,
            isBlueprintEditMode: false,
        };
        let supplementaryMaterials = [];

        // ============ 步骤控制 ============
        function goToStep(step) {
            wizardState.currentStep = step;
            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            document.getElementById('step' + step).classList.add('active');

            // 更新步骤指示器（支持4步）
            for (let i = 1; i <= 4; i++) {
                const indicator = document.getElementById('step' + i + 'Indicator');
                if (indicator) {
                    indicator.classList.remove('active', 'completed');
                    if (i < step) indicator.classList.add('completed');
                    if (i === step) indicator.classList.add('active');
                }
            }

            window.scrollTo(0, 0);
        }

        // ============ 补充资料 ============
        function switchTab(tab) {
            document.querySelectorAll('.supplementary-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.supplementary-panel').forEach(p => p.classList.remove('active'));
            document.getElementById('panel-' + tab).classList.add('active');
            event.target.classList.add('active');
        }

        function addUrl() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url) { alert('请输入URL'); return; }
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                alert('请输入有效的URL'); return;
            }
            supplementaryMaterials.push({ type: 'url', source: url, title: url.length > 50 ? url.substring(0, 50) + '...' : url });
            document.getElementById('urlInput').value = '';
            renderSupplementaryList();
        }

        function addText() {
            const content = document.getElementById('textInput').value.trim();
            const title = document.getElementById('textTitle').value.trim() || '粘贴文本';
            if (!content) { alert('请输入文本内容'); return; }
            supplementaryMaterials.push({ type: 'text', source: content, title: title });
            document.getElementById('textInput').value = '';
            document.getElementById('textTitle').value = '';
            renderSupplementaryList();
        }

        function handleSuppFilesSelect(input) {
            for (let file of input.files) {
                const ext = file.name.split('.').pop().toLowerCase();
                const reader = new FileReader();
                reader.onload = function(e) {
                    supplementaryMaterials.push({ type: 'file', source: e.target.result, title: file.name, name: file.name, ext: ext });
                    renderSupplementaryList();
                };
                if (['docx', 'xlsx'].includes(ext)) reader.readAsDataURL(file);
                else reader.readAsText(file);
            }
            input.value = '';
        }

        function removeSupplementary(index) {
            supplementaryMaterials.splice(index, 1);
            renderSupplementaryList();
        }

        function renderSupplementaryList() {
            const listEl = document.getElementById('supplementaryList');
            if (supplementaryMaterials.length === 0) {
                listEl.innerHTML = '<div class="supplementary-empty">暂无补充资料</div>';
                return;
            }
            const typeLabels = { url: '链接', text: '文本', file: '文件' };
            listEl.innerHTML = supplementaryMaterials.map((m, i) => `
                <div class="supplementary-item">
                    <div class="supplementary-item-info">
                        <div class="supplementary-item-title">${m.title}</div>
                        <div class="supplementary-item-meta">${m.ext ? '(' + m.ext.toUpperCase() + ')' : '(' + typeLabels[m.type] + ')'}</div>
                    </div>
                    <button type="button" class="btn btn-sm btn-danger" onclick="removeSupplementary(${i})">删除</button>
                </div>
            `).join('');
        }

        // 文件拖拽
        document.getElementById('suppFiles').addEventListener('change', function() { handleSuppFilesSelect(this); });

        // ============ 状态检查 ============
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                document.getElementById('status').innerHTML = `
                    <div class="status-item"><span>Milvus:</span><span>${data.milvus.exists ? '已连接 (' + data.milvus.row_count + '条)' : '未连接'}</span></div>
                    <div class="status-item"><span>Embedding:</span><span>${data.embedding_model} ${data.embedding_loaded ? '✓' : ''}</span></div>
                    <div class="status-item"><span>LLM:</span><span>${data.llm_provider} / ${data.llm_model}</span></div>
                `;
            } catch (error) {
                document.getElementById('status').innerHTML = '<div class="error">状态加载失败</div>';
            }
        }

        // ============ Step 1: 生成策略蓝图 ============
        document.getElementById('taskForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            if (wizardState.isLoading) return;

            const topic = document.getElementById('topic').value.trim();
            if (!topic) { alert('请输入话题'); return; }

            wizardState.isLoading = true;
            wizardState.taskData = {
                topic: topic,
                requirements: document.getElementById('requirements').value.trim(),
                keywords: document.getElementById('keywords').value.split(',').map(k => k.trim()).filter(k => k),
                length: document.getElementById('length').value.trim() || null,
                top_k: parseInt(document.getElementById('topK').value),
                supplementary_sources: supplementaryMaterials.map(m => m.source),
            };

            document.getElementById('blueprintLoading').style.display = 'block';
            document.getElementById('blueprintError').style.display = 'none';
            document.getElementById('blueprintSection').style.display = 'none';
            document.getElementById('generateOutlineBtn').disabled = true;
            document.getElementById('blueprintLoading').innerHTML = '<div class="spinner"></div><p>正在生成策略蓝图，请稍候...</p>';

            try {
                const response = await fetch('/api/generate_blueprint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(wizardState.taskData),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                // 保存蓝图数据和历史
                wizardState.blueprintData = data;
                wizardState.blueprintHistory = [JSON.parse(JSON.stringify(data))];  // 深拷贝
                wizardState.outlineData = null;
                wizardState.blueprintConfirmed = false;
                wizardState.revisionCount = 0;

                // 显示蓝图文案
                document.getElementById('blueprintDisplay').innerHTML = '<pre style="white-space: pre-wrap; font-size: 13px; background: #f8f9fa; padding: 16px; border-radius: 6px; max-height: 500px; overflow-y: auto;">' + (data.blueprint_markdown || '蓝图生成成功') + '</pre>';
                document.getElementById('blueprintSection').style.display = 'block';
                document.getElementById('blueprintHistorySection').style.display = 'none';
                goToStep(2);
            } catch (error) {
                document.getElementById('blueprintError').textContent = error.message;
                document.getElementById('blueprintError').style.display = 'block';
            } finally {
                wizardState.isLoading = false;
                document.getElementById('blueprintLoading').style.display = 'none';
                document.getElementById('generateOutlineBtn').disabled = false;
            }
        });

        // ============ Step 2: 策略蓝图审核 ============
        function toggleBlueprintEdit() {
            if (!wizardState.blueprintData) {
                alert('无蓝图数据');
                return;
            }
            wizardState.isBlueprintEditMode = !wizardState.isBlueprintEditMode;
            const display = document.getElementById('blueprintDisplay');
            const currentBlueprint = wizardState.blueprintData?.blueprint_markdown || '';

            if (wizardState.isBlueprintEditMode) {
                display.style.display = 'none';
                const textarea = document.createElement('textarea');
                textarea.id = 'blueprintEditText';
                textarea.className = 'outline-editor';
                textarea.value = currentBlueprint;
                textarea.style.display = 'block';
                display.parentNode.insertBefore(textarea, display.nextSibling);
            } else {
                const textarea = document.getElementById('blueprintEditText');
                if (textarea) {
                    wizardState.blueprintData.blueprint_markdown = textarea.value;
                    textarea.remove();
                }
                display.innerHTML = '<pre style="white-space: pre-wrap; font-size: 13px; background: #f8f9fa; padding: 16px; border-radius: 6px; max-height: 500px; overflow-y: auto;">' + (wizardState.blueprintData?.blueprint_markdown || '') + '</pre>';
                display.style.display = 'block';
            }
        }

        async function reviseBlueprint() {
            if (wizardState.isLoading) return;
            const feedback = document.getElementById('blueprintFeedbackInput').value.trim();
            if (!feedback) { alert('请输入修改意见'); return; }
            if (!wizardState.blueprintData) {
                alert('无蓝图数据，请重新生成');
                return;
            }

            wizardState.isLoading = true;
            document.getElementById('blueprintLoading').style.display = 'block';
            document.getElementById('blueprintError').style.display = 'none';

            // 如果用户在编辑模式，获取编辑后的蓝图内容
            let revisedBlueprintMarkdown = null;
            if (wizardState.isBlueprintEditMode) {
                const textarea = document.getElementById('blueprintEditText');
                if (textarea) {
                    revisedBlueprintMarkdown = textarea.value;
                    // 退出编辑模式
                    wizardState.isBlueprintEditMode = false;
                }
            }

            try {
                const response = await fetch('/api/revise_blueprint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: wizardState.taskData.topic,
                        original_feedback: feedback,
                        revised_blueprint_markdown: revisedBlueprintMarkdown,
                        original_blueprint: wizardState.blueprintData?.blueprint || null,
                        supplementary_sources: wizardState.taskData.supplementary_sources,
                    }),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                // 保存到历史（当前版本）
                wizardState.blueprintHistory.push(JSON.parse(JSON.stringify(data)));
                wizardState.blueprintData = data;
                wizardState.revisionCount++;

                document.getElementById('blueprintDisplay').innerHTML = '<pre style="white-space: pre-wrap; font-size: 13px; background: #f8f9fa; padding: 16px; border-radius: 6px; max-height: 500px; overflow-y: auto;">' + (data.blueprint_markdown || '蓝图生成成功') + '</pre>';
                document.getElementById('blueprintFeedbackInput').value = '';
            } catch (error) {
                document.getElementById('blueprintError').textContent = error.message;
                document.getElementById('blueprintError').style.display = 'block';
            } finally {
                wizardState.isLoading = false;
                document.getElementById('blueprintLoading').style.display = 'none';
            }
        }

        function rollbackBlueprint() {
            if (wizardState.blueprintHistory.length <= 1) {
                alert('没有可回退的版本');
                return;
            }
            // 弹出选择版本的提示（简化版，实际可用模态框）
            const versionIndex = prompt('请输入要回退的版本号（1-' + wizardState.blueprintHistory.length + '）：\n当前版本：' + wizardState.blueprintHistory.length + '\n（输入数字，回车确认）');
            if (versionIndex === null) return;  // 用户取消

            const idx = parseInt(versionIndex);
            if (isNaN(idx) || idx < 1 || idx > wizardState.blueprintHistory.length) {
                alert('无效的版本号');
                return;
            }

            // 回退到指定版本（不包括当前，选定版本）
            wizardState.blueprintData = JSON.parse(JSON.stringify(wizardState.blueprintHistory[idx - 1]));
            document.getElementById('blueprintDisplay').innerHTML = '<pre style="white-space: pre-wrap; font-size: 13px; background: #f8f9fa; padding: 16px; border-radius: 6px; max-height: 500px; overflow-y: auto;">' + (wizardState.blueprintData?.blueprint_markdown || '') + '</pre>';
            alert('已回退到版本 ' + idx);
        }

        async function confirmBlueprint() {
            // 如果用户在编辑模式，先保存编辑内容
            if (wizardState.isBlueprintEditMode) {
                const textarea = document.getElementById('blueprintEditText');
                if (textarea) {
                    wizardState.blueprintData.blueprint_markdown = textarea.value;
                    textarea.remove();
                    document.getElementById('blueprintDisplay').style.display = 'block';
                    wizardState.isBlueprintEditMode = false;
                }
            }

            wizardState.blueprintConfirmed = true;
            wizardState.isLoading = true;
            document.getElementById('outlineLoading').style.display = 'block';
            document.getElementById('outlineError').style.display = 'none';
            document.getElementById('outlineSection').style.display = 'none';
            document.getElementById('outlineLoading').innerHTML = '<div class="spinner"></div><p>正在基于策略蓝图生成大纲，请稍候...</p>';

            try {
                // 基于蓝图生成大纲
                const response = await fetch('/api/generate_outline_from_blueprint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        blueprint: wizardState.blueprintData.blueprint,
                        topic: wizardState.taskData.topic,
                        supplementary_sources: wizardState.taskData.supplementary_sources,
                    }),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                wizardState.outlineData = data;
                document.getElementById('outlineDisplay').textContent = data.outline;
                document.getElementById('outlineSection').style.display = 'block';
                goToStep(3);
            } catch (error) {
                document.getElementById('outlineError').textContent = error.message;
                document.getElementById('outlineError').style.display = 'block';
            } finally {
                wizardState.isLoading = false;
                document.getElementById('outlineLoading').style.display = 'none';
            }
        }

        function backToBlueprint() {
            goToStep(2);
        }

        // ============ Step 3: 大纲审核 ============
        function toggleOutlineEdit() {
            if (!wizardState.outlineData) {
                alert('无大纲数据');
                return;
            }
            wizardState.isOutlineEditMode = !wizardState.isOutlineEditMode;
            const display = document.getElementById('outlineDisplay');
            const currentOutline = wizardState.outlineData?.outline || '';

            if (wizardState.isOutlineEditMode) {
                display.style.display = 'none';
                const textarea = document.createElement('textarea');
                textarea.id = 'outlineEditText';
                textarea.className = 'outline-editor';
                textarea.value = currentOutline;
                textarea.style.display = 'block';
                textarea.onchange = function() {
                    if (wizardState.outlineData) {
                        wizardState.outlineData.outline = this.value;
                    }
                };
                display.parentNode.insertBefore(textarea, display.nextSibling);
            } else {
                const textarea = document.getElementById('outlineEditText');
                if (textarea) {
                    if (wizardState.outlineData) {
                        wizardState.outlineData.outline = textarea.value;
                    }
                    textarea.remove();
                }
                display.textContent = currentOutline;
                display.style.display = 'block';
            }
        }

        async function reviseOutline() {
            if (wizardState.isLoading) return;
            const feedback = document.getElementById('feedbackInput').value.trim();
            if (!feedback) { alert('请输入修改意见'); return; }
            if (!wizardState.outlineData) {
                alert('无大纲数据，请重新生成');
                return;
            }

            wizardState.isLoading = true;
            document.getElementById('outlineLoading').style.display = 'block';
            document.getElementById('outlineError').style.display = 'none';

            try {
                // 如果用户在编辑模式，获取编辑后的大纲内容
                let revisedOutline = null;
                if (wizardState.isOutlineEditMode) {
                    const textarea = document.getElementById('outlineEditText');
                    if (textarea) {
                        revisedOutline = textarea.value;
                        wizardState.isOutlineEditMode = false;
                    }
                }

                const response = await fetch('/api/revise_outline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        original_outline: wizardState.outlineData?.outline || '',
                        feedback: feedback,
                        revised_outline: revisedOutline,
                        supplementary_sources: wizardState.taskData.supplementary_sources,
                    }),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                wizardState.outlineData = data;
                wizardState.revisionCount++;
                document.getElementById('outlineDisplay').textContent = data.outline;
                document.getElementById('feedbackInput').value = '';
            } catch (error) {
                document.getElementById('outlineError').textContent = error.message;
                document.getElementById('outlineError').style.display = 'block';
            } finally {
                wizardState.isLoading = false;
                document.getElementById('outlineLoading').style.display = 'none';
            }
        }

        function confirmOutline() {
            // 如果用户在编辑模式，先保存编辑内容
            if (wizardState.isOutlineEditMode) {
                const textarea = document.getElementById('outlineEditText');
                if (textarea) {
                    if (wizardState.outlineData) {
                        wizardState.outlineData.outline = textarea.value;
                    }
                    textarea.remove();
                    document.getElementById('outlineDisplay').style.display = 'block';
                    wizardState.isOutlineEditMode = false;
                }
            }

            // 确认大纲，进入Step 4生成文章
            wizardState.taskData.confirmedOutline = wizardState.outlineData?.outline || '';
            goToStep(4);
            writeArticle();
        }

        // ============ Step 4: 生成文章 ============
        async function writeArticle() {
            document.getElementById('articleLoading').style.display = 'block';
            document.getElementById('articleError').style.display = 'none';
            document.getElementById('articleSection').style.display = 'none';
            document.getElementById('articleLoading').innerHTML = '<div class="spinner"></div><p>正在生成文章，请稍候...</p>';

            try {
                // 从大纲写作
                const response = await fetch('/api/write_from_outline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        outline: wizardState.taskData.confirmedOutline,
                        topic: wizardState.taskData.topic,
                        supplementary_sources: wizardState.taskData.supplementary_sources,
                    }),
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                document.getElementById('articleContent').textContent = data.article;
                const metaText = `模型: ${data.model} | 生成时间: ${data.generation_time.toFixed(2)}s`;
                document.getElementById('resultMeta').textContent = metaText;
                document.getElementById('articleSection').style.display = 'block';

                if (data.knowledge_sources && data.knowledge_sources.length > 0) {
                    document.getElementById('sources').innerHTML = data.knowledge_sources.map((s, i) =>
                        `<div class="source-item"><div class="source-title">${i+1}. ${s.title}</div><div class="source-meta">${s.author || ''} ${s.date ? '| ' + s.date : ''}</div></div>`
                    ).join('');
                    document.getElementById('sourcesSection').style.display = 'block';
                }
            } catch (error) {
                document.getElementById('articleError').textContent = error.message;
                document.getElementById('articleError').style.display = 'block';
            } finally {
                document.getElementById('articleLoading').style.display = 'none';
            }
        }

        function backToOutline() {
            goToStep(3);  // 返回大纲审核
        }

        function backToStep1() {
            goToStep(1);
        }

        function regenerateArticle() {
            if (wizardState.isLoading) return;
            writeArticle();
        }

        function copyArticle() {
            const content = document.getElementById('articleContent').textContent;
            navigator.clipboard.writeText(content).then(() => alert('文章已复制'));
        }

        function downloadArticle() {
            const content = document.getElementById('articleContent').textContent;
            const blob = new Blob(['# ' + wizardState.taskData.topic + '\n\n' + content], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `article_${Date.now()}.md`;
            a.click();
            URL.revokeObjectURL(url);
        }

        // ============ 初始化 ============
        document.addEventListener('DOMContentLoaded', function() {
            checkStatus();
            renderSupplementaryList();
            initFeedbackButtons();
        });

        // ============= 用户反馈入库 (协同入库) =============
        // 当前激活的 preview (用户确认后传给 /api/feedback/confirm)
        let _activePreview = null;

        function initFeedbackButtons() {
            // 给两个反馈 textarea 各加一个"📌 标记为反馈"按钮
            const pairs = [
                { textarea: 'blueprintFeedbackInput', stage: 'blueprint' },
                { textarea: 'feedbackInput', stage: 'outline' },
            ];
            pairs.forEach(({ textarea, stage }) => {
                const ta = document.getElementById(textarea);
                if (!ta) return;
                // 找最近 .form-group 的 label, 按钮塞进 label 后
                const label = ta.parentNode.querySelector('label');
                if (!label) return;
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'feedback-pin-btn';
                btn.textContent = '📌 标记为反馈 (入库 wiki)';
                btn.onclick = () => markAsFeedback(textarea, stage);
                label.appendChild(btn);
            });
        }

        async function markAsFeedback(textareaId, stage) {
            const ta = document.getElementById(textareaId);
            const message = (ta?.value || '').trim();
            if (!message) {
                alert('请先输入反馈内容');
                return;
            }
            // 找最近反馈区, 在 textarea 下方插入"分析中..."
            const container = ta.closest('.feedback-section') || ta.parentNode;
            let preview = container.querySelector('.feedback-preview');
            if (!preview) {
                preview = document.createElement('div');
                preview.className = 'feedback-preview';
                ta.parentNode.insertBefore(preview, ta.nextSibling);
            }
            preview.innerHTML = '🔄 正在分析反馈 (调 LLM)...';

            try {
                const resp = await fetch('/api/feedback/capture', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_message: message,
                        context_history: window.wizardState?.blueprintHistory || [],
                        product: 'wangzhe',  // TODO: 从表单取
                        topic: window.wizardState?.taskData?.topic || '',
                    }),
                });
                const data = await resp.json();
                if (data.error) throw new Error(data.error);
                const p = data.preview;
                _activePreview = p;
                if (p.feedback_type === 'none') {
                    preview.innerHTML = `<span class="feedback-badge none">无价值</span> ${p.reason} (conf=${p.confidence.toFixed(2)})`;
                    return;
                }
                // 显示可入库摘要 + "查看详情/确认入库" 按钮
                const typeLabel = data.feedback_types[p.feedback_type] || p.feedback_type;
                const targetLabel = p.target === 'wiki' ? '走 ingest → wiki' : '写 log';
                const factsStr = JSON.stringify(p.candidate_facts || {}, null, 2);
                preview.innerHTML = `
                    <div>
                        <span class="feedback-badge ${p.target === 'wiki' ? 'fact' : (p.feedback_type === 'style_preference' ? 'style' : 'topic')}">
                            ${typeLabel}
                        </span>
                        <span style="color:#6e7781; font-size:12px;">
                            conf=${p.confidence.toFixed(2)} · 目标: ${targetLabel}
                        </span>
                    </div>
                    <div style="margin-top:6px; color:#57606a;">${p.reason}</div>
                    <div style="margin-top:6px;">
                        <button class="feedback-pin-btn" onclick="openFeedbackModal()">📋 查看候选事实 / 确认入库</button>
                        <button class="feedback-pin-btn" onclick="dismissFeedback(this)">✕ 忽略</button>
                    </div>
                `;
            } catch (e) {
                preview.innerHTML = `<span class="feedback-badge none">错误</span> ${e.message}`;
            }
        }

        function openFeedbackModal() {
            if (!_activePreview || _activePreview.feedback_type === 'none') {
                alert('没有可入库的反馈');
                return;
            }
            const modal = document.getElementById('feedbackModal');
            document.getElementById('modalType').textContent = _activePreview.feedback_type;
            document.getElementById('modalConf').textContent = _activePreview.confidence.toFixed(2);
            document.getElementById('modalTarget').textContent = _activePreview.target;
            document.getElementById('modalReason').textContent = _activePreview.reason;
            document.getElementById('modalFacts').value = JSON.stringify(
                _activePreview.candidate_facts || {}, null, 2
            );
            modal.classList.add('active');
        }

        function closeFeedbackModal() {
            document.getElementById('feedbackModal').classList.remove('active');
        }

        async function confirmFeedback() {
            if (!_activePreview) return;
            let editedFacts = {};
            try {
                editedFacts = JSON.parse(document.getElementById('modalFacts').value || '{}');
            } catch (e) {
                alert('候选事实 JSON 格式错误: ' + e.message);
                return;
            }
            const btn = document.querySelector('#feedbackModal .btn-confirm');
            btn.disabled = true;
            btn.textContent = '入库中...';
            try {
                const resp = await fetch('/api/feedback/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        preview_id: _activePreview.preview_id,
                        edited_payload: { candidate_facts: editedFacts },
                    }),
                });
                const data = await resp.json();
                if (data.error) throw new Error(data.error);
                let msg = `✅ 入库成功!\n动作: ${data.action}\n详情: ${data.detail}`;
                if (data.path) msg += `\n路径: ${data.path}`;
                alert(msg);
                closeFeedbackModal();
                // 清空 preview
                document.querySelectorAll('.feedback-preview').forEach(p => p.innerHTML = '');
                _activePreview = null;
            } catch (e) {
                alert('入库失败: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '✅ 确认入库';
            }
        }

        function dismissFeedback(btn) {
            const preview = btn.closest('.feedback-preview');
            if (preview) preview.innerHTML = '';
            _activePreview = null;
        }
    </script>

    <!-- 用户反馈入库 Modal -->
    <div id="feedbackModal" class="feedback-modal-bg" onclick="if(event.target===this) closeFeedbackModal()">
        <div class="feedback-modal">
            <h3>📌 确认反馈入库</h3>
            <div class="modal-row"><label>类型:</label> <span id="modalType"></span></div>
            <div class="modal-row"><label>置信度:</label> <span id="modalConf"></span></div>
            <div class="modal-row"><label>入库目标:</label> <span id="modalTarget"></span></div>
            <div class="modal-row"><label>原因:</label> <div id="modalReason"></div></div>
            <div class="modal-row">
                <label>候选事实 (可编辑 JSON):</label>
                <textarea id="modalFacts"></textarea>
            </div>
            <div class="modal-actions">
                <button class="btn-cancel" onclick="closeFeedbackModal()">取消</button>
                <button class="btn-confirm" onclick="confirmFeedback()">✅ 确认入库</button>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    """主页"""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'templates'),
        'index.html'
    )


@app.route("/api/brainstorm", methods=["POST"])
def api_brainstorm():
    """头脑风暴：基于产品知识库生成切入角度"""
    data = request.get_json()
    topic = data.get("topic", "")
    background = data.get("background", "")
    requirements = data.get("requirements", "")
    keywords = data.get("keywords", [])
    product_filter = data.get("product")
    selected_angle = data.get("selected_angle")
    user_feedback = data.get("user_feedback", "")
    brainstorm_history = data.get("brainstorm_history", [])

    try:
        writer_instance = get_writer()

        # 1. 检索产品知识库 (混合模式: Wiki 优先, RAG 兜底)
        product_context = ""
        available_products = []
        knowledge_mode = getattr(settings.wiki, "knowledge_mode", "hybrid")

        def _format_results(kb_results, fallback_used=""):
            """把检索结果格式化为 product_context 字符串"""
            product_parts = []
            for r in kb_results:
                product_parts.append(
                    f"[{r['product_display']}] {r['title']} | {r['date']}\n{r['content_text'][:300]}..."
                )
            ctx = "\n\n".join(product_parts)
            if fallback_used:
                ctx = f"（Wiki 检索失败, 已降级到 Milvus RAG 兜底: {fallback_used}）\n\n" + ctx
            return ctx

        try:
            # 构建搜索查询
            search_parts = [topic]
            if background:
                search_parts.append(background)
            if requirements:
                search_parts.append(requirements)
            search_query = " ".join(search_parts)

            kb_results = []
            knowledge_mode_fallback = False

            if knowledge_mode in ("wiki", "hybrid"):
                # === Wiki 模式: 调本机 LLM-Wiki ===
                try:
                    from wiki_product_backend import WikiProductBackend
                    wiki_backend = WikiProductBackend(
                        verbose=False,
                        timeout_sec=settings.wiki.timeout_sec,
                    )
                    available_products = wiki_backend.list_collections()
                    if product_filter:
                        kb_results = wiki_backend.search(
                            search_query, product=product_filter, top_k=8
                        )
                    else:
                        kb_results = wiki_backend.search(
                            search_query, product=None, top_k=10
                        )
                    print(f"[Wiki] 命中 {len(kb_results)} 条 (backend={wiki_backend.backend})")

                    # hybrid 模式: Wiki 空则降级 RAG
                    if knowledge_mode == "hybrid" and not kb_results:
                        print("[Wiki] 无结果, 降级到 Milvus RAG")
                        knowledge_mode_fallback = True
                    else:
                        product_context = _format_results(kb_results)
                except Exception as wiki_err:
                    if knowledge_mode == "wiki":
                        # 纯 Wiki 模式不允许降级
                        raise wiki_err
                    print(f"[Wiki] 检索失败 ({wiki_err}), 降级到 Milvus RAG")
                    knowledge_mode_fallback = True
                    kb_results = []

            if (not kb_results) and knowledge_mode in ("rag", "hybrid"):
                # === RAG 模式: 原 Milvus 产品库 ===
                knowledge_base_path = Path(r"e:\产品信息知识库")
                crawler_path = str(knowledge_base_path / "crawler")
                if crawler_path not in sys.path:
                    sys.path.insert(0, crawler_path)
                from product_retriever import ProductKnowledgeBase

                kb = ProductKnowledgeBase()
                available_products = kb.list_collections()
                available_products = [
                    p for p in available_products if p.get("status") == "ready"
                ]

                if product_filter:
                    kb_results = kb.search(search_query, product=product_filter, top_k=8)
                else:
                    kb_results = kb.search(search_query, product=None, top_k=10)

                fallback_msg = "Wiki 无结果" if knowledge_mode_fallback else ""
                product_context = _format_results(kb_results, fallback_used=fallback_msg)
                print(f"[RAG] 命中 {len(kb_results)} 条")

        except Exception as e:
            print(f"产品知识库检索失败，继续无产品上下文的头脑风暴: {e}")
            product_context = "（产品知识库暂时不可用，请基于话题进行头脑风暴）"

        # 2. 检索策略案例（专业优质文章，用于学习深度思考方法）
        strategy_case_context = ""
        try:
            skill_agent = writer_instance.create_skill_agent(case_base_path="./strategy_cases")
            similar_cases = skill_agent.retriever.retrieve(
                query=f"{topic} {background}",
                top_k=5,
            )
            if similar_cases:
                case_parts = []
                for i, case in enumerate(similar_cases, 1):
                    annotation = case.annotation
                    section_examples = ""
                    if annotation.section_strategies:
                        section_examples = "\n".join([
                            f"    - {s.section_title}: {s.structural_approach}手法, 重点「{s.content_focus}」"
                            for s in annotation.section_strategies[:3]
                        ])
                    case_parts.append(f"""【优质范文 {i}】《{case.title}》
  开篇方式: {annotation.opening_approach}（效果: {annotation.opening_effectiveness}/5）
  结构模式: {annotation.structural_pattern}
  核心张力: {annotation.core_tension or '未标注'}
  章节策略:
{section_examples}
  收尾方式: {annotation.closing_approach}（效果: {annotation.closing_effectiveness}/5）
  风格特征: {', '.join(annotation.style_features[:5]) if annotation.style_features else '未标注'}
  亮点手法: {', '.join(annotation.notable_techniques[:3]) if annotation.notable_techniques else '未标注'}""")
                strategy_case_context = "\n\n".join(case_parts)
                print(f"检索到 {len(similar_cases)} 个策略案例作为深度思考范本")
        except Exception as e:
            print(f"策略案例检索失败（不影响继续）: {e}")

        # 3. 构建头脑风暴提示词（含策略案例参考）
        from rag_writer.skill_agent.prompts import SkillPromptBuilder
        builder = SkillPromptBuilder()
        prompt = builder.build_brainstorm_prompt(
            topic=topic,
            background=background,
            requirements=requirements,
            keywords=keywords,
            product_context=product_context,
            selected_angle=selected_angle,
            user_feedback=user_feedback,
            brainstorm_history=brainstorm_history,
            strategy_case_context=strategy_case_context,
        )

        # 4. 调用LLM
        response = writer_instance.llm_client.generate_with_system(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=0.7,
            max_tokens=4096,
        )

        # 5. 解析角度
        angles = _parse_brainstorm_angles(response.content)

        # 6. === 用户反馈采集 (协同入库) ===
        #    自动检测 user_feedback 是否含"可入库"价值, 有则附带 preview 给前端展示
        feedback_preview = None
        if user_feedback and len(user_feedback.strip()) >= 4:
            try:
                from rag_writer.feedback_capture import get_capture
                fc = get_capture(llm_client=writer_instance.llm_client)
                feedback_preview = fc.capture_preview(
                    user_message=user_feedback,
                    context_history=brainstorm_history,
                    product=product_filter or "wangzhe",
                    topic=topic,
                )
                # 只在识别到"可入库"反馈时才返回
                if feedback_preview.get("feedback_type") == "none":
                    feedback_preview = None
            except Exception as e:
                print(f"[brainstorm] feedback capture failed: {e}")

        return jsonify({
            "angles": angles,
            "product_context": product_context,
            "available_products": [
                {"collection": p.get("collection", ""), "display_name": p.get("display_name", ""), "article_count": p.get("article_count", 0)}
                for p in available_products
            ],
            "feedback_preview": feedback_preview,  # 非 None 时前端展示入库按钮
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


# ============= 用户反馈采集 (协同入库) =============

@app.route("/api/feedback/capture", methods=["POST"])
def api_feedback_capture():
    """
    LLM 实时识别用户消息是否含"可入库"反馈 (事实纠正/补充/偏好)
    返回 preview dict, 供前端展示候选入库内容, 等用户确认
    """
    data = request.get_json() or {}
    user_message = (data.get("user_message") or "").strip()
    context_history = data.get("context_history") or []
    product = data.get("product") or "wangzhe"
    topic = data.get("topic") or ""

    if not user_message:
        return jsonify({"error": "user_message 不能为空"}), 400

    try:
        from rag_writer.feedback_capture import get_capture
        writer_instance = get_writer()
        fc = get_capture(llm_client=writer_instance.llm_client)
        preview = fc.capture_preview(
            user_message=user_message,
            context_history=context_history,
            product=product,
            topic=topic,
        )
        return jsonify({
            "preview": preview,
            "feedback_types": {
                "fact_correction": "事实纠正 (走 ingest)",
                "fact_supplement": "事实补充 (走 ingest)",
                "fact_contradiction_flag": "事实纠错 (高优, 走 ingest)",
                "style_preference": "风格偏好 (写 log)",
                "topic_pivot": "选题调整 (写 log)",
                "quality_rating": "质量评分 (写 log)",
                "none": "无可入库反馈",
            },
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/feedback/confirm", methods=["POST"])
def api_feedback_confirm():
    """
    用户确认入库: 走 ingest 管道 (事实类) 或写 log (偏好类)
    Body: {"preview_id": "fb_xxx", "edited_payload": {...} (可选)}
    """
    data = request.get_json() or {}
    preview_id = (data.get("preview_id") or "").strip()
    edited_payload = data.get("edited_payload") or {}

    if not preview_id:
        return jsonify({"error": "preview_id 不能为空"}), 400

    try:
        from rag_writer.feedback_capture import get_capture
        fc = get_capture()
        result = fc.confirm_and_write(preview_id, edited_payload)
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/feedback/list", methods=["GET"])
def api_feedback_list():
    """列出最近的 feedback 预览 + log (调试用)"""
    try:
        from rag_writer.feedback_capture import get_capture
        fc = get_capture()
        return jsonify({
            "previews": fc.list_previews(limit=20),
            "log": fc.list_log(limit=20),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def api_status():
    """获取系统状态"""
    try:
        writer_instance = get_writer()
        status = writer_instance.check_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/write", methods=["POST"])
def api_write():
    """执行写作"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        topic = data.get("topic", "")
        requirements = data.get("requirements", "")

        # 处理文件上传
        if data.get("file"):
            file_info = data["file"]
            file_name = file_info.get("name", "")
            file_content = file_info.get("content", "")
            file_type = file_info.get("type", "text")

            if file_name.endswith('.docx') or file_type == 'base64':
                # docx文件：需要解析base64内容
                from rag_writer.document_parser import WordParser
                import base64
                import tempfile

                # 将base64写入临时文件
                try:
                    binary_data = base64.b64decode(file_content.split(',')[1] if ',' in file_content else file_content)
                except:
                    binary_data = base64.b64decode(file_content)

                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                    tmp.write(binary_data)
                    tmp_path = tmp.name

                try:
                    parser = WordParser()
                    parsed_content = parser.parse(tmp_path)
                    # 解析docx内容
                    from rag_writer.document_parser import extract_topic_from_text
                    topic_info = extract_topic_from_text(parsed_content)
                    if not topic:
                        topic = topic_info['topic']
                    if not requirements:
                        requirements = parsed_content
                finally:
                    import os
                    os.unlink(tmp_path)

            elif file_name.endswith('.txt') or file_type == 'text':
                # txt文件：直接使用内容
                from rag_writer.document_parser import extract_topic_from_text
                topic_info = extract_topic_from_text(file_content)
                if not topic:
                    topic = topic_info['topic']
                if not requirements:
                    requirements = file_content

        # 处理补充资料
        supplementary_sources = data.get("supplementary_sources", [])

        result = writer_instance.write(
            topic=topic,
            requirements=requirements,
            keywords=data.get("keywords", []),
            length=data.get("length"),
            top_k=data.get("top_k", 5),
            supplementary_sources=supplementary_sources if supplementary_sources else None,
        )

        return jsonify({
            "article": result.article,
            "topic": result.topic,
            "model": result.model,
            "knowledge_count": result.knowledge_count,
            "knowledge_sources": result.knowledge_sources,
            "generation_time": result.generation_time,
            "usage": result.usage,
            "supplementary_count": result.supplementary_count,
            "supplementary_sources": result.supplementary_sources,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/generate_outline", methods=["POST"])
def api_generate_outline():
    """生成大纲"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        topic = data.get("topic", "")
        requirements = data.get("requirements", "")

        # 处理需求文件上传
        if data.get("file"):
            file_info = data["file"]
            file_name = file_info.get("name", "")
            file_content = file_info.get("content", "")
            file_type = file_info.get("type", "text")

            if file_name.endswith('.docx') or file_type == 'base64':
                # docx文件：需要解析base64内容
                from rag_writer.document_parser import WordParser
                import base64
                import tempfile

                # 将base64写入临时文件
                try:
                    binary_data = base64.b64decode(file_content.split(',')[1] if ',' in file_content else file_content)
                except:
                    binary_data = base64.b64decode(file_content)

                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                    tmp.write(binary_data)
                    tmp_path = tmp.name

                try:
                    parser = WordParser()
                    parsed_content = parser.parse(tmp_path)
                    # 解析docx内容
                    from rag_writer.document_parser import extract_topic_from_text
                    topic_info = extract_topic_from_text(parsed_content)
                    if not topic:
                        topic = topic_info['topic']
                    if not requirements:
                        requirements = parsed_content
                finally:
                    import os
                    os.unlink(tmp_path)

            elif file_name.endswith('.txt') or file_type == 'text':
                # txt文件：直接使用内容
                from rag_writer.document_parser import extract_topic_from_text
                topic_info = extract_topic_from_text(file_content)
                if not topic:
                    topic = topic_info['topic']
                if not requirements:
                    requirements = file_content

        # 处理补充资料
        supplementary_sources = data.get("supplementary_sources", [])

        result = writer_instance.generate_outline(
            topic=topic,
            requirements=requirements,
            keywords=data.get("keywords", []),
            length=data.get("length"),
            target_audience=data.get("target_audience"),
            perspective=data.get("perspective"),
            top_k=data.get("top_k", 5),
            supplementary_sources=supplementary_sources if supplementary_sources else None,
        )

        return jsonify({
            "outline": result.outline,
            "sections": [
                {
                    "title": s.title,
                    "description": s.description,
                    "citations": s.citations,
                    "word_count_estimate": s.word_count_estimate,
                }
                for s in result.sections
            ],
            "title": result.title,
            "topic": result.topic,
            "model": result.model,
            "knowledge_sources": result.knowledge_sources,
            "supplementary_sources": result.supplementary_sources,
            "usage": result.usage,
            "generation_time": result.generation_time,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/revise_outline", methods=["POST"])
def api_revise_outline():
    """修订大纲"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        original_outline = data.get("original_outline", "")
        feedback = data.get("feedback", "")
        revised_outline = data.get("revised_outline")
        supplementary_sources = data.get("supplementary_sources", [])

        result = writer_instance.revise_outline(
            original_outline=original_outline,
            feedback=feedback,
            revised_outline=revised_outline,
            supplementary_sources=supplementary_sources if supplementary_sources else None,
        )

        return jsonify({
            "outline": result.outline,
            "sections": [
                {
                    "title": s.title,
                    "description": s.description,
                    "citations": s.citations,
                    "word_count_estimate": s.word_count_estimate,
                }
                for s in result.sections
            ],
            "title": result.title,
            "model": result.model,
            "supplementary_sources": result.supplementary_sources,
            "usage": result.usage,
            "generation_time": result.generation_time,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/revise_blueprint", methods=["POST"])
def api_revise_blueprint():
    """修订策略蓝图（Skill模式）"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        topic = data.get("topic", "")
        background = data.get("background", "")
        requirements = data.get("requirements", "")
        original_feedback = data.get("original_feedback", "")
        revised_blueprint_markdown = data.get("revised_blueprint_markdown")
        original_blueprint = data.get("original_blueprint")
        supplementary_sources = data.get("supplementary_sources", [])

        # 创建SkillAgent
        skill_agent = writer_instance.create_skill_agent(
            case_base_path="./strategy_cases"
        )

        # 检索RAG上下文
        rag_knowledge = writer_instance.retrieve_knowledge(topic, top_k=5)

        rag_context = {
            "knowledge": rag_knowledge,
            "topic": topic,
            "background": background,
            "requirements": requirements,
            "content_type": "行业分析",
        }

        # 如果有原始蓝图和反馈，基于反馈和原蓝图修订
        if original_feedback:
            blueprint = skill_agent.revise_blueprint(
                topic=topic,
                rag_context=rag_context,
                original_blueprint=original_blueprint,
                user_feedback=original_feedback,
                revised_markdown=revised_blueprint_markdown,
                content_type="行业分析",
                target_audience="企业决策者、技术从业者",
                use_reflection=False,
                background=background,
                requirements=requirements,
            )
        else:
            # 重新生成
            blueprint = skill_agent.generate_blueprint(
                topic=topic,
                background=background,
                rag_context=rag_context,
                content_type="行业分析",
                target_audience="企业决策者、技术从业者",
                use_reflection=False,
            )

        return jsonify({
            "blueprint": blueprint.model_dump(),
            "blueprint_markdown": blueprint.to_markdown(),
            "confidence": blueprint.confidence,
            "section_count": len(blueprint.sections),
            "case_references": blueprint.meta.get('case_references', []) if blueprint.meta else [],
            "topic": topic,
            "model": writer_instance.llm_client.model,
            "knowledge_count": len(rag_knowledge),
            "knowledge_sources": [
                {"title": k.title, "author": k.author, "date": k.date, "url": k.url}
                for k in rag_knowledge
            ],
            "generation_time": blueprint.meta.get('generation_time', 0) if blueprint.meta else 0,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/generate_blueprint", methods=["POST"])
def api_generate_blueprint():
    """生成策略蓝图（Skill模式）"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        topic = data.get("topic", "")
        background = data.get("background", "")
        requirements = data.get("requirements", "")
        keywords = data.get("keywords", [])
        length = data.get("length")
        top_k = data.get("top_k", 5)
        supplementary_sources = data.get("supplementary_sources", [])

        # 处理需求文件上传
        if data.get("file"):
            file_info = data["file"]
            file_name = file_info.get("name", "")
            file_content = file_info.get("content", "")
            file_type = file_info.get("type", "text")

            if file_name.endswith('.docx') or file_type == 'base64':
                from rag_writer.document_parser import WordParser
                import base64
                import tempfile

                try:
                    binary_data = base64.b64decode(file_content.split(',')[1] if ',' in file_content else file_content)
                except:
                    binary_data = base64.b64decode(file_content)

                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                    tmp.write(binary_data)
                    tmp_path = tmp.name

                try:
                    parser = WordParser()
                    parsed_content = parser.parse(tmp_path)
                    from rag_writer.document_parser import extract_topic_from_text
                    topic_info = extract_topic_from_text(parsed_content)
                    if not topic:
                        topic = topic_info['topic']
                    if not requirements:
                        requirements = parsed_content
                finally:
                    import os
                    os.unlink(tmp_path)

            elif file_name.endswith('.txt') or file_type == 'text':
                from rag_writer.document_parser import extract_topic_from_text
                topic_info = extract_topic_from_text(file_content)
                if not topic:
                    topic = topic_info['topic']
                if not requirements:
                    requirements = file_content

        # 创建SkillAgent
        skill_agent = writer_instance.create_skill_agent(
            case_base_path="./strategy_cases"
        )

        # 检索策略案例框架（展示在策略蓝图中供用户参考）
        strategy_case_frameworks = []
        try:
            similar_cases = skill_agent.retriever.retrieve(
                query=f"{topic} {background}",
                top_k=5,
            )
            for case in similar_cases:
                annotation = case.annotation
                section_flow = []
                if annotation.section_strategies:
                    section_flow = [
                        f"{s.section_title}（{s.structural_approach}→「{s.content_focus}」）"
                        for s in annotation.section_strategies[:4]
                    ]
                strategy_case_frameworks.append({
                    "title": case.title,
                    "content_type": case.content_type,
                    "core_tension": annotation.core_tension or "",
                    "opening_approach": annotation.opening_approach,
                    "structural_pattern": annotation.structural_pattern,
                    "section_flow": section_flow,
                    "closing_approach": annotation.closing_approach,
                    "quality_score": case.quality_score,
                })
        except Exception as e:
            print(f"策略案例检索失败（不影响生成）: {e}")

        # 检索RAG上下文（用于事实支撑）
        rag_knowledge = writer_instance.retrieve_knowledge(topic, top_k=top_k)

        rag_context = {
            "knowledge": rag_knowledge,
            "topic": topic,
            "background": background,
            "requirements": requirements,
            "content_type": "行业分析",
        }

        # 提取头脑风暴结果
        brainstorm_results = data.get("brainstorm_results")

        # 生成策略蓝图（传入背景、检索文章数量、头脑风暴结果）
        blueprint = skill_agent.generate_blueprint(
            topic=topic,
            background=background,
            rag_context=rag_context,
            content_type="行业分析",
            target_audience="企业决策者、技术从业者",
            constraints={
                "requirements": requirements,
                "length": length,
                "article_count": top_k,
            },
            use_reflection=False,
            brainstorm_results=brainstorm_results,
        )

        return jsonify({
            "blueprint": blueprint.model_dump(),
            "blueprint_markdown": blueprint.to_markdown(),
            "confidence": blueprint.confidence,
            "section_count": len(blueprint.sections),
            "case_references": blueprint.meta.get('case_references', []) if blueprint.meta else [],
            "strategy_case_frameworks": strategy_case_frameworks,
            "topic": topic,
            "model": writer_instance.llm_client.model,
            "knowledge_count": len(rag_knowledge),
            "knowledge_sources": [
                {"title": k.title, "author": k.author, "date": k.date, "url": k.url}
                for k in rag_knowledge
            ],
            "generation_time": blueprint.meta.get('generation_time', 0) if blueprint.meta else 0,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/write_from_blueprint", methods=["POST"])
def api_write_from_blueprint():
    """基于策略蓝图写文章（Skill模式）"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        blueprint_data = data.get("blueprint", {})
        topic = data.get("topic", "")
        supplementary_sources = data.get("supplementary_sources", [])

        # 重建Blueprint对象
        from rag_writer.skill_agent.models import StrategyBlueprint, SectionStrategy, OpeningStrategy, ClosingStrategy, WritingTone

        sections = []
        for s in blueprint_data.get('sections', []):
            sections.append(SectionStrategy(**s))

        opening = OpeningStrategy(**blueprint_data.get('opening', {}))
        closing = ClosingStrategy(**blueprint_data.get('closing', {}))

        blueprint = StrategyBlueprint(
            version=blueprint_data.get('version', '1.0'),
            article_title=blueprint_data.get('article_title', ''),
            topic=blueprint_data.get('topic', topic),
            content_type=blueprint_data.get('content_type', '行业分析'),
            target_audience=blueprint_data.get('target_audience', '企业决策者'),
            core_tension=blueprint_data.get('core_tension', ''),
            writing_tone=WritingTone(blueprint_data.get('writing_tone', 'analytical')),
            opening=opening,
            sections=sections,
            closing=closing,
            global_style_notes=blueprint_data.get('global_style_notes', []),
            forbidden_patterns=blueprint_data.get('forbidden_patterns', []),
            case_references=blueprint_data.get('case_references', []),
            confidence=blueprint_data.get('confidence', 0.8),
            meta=blueprint_data.get('meta', {}),
        )

        # 检索RAG上下文
        rag_knowledge = writer_instance.retrieve_knowledge(topic, top_k=5)

        # 基于蓝图写作
        result = writer_instance.write_from_blueprint(
            blueprint=blueprint,
            knowledge=rag_knowledge,
            temperature=0.5,
        )

        return jsonify({
            "article": result.article,
            "topic": result.topic,
            "model": result.model,
            "knowledge_count": result.knowledge_count,
            "knowledge_sources": result.knowledge_sources,
            "generation_time": result.generation_time,
            "usage": result.usage,
            "blueprint_confidence": blueprint.confidence,
            "supplementary_count": result.supplementary_count,
            "supplementary_sources": result.supplementary_sources,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/write_from_outline", methods=["POST"])
def api_write_from_outline():
    """根据大纲写文章"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        outline = data.get("outline", "")
        topic = data.get("topic", "")
        supplementary_sources = data.get("supplementary_sources", [])

        result = writer_instance.write_from_outline(
            outline=outline,
            topic=topic,
            supplementary_sources=supplementary_sources if supplementary_sources else None,
        )

        return jsonify({
            "article": result.article,
            "topic": result.topic,
            "model": result.model,
            "knowledge_count": result.knowledge_count,
            "knowledge_sources": result.knowledge_sources,
            "generation_time": result.generation_time,
            "usage": result.usage,
            "supplementary_count": result.supplementary_count,
            "supplementary_sources": result.supplementary_sources,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


@app.route("/api/generate_outline_from_blueprint", methods=["POST"])
def api_generate_outline_from_blueprint():
    """基于策略蓝图生成大纲"""
    global writer

    data = request.get_json()

    try:
        writer_instance = get_writer()

        blueprint_data = data.get("blueprint", {})
        topic = data.get("topic", "")
        supplementary_sources = data.get("supplementary_sources", [])

        # 重建Blueprint对象
        from rag_writer.skill_agent.models import StrategyBlueprint, SectionStrategy, OpeningStrategy, ClosingStrategy, WritingTone

        sections = []
        for s in blueprint_data.get('sections', []):
            sections.append(SectionStrategy(**s))

        opening = OpeningStrategy(**blueprint_data.get('opening', {}))
        closing = ClosingStrategy(**blueprint_data.get('closing', {}))

        blueprint = StrategyBlueprint(
            version=blueprint_data.get('version', '1.0'),
            article_title=blueprint_data.get('article_title', ''),
            topic=blueprint_data.get('topic', topic),
            content_type=blueprint_data.get('content_type', '行业分析'),
            target_audience=blueprint_data.get('target_audience', '企业决策者'),
            core_tension=blueprint_data.get('core_tension', ''),
            writing_tone=WritingTone(blueprint_data.get('writing_tone', 'analytical')),
            opening=opening,
            sections=sections,
            closing=closing,
            global_style_notes=blueprint_data.get('global_style_notes', []),
            forbidden_patterns=blueprint_data.get('forbidden_patterns', []),
            case_references=blueprint_data.get('case_references', []),
            confidence=blueprint_data.get('confidence', 0.8),
            meta=blueprint_data.get('meta', {}),
        )

        # 检索RAG上下文
        rag_knowledge = writer_instance.retrieve_knowledge(topic, top_k=5)

        # 使用StrategyCompiler将蓝图转为大纲
        from rag_writer.skill_agent.compiler import StrategyCompiler
        compiler = StrategyCompiler(
            llm_client=writer_instance.llm_client,
            temperature=0.5,
        )

        rag_context = {
            "knowledge": rag_knowledge,
            "topic": topic,
            "content_type": "行业分析",
        }

        instructions = compiler.compile(blueprint, rag_context)

        # 构建大纲文本
        outline_text = instructions.instruction_text

        return jsonify({
            "outline": outline_text,
            "title": blueprint.topic,
            "topic": topic,
            "model": writer_instance.llm_client.model,
            "knowledge_sources": [
                {"title": k.title, "author": k.author, "date": k.date, "url": k.url}
                for k in rag_knowledge
            ],
            "supplementary_sources": [],
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e) + "\n" + traceback.format_exc()}), 500


def _parse_brainstorm_angles(llm_output: str) -> list:
    """解析LLM输出的角度JSON数组，分配angle_id和初始selected状态"""
    # 尝试直接解析JSON数组
    array_match = re.search(r'\[[\s\S]*\]', llm_output)
    if array_match:
        try:
            angles = json.loads(array_match.group())
            for i, angle in enumerate(angles):
                angle["angle_id"] = f"a{i+1}"
                angle["selected"] = False
                # 确保必要字段存在
                angle.setdefault("depth", 0)
                angle.setdefault("product_facts", [])
                angle.setdefault("dimension", "general")
                angle.setdefault("parent_angle_id", None)
            return angles
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON解析失败: {e}")

    # 备用方案：将整个响应作为单个角度
    return [{
        "angle_id": "a1",
        "angle_title": "从话题切入",
        "stance": llm_output[:200],
        "reasoning": "LLM未按JSON格式返回，请点击'换个思路'重试",
        "product_facts": [],
        "dimension": "general",
        "depth": 0,
        "parent_angle_id": None,
        "selected": False,
    }]


def main():
    """启动Web服务"""
    port = 5003
    print(f"""
========================================
  RAG写作系统 Web界面
========================================

  启动服务: http://localhost:{port}

  按 Ctrl+C 停止服务
========================================
    """)
    app.run(debug=False, port=port, host='0.0.0.0')


if __name__ == "__main__":
    main()
