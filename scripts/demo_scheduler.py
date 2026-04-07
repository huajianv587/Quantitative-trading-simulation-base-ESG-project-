#!/usr/bin/env python3
# demo_scheduler.py — ESG 调度器演示脚本
#
# 这个脚本展示如何使用调度器系统来扫描、分析和推送 ESG 事件

import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.scheduler.orchestrator import get_orchestrator
from gateway.scheduler.matcher import get_matcher
from gateway.scheduler.scanner import get_scanner
from gateway.models.schemas import ESGEventType, RiskLevel


def demo_basic_scan():
    """演示：基本扫描功能"""
    print("\n" + "="*80)
    print("DEMO 1: Basic Scanning")
    print("="*80)

    scanner = get_scanner()
    print("\n[Scanning news feeds...]")
    news_events, _ = scanner.scan_news_feeds()
    print(f"  Found {len(news_events)} news events")
    if news_events:
        print(f"  Example: {news_events[0].title}")

    print("\n[Scanning ESG reports...]")
    report_events, _ = scanner.scan_esg_reports()
    print(f"  Found {len(report_events)} report events")

    print("\n[Scanning compliance updates...]")
    compliance_events, _ = scanner.scan_compliance_updates()
    print(f"  Found {len(compliance_events)} compliance events")

    total = len(news_events) + len(report_events) + len(compliance_events)
    print(f"\n[Total: {total} events detected]")


def demo_user_preferences():
    """演示：用户偏好管理"""
    print("\n" + "="*80)
    print("DEMO 2: User Preference Management")
    print("="*80)

    matcher = get_matcher()

    # 创建多个用户偏好
    users = [
        {
            "user_id": "user_tech_esg",
            "prefs": {
                "interested_companies": ["Tesla", "Apple", "Microsoft"],
                "interested_categories": ["E", "G"],  # 关注环境和治理
                "risk_threshold": "medium",
                "keywords": ["carbon", "renewable", "board", "transparency"],
                "notification_channels": ["email", "in_app"],
            }
        },
        {
            "user_id": "user_social_focus",
            "prefs": {
                "interested_companies": ["Starbucks", "Nike", "Unilever"],
                "interested_categories": ["S"],  # 仅关注社会
                "risk_threshold": "high",
                "keywords": ["diversity", "supply_chain", "labor"],
                "notification_channels": ["in_app"],
            }
        },
        {
            "user_id": "user_all_sectors",
            "prefs": {
                "interested_companies": [],  # 关注所有公司
                "interested_categories": ["E", "S", "G"],
                "risk_threshold": "low",
                "keywords": [],
                "notification_channels": ["email", "webhook"],
            }
        },
    ]

    print("\n[Creating user preferences...]")
    for user in users:
        matcher.create_or_update_preference(user["user_id"], user["prefs"])
        print(f"  - Created preferences for {user['user_id']}")

    print("\n[User preferences created successfully]")


def demo_event_pipeline():
    """演示：完整的事件处理流程"""
    print("\n" + "="*80)
    print("DEMO 3: Complete Event Processing Pipeline")
    print("="*80)

    print("\n[Step 1: Scanning events...]")
    scanner = get_scanner()
    scan_result = scanner.run_scan()
    event_ids = scan_result.get("event_ids", [])
    print(f"  Scanned: {len(event_ids)} events")

    if not event_ids:
        print("  No events found in this scan. Using example event IDs for demo...")
        event_ids = ["example_event_1", "example_event_2"]

    print("\n[Step 2: Extracting structured information...]")
    print("  (Would use LLM to extract: title, company, metrics, risk level)")
    print("  Example extraction:")
    print("    - Title: Tesla Announces 50% Carbon Reduction Target")
    print("    - Company: Tesla")
    print("    - Type: emission_reduction")
    print("    - Severity: high")

    print("\n[Step 3: Scoring risk levels...]")
    print("  (Would use LLM to score: 0-100)")
    print("  Example score:")
    print("    - Risk Level: high")
    print("    - Score: 78.5/100")
    print("    - E: 0.9, S: 0.3, G: 0.2")

    print("\n[Step 4: Matching with users...]")
    print("  Example matches:")
    print("    - user_tech_esg: MATCH (interested in E+G)")
    print("    - user_social_focus: NO MATCH (only interested in S)")
    print("    - user_all_sectors: MATCH (all categories)")
    print("  Total: 2 users matched")

    print("\n[Step 5: Sending notifications...]")
    print("  Example notifications:")
    print("    - user_tech_esg: email + in_app")
    print("    - user_all_sectors: email + webhook")
    print("  Sent: 2 notifications")


