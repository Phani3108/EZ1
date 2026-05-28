# EduZim Platform — Makefile
# Usage: make up | make down | make logs | make test

.PHONY: up down logs test seed topics clean rebuild

# Start all services
up:
	docker compose up -d --build
	@echo "✅ EduZim stack is up"
	@echo "   Gateway:    http://localhost:8000"
	@echo "   Auth:       http://localhost:8001/docs"
	@echo "   School:     http://localhost:8002/docs"
	@echo "   Student:    http://localhost:8003/docs"
	@echo "   Attendance: http://localhost:8004/docs"
	@echo "   Fees:       http://localhost:8005/docs"
	@echo "   Comms:      http://localhost:8006/docs"

# Stop all services
down:
	docker compose down

# Tail logs
logs:
	docker compose logs -f

# Logs for a specific service (usage: make log s=identity)
log:
	docker compose logs -f $(s)

# Run tests across all services.
# Phase 19d — `make test` was broken since the PH2 service consolidation
# deleted school-service / student-service / attendance-service /
# assessment-service. The four surviving services are below; the
# reporting-service has Kafka-consumer tests only (no HTTP surface).
test:
	@echo "🧪 Running shared lib tests..."
	cd shared && python3 -m pytest tests/ -v
	@echo "🧪 Running identity tests..."
	cd services/identity && python3 -m pytest tests/ -v
	@echo "🧪 Running academics tests..."
	cd services/academics && python3 -m pytest tests/ -v
	@echo "🧪 Running finance tests..."
	cd services/finance && python3 -m pytest tests/ -v
	@echo "🧪 Running communications tests..."
	cd services/communications && python3 -m pytest tests/ -v
	@echo "🧪 Running reporting-service tests..."
	cd services/reporting-service && python3 -m pytest tests/ -v
	@echo "🧪 Running api-gateway tests..."
	cd services/api-gateway && python3 -m pytest tests/ -v

# Create Kafka topics
topics:
	@bash scripts/create-topics.sh

# Seed dev data
seed:
	@bash scripts/dev-seed.sh

# Clean volumes
clean:
	docker compose down -v
	@echo "🗑️  Volumes cleaned"

# Full rebuild
rebuild: clean up topics seed

# ── E2E (Playwright) ──────────────────────────────────────────
# Starts the full docker stack, waits for health, runs Playwright
# E2E tests, then exports artifacts (screenshots, traces, videos)
# into apps/admin-web/test-results/ and apps/admin-web/playwright-report/.
#
# Usage:
#   make e2e              — full run (stack + tests + report)
#   make e2e-only         — tests only (assumes stack is up)

E2E_RESULTS := apps/admin-web/test-results
E2E_REPORT  := apps/admin-web/playwright-report

.PHONY: e2e e2e-only

e2e: up _wait-healthy e2e-only

e2e-only:
	@echo "🎭 Running Playwright E2E tests..."
	cd apps/admin-web && npx playwright test || true
	@echo ""
	@echo "📦 Artifacts:"
	@echo "   Screenshots / traces / videos → $(E2E_RESULTS)/"
	@echo "   HTML report                   → $(E2E_REPORT)/"
	@echo ""
	@echo "💡 Open report: make e2e-report"

e2e-report:
	cd apps/admin-web && npx playwright show-report playwright-report

e2e-clean:
	@echo "🗑️  Cleaning E2E artifacts..."
	rm -rf $(E2E_RESULTS) $(E2E_REPORT)
	@echo "✅ Cleaned test-results/ and playwright-report/"

e2e-ci:
	@echo "🎭 Running Playwright E2E (CI mode — headless, strict exit)..."
	cd apps/admin-web && npx playwright test --reporter=html
	@echo "✅ E2E CI run complete"

# ── Teacher-web E2E ──────────────────────────────────────────

E2E_TEACHER_RESULTS := apps/teacher-web/test-results
E2E_TEACHER_REPORT  := apps/teacher-web/playwright-report

.PHONY: e2e-teacher e2e-teacher-only

e2e-teacher: up _wait-healthy e2e-teacher-only

e2e-teacher-only:
	@echo "🎭 Running Teacher-web Playwright E2E tests..."
	cd apps/teacher-web && npx playwright test || true
	@echo ""
	@echo "📦 Artifacts:"
	@echo "   Screenshots / traces / videos → $(E2E_TEACHER_RESULTS)/"
	@echo "   HTML report                   → $(E2E_TEACHER_REPORT)/"
	@echo ""
	@echo "💡 Open report: make e2e-teacher-report"

e2e-teacher-report:
	cd apps/teacher-web && npx playwright show-report playwright-report

e2e-teacher-clean:
	@echo "🗑️  Cleaning Teacher E2E artifacts..."
	rm -rf $(E2E_TEACHER_RESULTS) $(E2E_TEACHER_REPORT)
	@echo "✅ Cleaned teacher-web test-results/ and playwright-report/"

_wait-healthy:
	@echo "⏳ Waiting for services to be healthy..."
	@for i in $$(seq 1 30); do \
		curl -sf http://localhost:8000/health > /dev/null 2>&1 && break; \
		printf "."; sleep 2; \
	done
	@echo " ✅ Gateway ready"

# Health check
health:
	@echo "Checking services..."
	@curl -sf http://localhost:8000/health && echo " ✅ Gateway" || echo " ❌ Gateway"
	@curl -sf http://localhost:8001/health && echo " ✅ Auth" || echo " ❌ Auth"
	@curl -sf http://localhost:8002/health && echo " ✅ School" || echo " ❌ School"
	@curl -sf http://localhost:8003/health && echo " ✅ Student" || echo " ❌ Student"
	@curl -sf http://localhost:8004/health && echo " ✅ Attendance" || echo " ❌ Attendance"
	@curl -sf http://localhost:8005/health && echo " ✅ Fees" || echo " ❌ Fees"
	@curl -sf http://localhost:8006/health && echo " ✅ Comms" || echo " ❌ Comms"
	@curl -sf http://localhost:8007/health && echo " ✅ Reporting" || echo " ❌ Reporting"
	@curl -sf http://localhost:8008/health && echo " ✅ Assessment" || echo " ❌ Assessment"
