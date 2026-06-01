#!/usr/bin/env bash
#
# End-to-end validation + failure-simulation suite for the Multi-Agent RAG stack.
#
# Validates the full async flow:
#   PDF upload -> RabbitMQ publish -> Celery consumption -> embedding ->
#   Qdrant indexing -> chat retrieval -> streamed response
#
# And simulates failures:
#   * malformed PDF  -> DLQ routing
#   * RabbitMQ restart during operation -> worker recovery
#   * consumer (worker) crash -> recovery with no message loss
#   * Qdrant outage  -> retry exhaustion -> DLQ
#
# Usage:
#   ./scripts/e2e_test.sh            # run everything (incl. slow retry test)
#   RUN_SLOW=0 ./scripts/e2e_test.sh # skip the slow retry-exhaustion test
#
# Exit code is non-zero if any check fails.

set -uo pipefail

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
API="${API_BASE:-http://localhost:8000}"
QDRANT="${QDRANT_BASE:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-documents}"
RUN_SLOW="${RUN_SLOW:-1}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

WORKDIR="$(mktemp -d)"
PASS=0
FAIL=0

# Colors (fall back to plain if not a tty)
if [ -t 1 ]; then
  G="\033[0;32m"; R="\033[0;31m"; Y="\033[0;33m"; B="\033[0;34m"; N="\033[0m"
else
  G=""; R=""; Y=""; B=""; N=""
fi

section() { echo -e "\n${B}========== $* ==========${N}"; }
pass()    { echo -e "  ${G}PASS${N}  $*"; PASS=$((PASS+1)); }
fail()    { echo -e "  ${R}FAIL${N}  $*"; FAIL=$((FAIL+1)); }
info()    { echo -e "  ${Y}··${N}    $*"; }

cleanup() {
  section "Cleanup — restoring full stack"
  docker compose start qdrant worker rabbitmq >/dev/null 2>&1 || true
  rm -rf "$WORKDIR"
  section "RESULT: ${PASS} passed, ${FAIL} failed"
  [ "$FAIL" -eq 0 ] || exit 1
}
trap cleanup EXIT

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
jget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

make_pdf() { # $1=path  $2=text
  python3 - "$1" "$2" <<'PY'
import sys
path, text = sys.argv[1], sys.argv[2]
objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
]
content = ("BT /F1 18 Tf 72 720 Td (" + text + ") Tj ET").encode()
objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content))
objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
out = bytearray(b"%PDF-1.4\n")
offs = []
for i, o in enumerate(objs, 1):
    offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
xref = len(out); n = len(objs) + 1
out += b"xref\n0 %d\n0000000000 65535 f \n" % n
for off in offs: out += b"%010d 00000 n \n" % off
out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (n, xref)
open(path, "wb").write(out)
PY
}

qcount() { # $1=queue name -> ready+unacked message count (authoritative)
  docker compose exec -T rabbitmq rabbitmqctl list_queues name messages 2>/dev/null \
    | awk -v q="$1" '$1==q{print $2}'
}

qpoints() { # qdrant points_count
  curl -s "$QDRANT/collections/$COLLECTION" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('result',{}).get('points_count',0))" 2>/dev/null || echo 0
}

upload() { # $1=file -> echoes document_id
  curl -s -X POST "$API/ingest/upload" -F "file=@$1;type=application/pdf" | jget document_id
}

poll_status() { # $1=document_id  $2=target  $3=timeout_s -> 0 if reached
  local doc="$1" target="$2" timeout="$3" waited=0 s
  while [ "$waited" -lt "$timeout" ]; do
    s=$(curl -s "$API/ingest/$doc" | jget status)
    [ "$s" = "$target" ] && return 0
    [ "$s" = "DEAD_LETTER" ] && [ "$target" != "DEAD_LETTER" ] && return 2
    sleep 3; waited=$((waited+3))
  done
  return 1
}

