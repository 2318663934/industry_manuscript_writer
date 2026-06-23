"""
feedback_capture.py — 用户反馈捕获与入库

🎯 目标:
    行业稿件写作系统用户交互过程中产生的"修正/补充/偏好"反馈,
    经 LLM 实时识别后, 走 ingest 管道入库 (事实类) 或写 log (偏好类).

📊 反馈类型映射:
    feedback_type              target        处理路径
    ─────────────────────────────────────────────────────
    fact_correction            wiki/99-待审  ingest_one() (合成 raw txt → 置信度门控)
    fact_supplement            wiki/99-待审  ingest_one()
    fact_contradiction_flag    99-待审       ingest_one() (高优)
    style_preference           feedback_log  state/feedback_log.jsonl
    topic_pivot                feedback_log  state/feedback_log.jsonl
    quality_rating             feedback_log  state/feedback_log.jsonl
    none (无价值)              忽略          不入库

🔧 用法:
    from feedback_capture import FeedbackCapture
    fc = FeedbackCapture(llm_client, product="honor_of_kings")
    preview = fc.capture_preview(user_message, context_history, product="honor_of_kings")
    result = fc.confirm_and_write(preview_id, edited_payload)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# === 路径 ===
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent  # E:/行业稿件写作/code/rag_writer/
_PROJECT_ROOT_PARENT = _PROJECT_ROOT.parent  # E:/行业稿件写作/code/
DEEPSEARCH_ROOT_CANDIDATES = [
    _PROJECT_ROOT_PARENT.parent.parent / "deepsearch",  # 远端服务器假设结构
    Path("e:/deepsearch").resolve(),
    Path("E:/deepsearch").resolve(),
    Path(r"e:\deepsearch").resolve(),
]

DEEPSEARCH_ROOT = None
for _cand in DEEPSEARCH_ROOT_CANDIDATES:
    if _cand.exists() and (_cand / "scripts" / "ingest.py").exists():
        DEEPSEARCH_ROOT = _cand
        break

# 状态目录 (在 E:/行业稿件写作/state/ 下)
_STATE_DIR = _PROJECT_ROOT_PARENT / "state"
STATE_DIR = _STATE_DIR
STATE_DIR.mkdir(parents=True, exist_ok=True)

FEEDBACK_LOG_PATH = STATE_DIR / "feedback_log.jsonl"
FEEDBACK_PREVIEW_CACHE_PATH = STATE_DIR / "feedback_preview_cache.json"

# === 反馈类型常量 ===
FEEDBACK_TYPES = {
    "fact_correction":          "事实纠正",
    "fact_supplement":          "事实补充",
    "fact_contradiction_flag":  "事实纠错 (高优)",
    "style_preference":         "写作风格偏好",
    "topic_pivot":              "选题方向调整",
    "quality_rating":           "稿件质量反馈",
    "none":                     "无价值",
}

# 目标决定: 走 ingest 管道 vs 仅写 log
FACT_TYPES = {"fact_correction", "fact_supplement", "fact_contradiction_flag"}
PREFERENCE_TYPES = {"style_preference", "topic_pivot", "quality_rating"}


# === LLM Prompt ===
CAPTURE_PROMPT = """你是用户反馈分类与提取助手, 负责识别用户消息是否含"可入库"的产品/写作反馈。

【用户消息】:
{user_message}

【对话上下文 (最近 {n_ctx} 轮)】:
{context_history}

【产品】: {product}
【话题】: {topic}

【任务】:
1. 判断 user_message 是否含"可入库"反馈 (产品事实 / 写作风格偏好 / 选题方向 / 质量评分)
2. 如果有, 提取:
   - feedback_type: 从以下选 1 个:
     - "fact_correction"          (用户在纠正错误事实, 例 "李白 1 技能是 8 秒不是 12 秒")
     - "fact_supplement"          (用户在补充新事实, 例 "李白还有彩蛋台词 X")
     - "fact_contradiction_flag"  (用户在标红错误, 高优, 例 "这段完全错了, 李白根本不是 X")
     - "style_preference"         (用户在表达风格偏好, 例 "下次更口语化")
     - "topic_pivot"              (用户在调整选题方向, 例 "换个角度, 聊 MMORPG 经济")
     - "quality_rating"           (用户在评质量, 例 "5 分, 但开头太长")
     - "none"                     (无可入库反馈, 例 "好的, 继续" / "看下个角度")
   - target: "wiki" (事实类) / "log" (偏好类) / "none"
   - candidate_facts: dict (key→value), 仅 fact_* 类需要 (例 {"1st_skill_cd": "8s"})
   - confidence: 0-1, 自评
   - reason: 1 句话解释

