#!/usr/bin/env python3
"""
Fix confidence field precision in agent data tables
"""

import psycopg
from database_manager import DatabaseManager

def main():
    print("Fixing confidence field precision...")

    db = DatabaseManager()

    with psycopg.connect(db.conn_string) as conn:
        with conn.cursor() as cur:
            # Fix agent_responses.confidence: DECIMAL(5,4) -> DECIMAL(8,4)
            # Allows range: -9999.9999 to 9999.9999
            print("Updating agent_responses.confidence...")
            cur.execute("""
                ALTER TABLE agent_responses
                ALTER COLUMN confidence TYPE DECIMAL(8, 4)
            """)

            # Fix judge_decisions.confidence: DECIMAL(5,4) -> DECIMAL(8,4)
            print("Updating judge_decisions.confidence...")
            cur.execute("""
                ALTER TABLE judge_decisions
                ALTER COLUMN confidence TYPE DECIMAL(8, 4)
            """)

            conn.commit()

    print("✅ Confidence fields updated successfully!")
    print("   Old: DECIMAL(5, 4) - range 0.0000 to 9.9999")
    print("   New: DECIMAL(8, 4) - range 0.0000 to 9999.9999")
    print()
    print("System can now handle confidence values in any range (0-1, 0-100, etc.)")

if __name__ == "__main__":
    main()
