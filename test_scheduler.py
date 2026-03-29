#!/usr/bin/env python3
# test_scheduler.py — 调度器集成测试脚本
#
# 用法：
#   python test_scheduler.py --full        # 运行完整流程
#   python test_scheduler.py --scanner     # 仅测试扫描器
#   python test_scheduler.py --extractor   # 仅测试提取器
#   python test_scheduler.py --matcher     # 仅测试匹配器
#   python test_scheduler.py --scorer      # 仅测试评分器
#   python test_scheduler.py --notifier    # 仅测试推送器

import sys
import json
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime, timezone
from gateway.utils.logger import get_logger
from gateway.scheduler.orchestrator import get_orchestrator
from gateway.scheduler.scanner import get_scanner
from gateway.scheduler.event_extractor import get_extractor
from gateway.scheduler.matcher import get_matcher
from gateway.scheduler.risk_scorer import get_risk_scorer
from gateway.scheduler.notifier import get_notifier

logger = get_logger(__name__)


def test_scanner():
    """测试扫描器模块"""
    print("\n" + "=" * 80)
    print("Testing Scanner Module")
    print("=" * 80)

    scanner = get_scanner()

    try:
        result = scanner.run_scan()
        print(f"\n✓ Scanner test passed!")
        print(f"  Events found: {result.get('total_events')}")
        print(f"  Events saved: {result.get('saved_events')}")
        print(f"  Event IDs: {result.get('event_ids')}")
        return result
    except Exception as e:
        print(f"\n✗ Scanner test failed: {e}")
        return None


def test_extractor(event_ids):
    """测试提取器模块"""
    print("\n" + "=" * 80)
    print("Testing Extractor Module")
    print("=" * 80)

    if not event_ids:
        print("No events to extract (Scanner returned empty list)")
        return None

    extractor = get_extractor()

    try:
        result = extractor.process_new_events(event_ids)
        print(f"\n✓ Extractor test passed!")
        print(f"  Total raw events: {result.get('total')}")
        print(f"  Extracted events: {result.get('extracted')}")
        print(f"  Saved to database: {result.get('saved')}")
        print(f"  Saved IDs: {result.get('saved_ids')}")
        return result
    except Exception as e:
        print(f"\n✗ Extractor test failed: {e}")
        return None


def test_matcher(extracted_ids):
    """测试匹配器模块"""
    print("\n" + "=" * 80)
    print("Testing Matcher Module")
    print("=" * 80)

    if not extracted_ids:
        print("No events to match (Extractor returned empty list)")
        return None

    matcher = get_matcher()

    try:
        result = matcher.match_batch_events(extracted_ids)
        print(f"\n✓ Matcher test passed!")
        print(f"  Total events: {result.get('total_events')}")
        print(f"  Total matches: {result.get('total_matches')}")
        print(f"  Avg matches per event: {result.get('avg_matches_per_event'):.2f}")
        return result
    except Exception as e:
        print(f"\n✗ Matcher test failed: {e}")
        return None


def test_risk_scorer(extracted_ids):
    """测试风险评分器模块"""
    print("\n" + "=" * 80)
    print("Testing Risk Scorer Module")
    print("=" * 80)

    if not extracted_ids:
        print("No events to score (Extractor returned empty list)")
        return None

    scorer = get_risk_scorer()

    try:
        result = scorer.score_batch_events(extracted_ids)
        print(f"\n✓ Risk Scorer test passed!")
        print(f"  Total events: {result.get('total_events')}")
        print(f"  Scored events: {result.get('scored')}")
        print(f"  Saved scores: {result.get('saved')}")
        return result
    except Exception as e:
        print(f"\n✗ Risk Scorer test failed: {e}")
        return None


def test_notifier(extracted_ids):
    """测试推送器模块"""
    print("\n" + "=" * 80)
    print("Testing Notifier Module")
    print("=" * 80)

    if not extracted_ids:
        print("No events to notify (Extractor returned empty list)")
        return None

    notifier = get_notifier()

    try:
        # 仅测试一个事件的推送（避免过度消耗）
        event_id = extracted_ids[0]

        # 示例用户 ID 列表（实际应从数据库查询）
        test_users = ["test_user_1", "test_user_2"]

        result = notifier.send_notifications(event_id, test_users)
        print(f"\n✓ Notifier test passed!")
        print(f"  Event ID: {event_id}")
        print(f"  Target users: {result.get('total')}")
        print(f"  Notifications sent: {result.get('sent')}")
        print(f"  Notifications failed: {result.get('failed')}")
        print(f"  By channel: {result.get('by_channel')}")
        return result
    except Exception as e:
        print(f"\n✗ Notifier test failed: {e}")
        return None


def test_full_pipeline():
    """测试完整流程"""
    print("\n" + "=" * 80)
    print("Testing Full Pipeline (Orchestrator)")
    print("=" * 80)

    orchestrator = get_orchestrator()

    try:
        result = orchestrator.run_full_pipeline()

        print(f"\n✓ Full pipeline test passed!")
        print(f"\nPipeline Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        return result
    except Exception as e:
        print(f"\n✗ Full pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_summary(results):
    """打印测试总结"""
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    for module, result in results.items():
        status = "✓" if result is not None else "✗"
        print(f"{status} {module}")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Test ESG Scheduler Components")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline",
    )
    parser.add_argument(
        "--scanner",
        action="store_true",
        help="Test scanner module only",
    )
    parser.add_argument(
        "--extractor",
        action="store_true",
        help="Test extractor module only",
    )
    parser.add_argument(
        "--matcher",
        action="store_true",
        help="Test matcher module only",
    )
    parser.add_argument(
        "--scorer",
        action="store_true",
        help="Test risk scorer module only",
    )
    parser.add_argument(
        "--notifier",
        action="store_true",
        help="Test notifier module only",
    )

    args = parser.parse_args()

    # 如果没有指定参数，默认运行完整流程
    if not any([args.full, args.scanner, args.extractor, args.matcher, args.scorer, args.notifier]):
        args.full = True

    results = {}

    print("\n" + "=" * 80)
    print("ESG Scheduler Integration Test Suite")
    print("=" * 80)

    if args.full:
        result = test_full_pipeline()
        results["Full Pipeline"] = result
    else:
        # 按顺序执行各模块测试
        if args.scanner:
            result = test_scanner()
            results["Scanner"] = result
            scan_event_ids = result.get("event_ids", []) if result else []
        else:
            scan_event_ids = []

        if args.extractor:
            result = test_extractor(scan_event_ids)
            results["Extractor"] = result
            extract_event_ids = result.get("saved_ids", []) if result else []
        else:
            extract_event_ids = []

        if args.matcher:
            result = test_matcher(extract_event_ids)
            results["Matcher"] = result

        if args.scorer:
            result = test_risk_scorer(extract_event_ids)
            results["Risk Scorer"] = result

        if args.notifier:
            result = test_notifier(extract_event_ids)
            results["Notifier"] = result

    print_summary(results)

    # 全部通过则返回 0，有失败则返回 1
    all_passed = all(v is not None for v in results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