【输出 JSON Schema (严格)】:
{{
  "feedback_type": "...",
  "target": "wiki" | "log" | "none",
  "candidate_facts": {{{{}}}}  | null,
  "confidence": 0.85,
  "reason": "..."
}}
(注: candidate_facts 的 key 用方括号访问, 不要进 str.format 替换)

【硬规则】:
- 普通对话 ("好的/继续/嗯") 一定返回 none
- confidence < 0.6 也视为 none
- 只输出 JSON, 不解释
- candidate_facts 的 key 不要用 {{}} 包裹, 避免 str.format 解析冲突"""


@dataclass
class FeedbackPreview:
    """反馈捕获的预览 (用户未确认前)"""
    preview_id: str
    user_message: str
    feedback_type: str
    target: str  # "wiki" | "log" | "none"
    candidate_facts: Dict[str, Any]
    confidence: float
    reason: str
    product: str
    topic: str
    created_at: float = field(default_factory=time.time)
    confirmed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackCapture:
    """用户反馈捕获 + 入库管理器"""

    def __init__(self, llm_client=None, verbose: bool = False):
        """
        Args:
            llm_client: LLM 客户端 (Qwen 本地或云端), 必须有 generate() / generate_with_system()
            verbose: 打印过程
        """
        self.llm_client = llm_client
        self.verbose = verbose

        # 预览缓存 (进程内 + 持久化)
        self._preview_cache: Dict[str, FeedbackPreview] = {}
        self._load_cache()

    def _load_cache(self):
        if FEEDBACK_PREVIEW_CACHE_PATH.exists():
            try:
                data = json.loads(FEEDBACK_PREVIEW_CACHE_PATH.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._preview_cache[k] = FeedbackPreview(**v)
            except Exception as e:
                if self.verbose:
                    print(f"[FeedbackCapture] cache load failed: {e}")

    def _save_cache(self):
        data = {k: v.to_dict() for k, v in self._preview_cache.items()}
        FEEDBACK_PREVIEW_CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ============= 阶段 1: 捕获预览 =============

    def capture_preview(
        self,
        user_message: str,
        context_history: Optional[List[Dict[str, str]]] = None,
        product: str = "wangzhe",
        topic: str = "",
    ) -> Dict[str, Any]:
        """
        调 LLM 识别用户消息, 返回 FeedbackPreview 字典
        若 LLM 不可用 / 识别失败, 返回 feedback_type="none"
        """
        if not self.llm_client:
            return self._empty_preview(user_message, product, topic, "llm 未配置")

        if not user_message or len(user_message.strip()) < 4:
            return self._empty_preview(user_message, product, topic, "消息太短")

        # 截取最近 4 轮上下文
        ctx = context_history or []
        ctx_str = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')[:200]}"
            for m in ctx[-4:]
        ) or "(无)"

        # 用 str.replace 而非 .format(), 避免 prompt 内 {} 与 LLM 输出冲突
        prompt = (
            CAPTURE_PROMPT
            .replace("{user_message}", user_message[:1000])
            .replace("{n_ctx}", str(len(ctx[-4:])))
            .replace("{context_history}", ctx_str)
            .replace("{product}", product)
            .replace("{topic}", topic[:200] or "(无)")
        )

        try:
            t0 = time.time()
            if hasattr(self.llm_client, "generate_with_system"):
                resp = self.llm_client.generate_with_system(
                    system_prompt="你是反馈分类器, 只输出 JSON。",
                    user_prompt=prompt,
                    temperature=0.1,
                    max_tokens=500,
                )
                content = getattr(resp, "content", None) or (resp.get("content") if isinstance(resp, dict) else str(resp))
            else:
                resp = self.llm_client.generate(prompt, temperature=0.1, max_tokens=500)
                content = str(resp)
            elapsed = time.time() - t0

            if self.verbose:
                print(f"[FeedbackCapture] LLM 识别: {elapsed:.2f}s, raw={content[:150]}")

            parsed = self._parse_llm_json(content)
            if not parsed:
                return self._empty_preview(user_message, product, topic, "LLM 输出非 JSON")

            preview = FeedbackPreview(
                preview_id=self._make_preview_id(user_message, product),
                user_message=user_message[:500],
                feedback_type=parsed.get("feedback_type", "none"),
                target=parsed.get("target", "none"),
                candidate_facts=parsed.get("candidate_facts") or {},
                confidence=float(parsed.get("confidence", 0)),
                reason=parsed.get("reason", ""),
                product=product,
                topic=topic[:200],
            )
            self._preview_cache[preview.preview_id] = preview
            self._save_cache()
            return preview.to_dict()
        except Exception as e:
            if self.verbose:
                print(f"[FeedbackCapture] LLM 失败: {e}")
            return self._empty_preview(user_message, product, topic, f"LLM 异常: {e}")

    def _empty_preview(self, msg, product, topic, reason):
        return FeedbackPreview(
            preview_id=self._make_preview_id(msg, product),
            user_message=msg[:500] if msg else "",
            feedback_type="none",
            target="none",
            candidate_facts={},
            confidence=0,
            reason=f"未识别: {reason}",
            product=product,
            topic=topic[:200] if topic else "",
        ).to_dict()

    @staticmethod
    def _make_preview_id(msg, product):
        h = hashlib.md5(f"{product}|{msg[:200]}|{time.time()//60}".encode()).hexdigest()[:12]
        return f"fb_{h}"

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None
        # 尝试直接 JSON 解析
        try:
            return json.loads(content)
        except Exception:
            pass
        # 抓 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # 抓第一个 {...} 块
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    # ============= 阶段 2: 确认并入库 =============

    def confirm_and_write(
        self,
        preview_id: str,
        edited_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        用户确认入库:
            - preview_id 找到 → 走对应入库管道
            - edited_payload: 用户编辑过的 candidate_facts (覆盖原值)
        返回: {
            ok: bool,
            action: "ingested" | "logged" | "skipped",
            detail: str,
            path: Optional[str],  # 入库的 wiki 路径 或 log 行号
        }
        """
        preview = self._preview_cache.get(preview_id)
        if not preview:
            return {
                "ok": False,
                "action": "skipped",
                "detail": f"preview_id {preview_id} 不存在 (可能已过期)",
            }

        if preview.confirmed:
            return {
                "ok": False,
                "action": "skipped",
                "detail": "该 preview 已被确认过, 不可重复入库",
            }

        # 合并编辑
        if edited_payload:
            if "candidate_facts" in edited_payload:
                preview.candidate_facts = edited_payload["candidate_facts"]
            if "feedback_type" in edited_payload:
                preview.feedback_type = edited_payload["feedback_type"]
            if "target" in edited_payload:
                preview.target = edited_payload["target"]

        # 根据 feedback_type 决定入库路径
        if preview.feedback_type in FACT_TYPES and preview.target == "wiki":
            result = self._write_to_wiki(preview)
        elif preview.feedback_type in PREFERENCE_TYPES and preview.target == "log":
            result = self._write_to_log(preview)
        else:
            result = {
                "ok": False,
                "action": "skipped",
                "detail": f"feedback_type={preview.feedback_type} 无对应入库路径",
            }

        if result.get("ok"):
            preview.confirmed = True
            self._save_cache()

        return result

    def _write_to_wiki(self, preview: FeedbackPreview) -> Dict[str, Any]:
        """
        事实类反馈 → 走 ingest 管道
        合成 raw/<product>/feedback/<date>/<preview_id>.txt
        调 scripts.ingest.ingest_one()
        """
        if not DEEPSEARCH_ROOT:
            return {
                "ok": False,
                "action": "skipped",
                "detail": "deepsearch 根目录未找到, 无法走 ingest 管道",
            }

        try:
            # 动态导入 (避免循环依赖)
            import sys
            if str(DEEPSEARCH_ROOT) not in sys.path:
                sys.path.insert(0, str(DEEPSEARCH_ROOT))
            from scripts.ingest import ingest_one  # type: ignore
        except Exception as e:
            return {
                "ok": False,
                "action": "skipped",
                "detail": f"ingest 模块导入失败: {e}",
            }

        # 合成 raw 文本
        facts_md = "\n".join(f"- **{k}**: {v}" for k, v in preview.candidate_facts.items())
        raw_text = f"""# {preview.feedback_type} — 用户反馈

**来源**: 行业稿件写作系统 / 用户反馈采集
**产品**: {preview.product}
**话题**: {preview.topic or '(无)'}
**反馈时间**: {time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}
**置信度**: {preview.confidence}
**原因**: {preview.reason}

## 用户原始消息
{preview.user_message}

## 提取的事实
{facts_md}

---
[来源: 行业稿件写作系统反馈采集 - {time.strftime("%Y-%m-%d")}]
"""
        # 写 raw 文件
        date_str = time.strftime("%Y-%m-%d")
        raw_dir = DEEPSEARCH_ROOT / "raw" / preview.product / "feedback" / date_str
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"{preview.preview_id}.md"
        raw_file.write_text(raw_text, encoding="utf-8")

        # 调 ingest
        try:
            ingest_result = ingest_one(
                raw_path=raw_file,
                client=self.llm_client,
                product=preview.product,
            )
            return {
                "ok": True,
                "action": "ingested",
                "detail": f"已走 ingest 管道, status={ingest_result.get('status', '?')}",
                "path": ingest_result.get("path"),
                "confidence": ingest_result.get("confidence"),
                "raw_file": str(raw_file.relative_to(DEEPSEARCH_ROOT)),
            }
        except Exception as e:
            return {
                "ok": False,
                "action": "skipped",
                "detail": f"ingest 失败: {e}",
                "raw_file": str(raw_file.relative_to(DEEPSEARCH_ROOT)),
            }

    def _write_to_log(self, preview: FeedbackPreview) -> Dict[str, Any]:
        """
        偏好类反馈 → 追加到 state/feedback_log.jsonl
        """
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "preview_id": preview.preview_id,
            "feedback_type": preview.feedback_type,
            "product": preview.product,
            "topic": preview.topic,
            "user_message": preview.user_message,
            "candidate_facts": preview.candidate_facts,
            "confidence": preview.confidence,
            "reason": preview.reason,
        }
        try:
            with FEEDBACK_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            line_num = sum(1 for _ in FEEDBACK_LOG_PATH.open(encoding="utf-8"))
            return {
                "ok": True,
                "action": "logged",
                "detail": f"已写入 {FEEDBACK_LOG_PATH.name} 第 {line_num} 行",
                "path": str(FEEDBACK_LOG_PATH),
                "line": line_num,
            }
        except Exception as e:
            return {
                "ok": False,
                "action": "skipped",
                "detail": f"写 log 失败: {e}",
            }

    # ============= 查询接口 =============

    def list_previews(self, limit: int = 20) -> List[Dict[str, Any]]:
        return sorted(
            [p.to_dict() for p in self._preview_cache.values()],
            key=lambda x: x.get("created_at", 0),
            reverse=True,
        )[:limit]

    def get_preview(self, preview_id: str) -> Optional[Dict[str, Any]]:
        p = self._preview_cache.get(preview_id)
        return p.to_dict() if p else None

    def list_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not FEEDBACK_LOG_PATH.exists():
            return []
        lines = FEEDBACK_LOG_PATH.read_text(encoding="utf-8").splitlines()
        records = []
        for ln in lines[-limit:]:
            try:
                records.append(json.loads(ln))
            except Exception:
                continue
        return records


# === 全局单例 ===
_capture_instance: Optional[FeedbackCapture] = None


def get_capture(llm_client=None) -> FeedbackCapture:
    global _capture_instance
    if _capture_instance is None:
        _capture_instance = FeedbackCapture(llm_client=llm_client, verbose=True)
    return _capture_instance


# === 自测 ===
if __name__ == "__main__":
    print("=== FeedbackCapture 自测 (无 LLM 客户端, 应全部返回 none) ===")
    fc = FeedbackCapture(verbose=True)
    tests = [
        ("李白 1 技能是 8 秒, 不是 12 秒", [{"role": "user", "content": "聊聊李白技能"}]),
        ("下次写作更口语化一点, 短句多", []),
        ("好的, 继续", []),
        ("洛克王国 星光对决 莫扎特", []),
    ]
    for msg, ctx in tests:
        preview = fc.capture_preview(msg, context_history=ctx, product="honor_of_kings", topic="测试")
        print(f"  [{preview['feedback_type']}] conf={preview['confidence']:.2f} | {msg[:40]}")
