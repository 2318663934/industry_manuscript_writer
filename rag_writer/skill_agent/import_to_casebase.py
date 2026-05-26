#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入标注数据到Milvus策略案例库

使用独立的collection，与RAG系统的wechat_articles隔离
"""

import json
from pathlib import Path

# 添加父目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_writer.skill_agent import CaseBaseManager


def main():
    import argparse
    parser = argparse.ArgumentParser(description='导入标注数据到Milvus策略案例库')
    parser.add_argument('--input', '-i', default='./rag_writer/skill_agent/annotations.json',
                       help='标注JSON文件路径')
    parser.add_argument('--base-path', '-b', default='./strategy_cases',
                       help='策略案例库根目录')

    args = parser.parse_args()

    # 创建案例库管理器
    print("创建案例库管理器...")
    case_base = CaseBaseManager(base_path=args.base_path)

    # 创建Milvus集合（独立collection，与RAG系统隔离）
    print("创建独立Milvus集合 'strategy_cases'...")
    case_base.create_collection(drop_existing=True)

    # 导入标注数据
    print(f"\n从 {args.input} 导入标注数据...")
    count = case_base.import_from_json(args.input)

    print(f"\n导入完成！共导入 {count} 条策略案例")
    print(f"案例库路径: {case_base.base_path}")

    # 显示统计信息
    stats = case_base.get_collection_stats()
    print(f"\n统计信息:")
    print(f"  总案例数: {stats['total_cases']}")
    print(f"  平均质量分: {stats['avg_quality_score']:.2f}")
    print(f"  内容类型: {', '.join(stats['content_types'][:5])}")


if __name__ == '__main__':
    main()