wait_healthy() { # $1=container  $2=timeout
  local c="$1" t="$2" w=0 h
  while [ "$w" -lt "$t" ]; do
    h=$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null || echo none)
    [ "$h" = "healthy" ] && return 0
    sleep 3; w=$((w+3))
  done
  return 1
}

# --------------------------------------------------------------------------
# 0. Preflight
# --------------------------------------------------------------------------
section "0. Preflight — services healthy"
ready=$(curl -s "$API/health/ready")
if [ "$(echo "$ready" | jget status)" = "ok" ]; then
  pass "API /health/ready ok ($ready)"
else
  fail "API not ready: $ready"
  echo -e "${R}Aborting — bring the stack up first: docker compose up -d${N}"; exit 1
fi

# --------------------------------------------------------------------------
# 1. End-to-end happy path
# --------------------------------------------------------------------------
section "1. E2E flow: upload -> publish -> consume -> embed -> index -> chat -> stream"
make_pdf "$WORKDIR/e2e.pdf" "Multi-Agent RAG end to end validation document. The capital of testing is reliability."
pts_before=$(qpoints)

doc=$(upload "$WORKDIR/e2e.pdf")
if [ -n "$doc" ]; then pass "PDF upload accepted (document_id=$doc)"; else fail "upload returned no document_id"; fi

if poll_status "$doc" SUCCESS 60; then
  pass "Celery consumed + embedded + indexed (status=SUCCESS)"
else
  fail "ingestion did not reach SUCCESS in time"
fi

pts_after=$(qpoints)
if [ "$pts_after" -gt "$pts_before" ]; then
  pass "Qdrant indexing verified (points $pts_before -> $pts_after)"
else
  fail "Qdrant points did not increase ($pts_before -> $pts_after)"
fi

chat=$(curl -s -X POST "$API/chat" -H 'Content-Type: application/json' \
  -d '{"query":"What is this validation document about?","top_k":3,"session_id":"e2e-json"}')
hits=$(echo "$chat" | jget retrieval_hits)
ans=$(echo "$chat" | jget answer)
if [ -n "$ans" ] && [ "${hits:-0}" -ge 1 ]; then
  pass "Chat retrieval + answer (hits=$hits, provider=$(echo "$chat" | jget provider))"
else
  fail "chat retrieval failed: $chat"
fi

stream=$(curl -sN -X POST "$API/chat/stream" -H 'Content-Type: application/json' \
  -d '{"query":"Summarize the document.","session_id":"e2e-stream"}')
if echo "$stream" | grep -q '"type": "token"' && echo "$stream" | grep -q '"type": "done"'; then
  pass "Streamed response delivered (token + done events)"
else
  fail "streaming did not produce token/done events"
fi

# --------------------------------------------------------------------------
# 2. Failure: malformed PDF -> DLQ routing
# --------------------------------------------------------------------------
section "2. Failure sim: malformed PDF -> DLQ routing"
dlq_before=$(qcount dead_letter_queue); dlq_before=${dlq_before:-0}
printf '%%PDF-1.4\nnot a real pdf body XXXXXXXXXXXXXXXXXXXXXXXX' > "$WORKDIR/bad.pdf"
bad=$(upload "$WORKDIR/bad.pdf")
info "uploaded poison doc=$bad (dlq before=$dlq_before)"
poll_status "$bad" DEAD_LETTER 30; rc=$?
dlq_after=$(qcount dead_letter_queue); dlq_after=${dlq_after:-0}
if [ "$rc" -eq 0 ]; then
  pass "Poison message status=DEAD_LETTER"
else
  fail "poison message did not reach DEAD_LETTER status"
fi
if [ "$dlq_after" -gt "$dlq_before" ]; then
  pass "DLQ messages visible during failure (dead_letter_queue $dlq_before -> $dlq_after)"
else
  fail "dead_letter_queue did not grow ($dlq_before -> $dlq_after)"
fi

