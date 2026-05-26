#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAGWriter + SkillAgent 完整工作流演示

演示端到端的智能写作流程：
1. 初始化RAGWriter + SkillAgent
2. 检索RAG事实素材
3. 生成策略蓝图（可预览/审核）
4. 基于蓝图生成最终文章
5. 输出完整结果

建议运行方式:
    python demo_workflow.py --topic "AI Agent的落地困境与未来趋势"
    python demo_workflow.py --interactive  # 交互式模式
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_writer import create_writer, RAGWriter
from rag_writer.prompt_engineering import KnowledgeContext
from rag_writer.skill_agent import SkillAgent, CaseBaseManager, StrategyBlueprint
from rag_writer.llm_client import create_llm_client


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    description: str
    status: str  # pending/running/completed/failed
    duration: float = 0.0
    result: Any = None
    error: Optional[str] = None


@dataclass
class WorkflowResult:
    """完整工作流结果"""
    topic: str
    content_type: str
    target_audience: str

    # 各阶段结果
    rag_knowledge: List[KnowledgeContext]
    similar_cases: List[Any]
    blueprint: Optional[StrategyBlueprint]
    article: Optional[str]

    # 统计信息
    total_time: float
    step_times: Dict[str, float]
    token_usage: Dict[str, int]

    # 来源信息
    knowledge_sources: List[Dict[str, str]]
    case_references: List[str]


