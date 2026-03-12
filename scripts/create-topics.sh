#!/bin/bash
# create-topics.sh — Create all EduZim Kafka topics (Phase 1)
# Usage: bash scripts/create-topics.sh

set -e

KAFKA_CONTAINER="eduzim-kafka"
PARTITIONS=3
REPLICATION=1

TOPICS=(
  "eduzim.auth.user.created.v1"
  "eduzim.school.school.created.v1"
  "eduzim.school.class.created.v1"
  "eduzim.student.student.created.v1"
  "eduzim.student.enrollment.created.v1"
  "eduzim.attendance.recorded.v1"
  "eduzim.fees.invoice.created.v1"
  "eduzim.fees.payment.recorded.v1"
  "eduzim.comm.announcement.created.v1"
)

echo "📡 Creating Kafka topics..."

for TOPIC in "${TOPICS[@]}"; do
  docker exec $KAFKA_CONTAINER kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic "$TOPIC" \
    --partitions $PARTITIONS \
    --replication-factor $REPLICATION \
    --if-not-exists \
    2>/dev/null && echo "  ✅ $TOPIC" || echo "  ⏭️  $TOPIC (exists)"
done

echo ""
echo "📋 All topics:"
docker exec $KAFKA_CONTAINER kafka-topics --list --bootstrap-server localhost:9092
echo ""
echo "✅ Kafka topic setup complete"