# --------------------------------------------------------------------------
# 3. Failure: RabbitMQ restart -> worker recovery
# --------------------------------------------------------------------------
section "3. Failure sim: RabbitMQ restart during operation -> worker recovery"
info "restarting rabbitmq…"
docker compose restart rabbitmq >/dev/null 2>&1
if wait_healthy rag_rabbitmq 60; then pass "RabbitMQ healthy again after restart"; else fail "rabbitmq did not become healthy"; fi
sleep 5  # give the worker a moment to re-establish its consumer
make_pdf "$WORKDIR/after_restart.pdf" "Document ingested after a broker restart to prove worker recovery."
doc=$(upload "$WORKDIR/after_restart.pdf")
if poll_status "$doc" SUCCESS 60; then
  pass "Worker recovered after broker restart (post-restart ingest SUCCESS)"
else
  fail "ingestion failed after broker restart (worker did not recover)"
fi

# --------------------------------------------------------------------------
# 4. Failure: consumer crash recovery (no message loss)
# --------------------------------------------------------------------------
section "4. Failure sim: consumer crash recovery (acks_late => no loss)"
info "stopping worker, then queueing a task while it is down…"
docker compose stop worker >/dev/null 2>&1
make_pdf "$WORKDIR/crash.pdf" "Task queued while the consumer was crashed; it must be processed on recovery."
doc=$(upload "$WORKDIR/crash.pdf")
sleep 2
depth=$(qcount pdf_ingestion_queue); depth=${depth:-0}
if [ "$depth" -ge 1 ]; then
  pass "Message durably queued while consumer down (pdf_ingestion_queue=$depth)"
else
  info "pdf_ingestion_queue depth=$depth (task may already be reserved)"
fi
info "restarting worker…"
docker compose start worker >/dev/null 2>&1
if poll_status "$doc" SUCCESS 60; then
  pass "Consumer recovered and processed queued task (no message loss)"
else
  fail "queued task was not processed after worker restart"
fi

# --------------------------------------------------------------------------
# 5. Failure: Qdrant outage -> retry exhaustion -> DLQ  (slow)
# --------------------------------------------------------------------------
if [ "$RUN_SLOW" = "1" ]; then
  section "5. Failure sim: Qdrant outage -> retry exhaustion -> DLQ (slow)"
  dlq_before=$(qcount dead_letter_queue); dlq_before=${dlq_before:-0}
  info "stopping qdrant to force transient write failures…"
  docker compose stop qdrant >/dev/null 2>&1
  make_pdf "$WORKDIR/retry.pdf" "This ingestion will fail transiently until retries are exhausted."
  doc=$(upload "$WORKDIR/retry.pdf")
  info "uploaded doc=$doc; observing retries (backoff: ~2,4,8,16,32s)…"
  # First confirm it enters RETRY, then wait for exhaustion -> DLQ.
  seen_retry=0
  for i in $(seq 1 8); do
    s=$(curl -s "$API/ingest/$doc" | jget status)
    [ "$s" = "RETRY" ] && { seen_retry=1; break; }
    [ "$s" = "DEAD_LETTER" ] && break
    sleep 3
  done
  [ "$seen_retry" -eq 1 ] && pass "Task entered automatic RETRY on transient failure" \
                          || info "did not observe RETRY window (may have moved fast)"
  if poll_status "$doc" DEAD_LETTER 150; then
    pass "Retry exhaustion routed task to DLQ (status=DEAD_LETTER)"
  else
    fail "task did not reach DLQ after retry exhaustion"
  fi
  dlq_after=$(qcount dead_letter_queue); dlq_after=${dlq_after:-0}
  [ "$dlq_after" -gt "$dlq_before" ] && pass "DLQ grew after retry exhaustion ($dlq_before -> $dlq_after)" \
                                     || fail "DLQ did not grow ($dlq_before -> $dlq_after)"
  info "restarting qdrant…"
  docker compose start qdrant >/dev/null 2>&1
  wait_healthy rag_qdrant 30 || true
else
  section "5. (skipped) retry-exhaustion test — set RUN_SLOW=1 to enable"
fi

# Summary is printed by the cleanup trap.