class RAGSkillWorkflowDemo:
    """
    RAG + SkillAgent 完整工作流演示

    展示如何将RAG事实检索与SkillAgent策略规划结合，
    实现"策略驱动的事实写作"。
    """

    def __init__(
        self,
        case_base_path: str = "./strategy_cases",
        articles_json: Optional[str] = None,
        llm_provider: Optional[str] = None,
    ):
        """
        初始化工作流演示

        Args:
            case_base_path: 策略案例库路径
            articles_json: 文章JSON文件（用于RAG检索）
            llm_provider: LLM提供商
        """
        self.case_base_path = case_base_path
        self.articles_json = articles_json
        self.llm_provider = llm_provider

        # 组件实例
        self.writer: Optional[RAGWriter] = None
        self.skill_agent: Optional[SkillAgent] = None

        # 工作流状态
        self.steps: List[WorkflowStep] = []
        self.result: Optional[WorkflowResult] = None

    # ============ 阶段1: 初始化 ============

    def _step_initialize(self) -> bool:
        """初始化RAGWriter和SkillAgent"""
        step = WorkflowStep(
            name="initialize",
            description="初始化RAGWriter和SkillAgent",
            status="running",
        )
        self.steps.append(step)

        try:
            start_time = time.time()

            # 1. 创建RAGWriter
            print("\n" + "=" * 60)
            print("阶段1: 系统初始化")
            print("=" * 60)

            print("\n[1.1] 创建RAGWriter...")
            self.writer = create_writer(
                articles_json=self.articles_json,
                llm_provider=self.llm_provider,
            )
            print(f"      LLM: {self.writer.llm_client.model}")
            print(f"      Embedding: {self.writer._embedding_model_name}")

            # 2. 检查系统状态
            print("\n[1.2] 检查系统状态...")
            status = self.writer.check_status()
            print(f"      Milvus: {'已连接' if 'error' not in status.get('milvus', {}) else '未连接'}")
            print(f"      文本检索: {'已配置' if status.get('text_retriever', {}).get('status') != 'not_configured' else '未配置'}")

            # 3. 创建SkillAgent
            print("\n[1.3] 创建SkillAgent...")
            self.skill_agent = self.writer.create_skill_agent(
                case_base_path=self.case_base_path
            )
            stats = self.skill_agent.get_case_base_stats()
            print(f"      案例库路径: {self.skill_agent.case_base.base_path}")
            print(f"      案例总数: {stats['total_cases']}")
            print(f"      平均质量分: {stats.get('avg_quality_score', 0):.2f}")

            step.duration = time.time() - start_time
            step.status = "completed"
            step.result = {
                "llm_model": self.writer.llm_client.model,
                "embedding_model": self.writer._embedding_model_name,
                "case_count": stats['total_cases'],
            }

            print(f"\n初始化完成，耗时: {step.duration:.2f}秒")
            return True

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            print(f"\n初始化失败: {e}")
            return False

    # ============ 阶段2: RAG事实素材检索 ============

    def _step_retrieve_knowledge(self, topic: str, top_k: int = 5) -> bool:
        """检索RAG事实素材"""
        step = WorkflowStep(
            name="retrieve_knowledge",
            description="检索RAG事实素材",
            status="running",
        )
        self.steps.append(step)

        try:
            start_time = time.time()

            print("\n" + "=" * 60)
            print("阶段2: RAG事实素材检索")
            print("=" * 60)

            print(f"\n[2.1] 检索查询: {topic}")
            print(f"      top_k: {top_k}")

            # 执行检索
            knowledge = self.writer.retrieve_knowledge(topic, top_k=top_k)

            print(f"\n[2.2] 检索结果:")
            print(f"      共检索到 {len(knowledge)} 条相关知识")

            for i, item in enumerate(knowledge, 1):
                print(f"\n      --- 知识 {i} ---")
                print(f"      标题: {item.title}")
                print(f"      来源: {item.author} | {item.date}")
                content_preview = item.content[:150] if item.content else ""
                print(f"      内容预览: {content_preview}...")

            step.duration = time.time() - start_time
            step.status = "completed"
            step.result = knowledge

            print(f"\n检索完成，耗时: {step.duration:.2f}秒")
            return True

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            print(f"\n检索失败: {e}")
            return False

    # ============ 阶段3: 策略蓝图生成 ============

    def _step_generate_blueprint(
        self,
        topic: str,
        content_type: str,
        target_audience: str,
        use_reflection: bool = True,
    ) -> bool:
        """生成策略蓝图"""
        step = WorkflowStep(
            name="generate_blueprint",
            description="生成策略蓝图",
            status="running",
        )
        self.steps.append(step)

        try:
            start_time = time.time()

            print("\n" + "=" * 60)
            print("阶段3: 策略蓝图生成")
            print("=" * 60)

            # 构建RAG上下文
            rag_context = {
                "knowledge": self.steps[1].result,  # 阶段2的检索结果
                "topic": topic,
                "content_type": content_type,
            }

            # 3.1 检索相似策略案例
            print("\n[3.1] 检索相似策略案例（动态Few-shot）...")
            similar_cases = self.skill_agent.retriever.retrieve(topic, top_k=3)
            print(f"      找到 {len(similar_cases)} 个相似案例:")
            for i, case in enumerate(similar_cases, 1):
                print(f"      {i}. [{case.case_id}] {case.title}")
                print(f"         开篇: {case.annotation.opening_approach} | "
                      f"结构: {case.annotation.structural_pattern} | "
                      f"收尾: {case.annotation.closing_approach}")

            # 3.2 生成策略蓝图
            print("\n[3.2] 生成策略蓝图...")
            if use_reflection:
                print("      (启用Self-Reflection校验)")
            else:
                print("      (禁用Self-Reflection校验)")

            blueprint = self.skill_agent.generate_blueprint(
                topic=topic,
                rag_context=rag_context,
                content_type=content_type,
                target_audience=target_audience,
                use_reflection=use_reflection,
            )

            # 3.3 展示蓝图统计
            print(f"\n[3.3] 策略蓝图生成完成!")
            print(f"      置信度: {blueprint.confidence:.2f}")
            print(f"      章节数: {len(blueprint.sections)}")
            case_refs = blueprint.meta.get('case_references', []) if blueprint.meta else []
            print(f"      引用案例: {len(case_refs)} 个")
            gen_time = blueprint.meta.get('generation_time', 0) if blueprint.meta else 0
            print(f"      生成耗时: {gen_time:.2f}秒")

            # 3.4 Markdown预览
            print("\n" + "-" * 40)
            print("策略蓝图预览（可人工审核）:")
            print("-" * 40)
            print(blueprint.to_markdown())

            step.duration = time.time() - start_time
            step.status = "completed"
            step.result = {
                "blueprint": blueprint,
                "similar_cases": similar_cases,
            }

            print(f"\n蓝图生成完成，耗时: {step.duration:.2f}秒")
            return True

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            print(f"\n蓝图生成失败: {e}")
            return False

    # ============ 阶段4: 基于蓝图写作 ============

    def _step_write_from_blueprint(self, temperature: float = 0.5) -> bool:
        """基于策略蓝图生成文章"""
        step = WorkflowStep(
            name="write_from_blueprint",
            description="基于策略蓝图生成文章",
            status="running",
        )
        self.steps.append(step)

        try:
            start_time = time.time()

            print("\n" + "=" * 60)
            print("阶段4: 基于策略蓝图生成文章")
            print("=" * 60)

            blueprint = self.steps[2].result["blueprint"]
            knowledge = self.steps[1].result

            print(f"\n[4.1] 使用策略蓝图写作...")
            print(f"      话题: {blueprint.topic}")
            print(f"      写作基调: {blueprint.writing_tone.value if hasattr(blueprint.writing_tone, 'value') else blueprint.writing_tone}")
            print(f"      温度参数: {temperature}")

            # 调用write_from_blueprint
            result = self.writer.write_from_blueprint(
                blueprint=blueprint,
                knowledge=knowledge,
                temperature=temperature,
            )

            # 展示结果统计
            print(f"\n[4.2] 文章生成完成!")
            print(f"      字数: 约 {len(result.article)} 字符")
            print(f"      模型: {result.model}")
            print(f"      知识来源: {result.knowledge_count} 条")
            print(f"      生成耗时: {result.generation_time:.2f}秒")
            print(f"      Token用量: {result.usage}")

            # 文章预览
            print("\n" + "-" * 40)
            print("生成文章预览（前2000字）:")
            print("-" * 40)
            preview = result.article[:2000]
            if len(result.article) > 2000:
                preview += "\n\n... (文章继续) ..."
            print(preview)

            step.duration = time.time() - start_time
            step.status = "completed"
            step.result = result

            print(f"\n文章生成完成，耗时: {step.duration:.2f}秒")
            return True

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            print(f"\n文章生成失败: {e}")
            return False

    # ============ 阶段5: 结果汇总 ============

    def _step_summarize(self) -> WorkflowResult:
        """汇总工作流结果"""
        step = WorkflowStep(
            name="summarize",
            description="汇总工作流结果",
            status="running",
        )
        self.steps.append(step)

        try:
            start_time = time.time()

            print("\n" + "=" * 60)
            print("阶段5: 工作流结果汇总")
            print("=" * 60)

            # 收集各阶段结果
            knowledge = self.steps[1].result
            similar_cases = self.steps[2].result.get("similar_cases", [])
            blueprint = self.steps[2].result.get("blueprint")
            write_result = self.steps[3].result

            # 计算总时间
            total_time = sum(s.duration for s in self.steps)

            # 汇总Token用量
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            if hasattr(write_result, 'usage') and write_result.usage:
                for key in total_usage:
                    total_usage[key] = write_result.usage.get(key, 0)

            # 构建知识来源列表
            knowledge_sources = []
            for k in knowledge:
                knowledge_sources.append({
                    "title": k.title,
                    "author": k.author,
                    "date": k.date,
                    "url": k.url,
                })

            # 构建案例引用列表
            case_references = [c.case_id for c in similar_cases]

            # 构建最终结果
            self.result = WorkflowResult(
                topic=blueprint.topic if blueprint else "",
                content_type=blueprint.content_type if blueprint else "",
                target_audience=blueprint.target_audience if blueprint else "",
                rag_knowledge=knowledge,
                similar_cases=similar_cases,
                blueprint=blueprint,
                article=write_result.article if write_result else None,
                total_time=total_time,
                step_times={s.name: s.duration for s in self.steps},
                token_usage=total_usage,
                knowledge_sources=knowledge_sources,
                case_references=case_references,
            )

            # 打印汇总报告
            blueprint_confidence = self.result.blueprint.confidence if self.result.blueprint else 'N/A'
            blueprint_sections = len(self.result.blueprint.sections) if self.result.blueprint else 0
            case_refs_str = ', '.join(self.result.case_references) if self.result.case_references else '无'

            print(f"""
============================================================
                    工作流执行汇总报告
============================================================

【基本信息】
  话题: {self.result.topic}
  内容类型: {self.result.content_type}
  目标受众: {self.result.target_audience}

【素材统计】
  RAG知识: {len(self.result.rag_knowledge)} 条
  策略案例: {len(self.result.similar_cases)} 个
  案例引用: {case_refs_str}

【性能统计】
  总耗时: {self.result.total_time:.2f} 秒
  各阶段耗时:
""")
            for name, duration in self.result.step_times.items():
                print(f"    - {name}: {duration:.2f}秒")

            print(f"""
  Token用量:
    - Prompt: {self.result.token_usage.get('prompt_tokens', 0)}
    - Completion: {self.result.token_usage.get('completion_tokens', 0)}
    - Total: {self.result.token_usage.get('total_tokens', 0)}

【策略蓝图】
  置信度: {blueprint_confidence}
  章节数: {blueprint_sections}

【文章输出】
  字数: {len(self.result.article) if self.result.article else 0} 字符
  知识来源: {len(self.result.knowledge_sources)} 条

============================================================
""")

            step.duration = time.time() - start_time
            step.status = "completed"

            return self.result

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            print(f"\n汇总失败: {e}")
            return None

    # ============ 主工作流执行 ============

    def run(
        self,
        topic: str,
        content_type: str = "行业分析",
        target_audience: str = "企业决策者、技术从业者",
        top_k: int = 5,
        use_reflection: bool = True,
        temperature: float = 0.5,
        interactive: bool = False,
    ) -> Optional[WorkflowResult]:
        """
        执行完整工作流

        Args:
            topic: 写作话题
            content_type: 内容类型
            target_audience: 目标受众
            top_k: RAG检索数量
            use_reflection: 是否启用Self-Reflection校验
            temperature: 写作温度参数
            interactive: 是否启用交互式审核

        Returns:
            WorkflowResult: 工作流执行结果
        """
        print("\n" + "#" * 60)
        print("# RAGWriter + SkillAgent 完整工作流演示")
        print("#" * 60)
        print(f"\n话题: {topic}")
        print(f"内容类型: {content_type}")
        print(f"目标受众: {target_audience}")
        print(f"交互模式: {'是' if interactive else '否'}")

        # 阶段1: 初始化
        if not self._step_initialize():
            return None

        # 阶段2: RAG检索
        if not self._step_retrieve_knowledge(topic, top_k):
            return None

        # 阶段3: 生成策略蓝图
        if not self._step_generate_blueprint(
            topic=topic,
            content_type=content_type,
            target_audience=target_audience,
            use_reflection=use_reflection,
        ):
            return None

        # 交互式审核（可选）
        if interactive:
            print("\n" + "-" * 40)
            print("【人工审核环节】请审核上述策略蓝图")
            print("-" * 40)
            user_input = input("是否继续生成文章？(y/n/q): ").strip().lower()
            if user_input == 'q':
                print("用户退出")
                return None
            elif user_input == 'n':
                print("用户取消，当前工作流结束")
                return None
            else:
                print("继续执行...")

        # 阶段4: 基于蓝图写作
        if not self._step_write_from_blueprint(temperature):
            return None

        # 阶段5: 汇总结果
        return self._step_summarize()

    def export_result(self, output_path: str) -> bool:
        """
        导出工作流结果到文件

        Args:
            output_path: 输出文件路径

        Returns:
            是否成功
        """
        if self.result is None:
            print("没有可导出的结果")
            return False

        try:
            export_data = {
                "topic": self.result.topic,
                "content_type": self.result.content_type,
                "target_audience": self.result.target_audience,
                "article": self.result.article,
                "blueprint": self.result.blueprint.model_dump() if self.result.blueprint else None,
                "knowledge_sources": self.result.knowledge_sources,
                "case_references": self.result.case_references,
                "total_time": self.result.total_time,
                "step_times": self.result.step_times,
                "token_usage": self.result.token_usage,
                "export_time": datetime.now().isoformat(),
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            print(f"结果已导出到: {output_path}")
            return True

        except Exception as e:
            print(f"导出失败: {e}")
            return False


# ============ 命令行入口 ============

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="RAGWriter + SkillAgent 完整工作流演示"
    )
    parser.add_argument(
        "--topic", "-t",
        default="AI Agent的落地困境与未来趋势",
        help="写作话题"
    )
    parser.add_argument(
        "--content-type", "-c",
        default="行业分析",
        help="内容类型"
    )
    parser.add_argument(
        "--audience", "-a",
        default="企业决策者、技术从业者",
        help="目标受众"
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=5,
        help="RAG检索数量"
    )
    parser.add_argument(
        "--no-reflection",
        action="store_true",
        help="禁用Self-Reflection校验"
    )
    parser.add_argument(
        "--temperature", "-T",
        type=float,
        default=0.5,
        help="写作温度参数"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="启用交互式审核"
    )
    parser.add_argument(
        "--output", "-o",
        help="导出结果到文件"
    )
    parser.add_argument(
        "--case-base",
        default="./strategy_cases",
        help="策略案例库路径"
    )
    parser.add_argument(
        "--articles-json",
        help="文章JSON文件路径（RAG检索用）"
    )
    parser.add_argument(
        "--llm-provider",
        help="LLM提供商"
    )

    args = parser.parse_args()

    # 创建并执行工作流
    demo = RAGSkillWorkflowDemo(
        case_base_path=args.case_base,
        articles_json=args.articles_json,
        llm_provider=args.llm_provider,
    )

    result = demo.run(
        topic=args.topic,
        content_type=args.content_type,
        target_audience=args.audience,
        top_k=args.top_k,
        use_reflection=not args.no_reflection,
        temperature=args.temperature,
        interactive=args.interactive,
    )

    # 导出结果
    if result and args.output:
        demo.export_result(args.output)


if __name__ == "__main__":
    main()
