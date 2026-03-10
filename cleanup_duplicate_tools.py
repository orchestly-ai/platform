#!/usr/bin/env python3
"""
Clean up duplicate MCP tools from the database
"""

import asyncio
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_duplicate_tools():
    """Remove duplicate tools, keeping only the most recent one for each tool_name/server_id combination"""

    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable must be set")

    # Create synchronous engine for this operation
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Begin transaction
        trans = conn.begin()

        try:
            # First, identify duplicates
            result = conn.execute(text("""
                SELECT tool_name, server_id, COUNT(*) as count
                FROM mcp_tools
                GROUP BY tool_name, server_id
                HAVING COUNT(*) > 1
            """))

            duplicates = result.fetchall()
            total_duplicates = 0

            print(f"Found {len(duplicates)} tool/server combinations with duplicates")

            for tool_name, server_id, count in duplicates:
                print(f"  - Tool '{tool_name}' on server {server_id}: {count} copies")

                # Keep the most recently discovered one, delete the rest
                conn.execute(text("""
                    DELETE FROM mcp_tools
                    WHERE tool_name = :tool_name
                      AND server_id = :server_id
                      AND tool_id NOT IN (
                          SELECT tool_id FROM (
                              SELECT tool_id
                              FROM mcp_tools
                              WHERE tool_name = :tool_name
                                AND server_id = :server_id
                              ORDER BY discovered_at DESC
                              LIMIT 1
                          ) AS keep
                      )
                """), {"tool_name": tool_name, "server_id": server_id})

                total_duplicates += (count - 1)

            # Commit the transaction
            trans.commit()
            print(f"\nSuccessfully removed {total_duplicates} duplicate tools")

            # Show final count
            result = conn.execute(text("SELECT COUNT(*) FROM mcp_tools"))
            total = result.scalar()
            print(f"Total tools remaining: {total}")

        except Exception as e:
            trans.rollback()
            print(f"Error: {e}")
            raise

if __name__ == "__main__":
    cleanup_duplicate_tools()