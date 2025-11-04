#!/usr/bin/env python3
"""
Quick script to check agent data capture status
"""

from agent_data_logger import AgentDataLogger
from database_manager import DatabaseManager

def main():
    # Initialize
    db = DatabaseManager()
    logger = AgentDataLogger(db.conn_string)

    print("\n" + "="*80)
    print("AGENT DATA CAPTURE STATUS")
    print("="*80)

    # Check each table
    with logger._get_connection() as conn:
        with conn.cursor() as cur:
            # Analysis sessions
            cur.execute("SELECT COUNT(*) as count FROM analysis_sessions")
            sessions_count = cur.fetchone()['count']
            print(f"\n📊 Analysis Sessions: {sessions_count}")

            if sessions_count > 0:
                cur.execute("""
                    SELECT session_id, pair, timestamp, current_price, spread_pips, can_trade
                    FROM analysis_sessions
                    ORDER BY timestamp DESC
                    LIMIT 5
                """)
                print("\nLatest sessions:")
                for row in cur.fetchall():
                    print(f"  {row['session_id']} | {row['pair']} | {row['timestamp']} | Price: {row['current_price']} | Spread: {row['spread_pips']} pips")

            # Market snapshots
            cur.execute("SELECT COUNT(*) as count FROM market_snapshots")
            snapshots_count = cur.fetchone()['count']
            print(f"\n📸 Market Snapshots: {snapshots_count}")

            # Indicators
            cur.execute("SELECT COUNT(*) as count FROM indicator_values")
            indicators_count = cur.fetchone()['count']
            print(f"\n📈 Indicator Records: {indicators_count}")

            # Agent responses
            cur.execute("""
                SELECT agent_name, COUNT(*) as count
                FROM agent_responses
                GROUP BY agent_name
                ORDER BY agent_name
            """)
            print(f"\n🤖 Agent Responses:")
            for row in cur.fetchall():
                print(f"  {row['agent_name']}: {row['count']}")

            # Judge decisions
            cur.execute("""
                SELECT judge_name, COUNT(*) as total,
                       SUM(CASE WHEN approved THEN 1 ELSE 0 END) as approved
                FROM judge_decisions
                GROUP BY judge_name
                ORDER BY judge_name
            """)
            print(f"\n⚖️  Judge Decisions:")
            for row in cur.fetchall():
                total = row['total']
                approved = row['approved']
                rate = (approved / total * 100) if total > 0 else 0
                print(f"  {row['judge_name']}: {approved}/{total} approved ({rate:.1f}%)")

    print("\n" + "="*80)

    if sessions_count == 0:
        print("\n⚠️  No data captured yet. System needs ~20 minutes to collect enough")
        print("   market data before running first analysis.")
    else:
        print(f"\n✅ Capturing data successfully! {sessions_count} analysis sessions logged.")

    print()


if __name__ == "__main__":
    main()
