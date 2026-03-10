#!/bin/bash
# Fix missing Session import in backend/router/monitor.py

set -e

MONITOR_FILE="backend/router/monitor.py"

echo "🔧 Fixing Session import in $MONITOR_FILE"

# Check if file exists
if [ ! -f "$MONITOR_FILE" ]; then
    echo "❌ Error: $MONITOR_FILE not found!"
    echo "This file should exist in your local repository."
    exit 1
fi

# Check if Session import already exists
if grep -q "from sqlalchemy.orm import Session" "$MONITOR_FILE"; then
    echo "✅ Session import already exists!"
    exit 0
fi

# Create backup
cp "$MONITOR_FILE" "$MONITOR_FILE.backup"
echo "📦 Created backup: $MONITOR_FILE.backup"

# Find the line number where we should add the import
# Look for existing SQLAlchemy or typing imports
IMPORT_LINE=$(grep -n "^from typing import\|^from sqlalchemy" "$MONITOR_FILE" | tail -1 | cut -d: -f1)

if [ -z "$IMPORT_LINE" ]; then
    # No typing/sqlalchemy imports found, add after first import
    IMPORT_LINE=$(grep -n "^from\|^import" "$MONITOR_FILE" | head -1 | cut -d: -f1)
fi

# Insert the import
if [ -n "$IMPORT_LINE" ]; then
    # Add after the found import line
    NEXT_LINE=$((IMPORT_LINE + 1))
    sed -i "${NEXT_LINE}i from sqlalchemy.orm import Session" "$MONITOR_FILE"
    echo "✅ Added 'from sqlalchemy.orm import Session' at line $NEXT_LINE"
else
    # Add at the beginning of the file
    sed -i '1i from sqlalchemy.orm import Session' "$MONITOR_FILE"
    echo "✅ Added 'from sqlalchemy.orm import Session' at line 1"
fi

echo ""
echo "🎉 Fix applied successfully!"
echo ""
echo "Verify the import was added:"
echo "$ grep -n 'from sqlalchemy.orm import Session' $MONITOR_FILE"
echo ""
echo "If you need to restore the backup:"
echo "$ cp $MONITOR_FILE.backup $MONITOR_FILE"