def demo_api_usage():
    """演示：API 使用示例"""
    print("\n" + "="*80)
    print("DEMO 4: API Usage Examples")
    print("="*80)

    print("""
[API Endpoint Examples]

1. Trigger a scan (POST /scheduler/scan)
   curl -X POST http://localhost:8000/scheduler/scan

2. Check scan status (GET /scheduler/scan/status)
   curl http://localhost:8000/scheduler/scan/status

3. Get statistics (GET /scheduler/statistics)
   curl http://localhost:8000/scheduler/statistics?days=7

4. Analyze ESG (POST /agent/analyze)
   curl -X POST "http://localhost:8000/agent/analyze?question=分析特斯拉的ESG表现"

5. Get in-app notifications (custom endpoint)
   curl http://localhost:8000/notifications/user_tech_esg
    """)


def demo_statistics():
    """演示：统计和监控"""
    print("\n" + "="*80)
    print("DEMO 5: Statistics and Monitoring")
    print("="*80)

    orchestrator = get_orchestrator()

    print("\n[Pipeline Statistics (Last 7 days)]")
    stats = orchestrator.get_pipeline_statistics(days=7)

    if stats:
        print(f"  Total scanned:     {stats.get('total_scanned', 0)}")
        print(f"  Total extracted:   {stats.get('total_extracted', 0)}")
        print(f"  Total scored:      {stats.get('total_scored', 0)}")
        print(f"  Total notified:    {stats.get('total_notified', 0)}")
        print(f"  Success rate:      {stats.get('success_rate', 0):.1f}%")
    else:
        print("  (No data yet)")

    print("\n[Recent Scan Status]")
    status = orchestrator.get_scan_status()
    if status:
        print(f"  Status:     {status.get('status', 'N/A')}")
        print(f"  Job type:   {status.get('job_type', 'N/A')}")
        print(f"  Events:     {status.get('events_found', 0)}")
    else:
        print("  (No scans yet)")


def main():
    """主演示函数"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + "ESG Agentic RAG Copilot - Scheduler System Demo".center(78) + "║")
    print("╚" + "="*78 + "╝")

    print("""
This demo showcases the ESG event scheduling and notification system:

  1. Scanner     - Scans external data sources for new ESG events
  2. Extractor   - Uses LLM to extract structured information
  3. Matcher     - Matches events with user preferences
  4. RiskScorer  - Scores events with AI-based risk assessment
  5. Notifier    - Pushes notifications through multiple channels

The system supports both:
  - Passive mode: Users ask questions and get analyzed
  - Active mode:  System proactively scans and pushes relevant updates
    """)

    try:
        demo_basic_scan()
        demo_user_preferences()
        demo_event_pipeline()
        demo_api_usage()
        demo_statistics()

        print("\n" + "="*80)
        print("DEMO COMPLETE")
        print("="*80)

        print("""
[Next Steps]

1. Set up Supabase database with required tables (see SCHEDULER_README.md)

2. Configure environment variables in .env:
   - SUPABASE_URL
   - SUPABASE_KEY
   - OPENAI_API_KEY or DEEPSEEK_API_KEY
   - (Optional) Email/Webhook settings

3. Run the scheduler:
   python -m gateway.main
   # Then POST http://localhost:8000/scheduler/scan

4. Or start periodic scanning:
   orchestrator = get_orchestrator()
   orchestrator.schedule_periodic_scan_background(interval_minutes=30)

[Documentation]
   See docs/ for complete documentation
    """)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
