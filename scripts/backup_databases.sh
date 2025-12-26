#!/bin/bash
# Backup databases from Mac Mini to MacBook Pro
# This is ONE-WAY: Mac Mini → MacBook (for backup only)

set -e

BACKUP_DIR=~/clat_preparation/database_backups/$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

echo "======================================================================"
echo "  Database Backup: Mac Mini → MacBook Pro"
echo "======================================================================"
echo ""
echo "📁 Backup directory: $BACKUP_DIR"
echo ""

# Backup main databases
echo "📦 Backing up databases..."
scp mac-mini:~/clat_preparation/revision_tracker.db "$BACKUP_DIR/"
scp mac-mini:~/clat_preparation/assessment_tracker.db "$BACKUP_DIR/"
scp mac-mini:~/clat_preparation/assessment.db "$BACKUP_DIR/" 2>/dev/null || true
scp mac-mini:~/clat_preparation/math_tracker.db "$BACKUP_DIR/"
scp mac-mini:~/clat_preparation/auth/users.db "$BACKUP_DIR/" 2>/dev/null || true
scp mac-mini:~/clat_preparation/math/math_tracker.db "$BACKUP_DIR/math_tracker_module.db"

echo ""
echo "✅ Backup complete!"
echo ""
echo "📊 Backed up:"
ls -lh "$BACKUP_DIR"
echo ""
echo "💡 To restore a database:"
echo "   cp $BACKUP_DIR/[database].db ~/clat_preparation/"
echo ""
