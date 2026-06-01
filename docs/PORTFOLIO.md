# Portfolio & LinkedIn visibility

Copy-paste ready content for LinkedIn, GitHub pinned posts, and interview walkthroughs.  
All claims below match the implementation in this repository.

---

## One-liner (headline / bio)

**Event-driven RAG platform** — RabbitMQ + Celery async ingestion, distributed workers, OTel/Prometheus/Grafana observability, **streaming LLM** answers, and **resilient retries** with DLQ routing.

---

## LinkedIn post — recommended (copy as-is)

I just shipped an end-to-end **RAG knowledge assistant** — not a single-script demo, but a **containerized, production-style** pipeline you can run with Docker Compose.

**What it does:** Upload PDFs → embed & index in Qdrant → ask questions → get **grounded, streamed** answers with source citations.

**Architecture highlights:**

- **Event-driven architecture** — ingestion and chat analytics decoupled via message queues  
- **RabbitMQ + Celery async processing** — durable PDF ingestion off the hot API path  
- **Distributed worker orchestration** — API and workers scale independently; late acks for crash safety  
- **Production observability stack** — OpenTelemetry, Prometheus, Grafana (queues, workers, chat latency)  
- **Streaming LLM responses** — SSE token streaming from Gemini through FastAPI to React  
- **Resilient retry mechanisms** — exponential backoff, jitter, dead-letter queues, bounded publish retries  

**Stack:** FastAPI · Celery · RabbitMQ · Redis · Qdrant · Gemini · React · Docker

Demo: `make up` → http://localhost:3000  
Repo: *[paste your GitHub URL]*

`#FastAPI #RAG #Celery #RabbitMQ #LLM #SystemDesign #Observability #PortfolioProject`

---

## LinkedIn post — short version

Built a **RAG platform** with:

✅ **Event-driven architecture**  
✅ **RabbitMQ + Celery** async PDF ingestion  
✅ **Distributed worker orchestration**  
✅ **Production observability stack** (OTel → Prometheus → Grafana)  
✅ **Streaming LLM responses** (SSE, token-by-token)  
✅ **Resilient retry mechanisms** (backoff, jitter, DLQ)

Upload docs → chat with citations → watch queues & metrics in real time.

---

## Carousel slide outline (6 slides)

Use screenshots from your local stack:

| Slide | Title | Screenshot / asset |
|-------|--------|-------------------|
| 1 | **Event-driven architecture** | Architecture diagram from [ARCHITECTURE.md](../ARCHITECTURE.md) |
| 2 | **RabbitMQ + Celery async processing** | RabbitMQ Management → `pdf_ingestion_queue` |
| 3 | **Distributed worker orchestration** | `docker compose ps` or Flower workers view |
| 4 | **Production observability stack** | Grafana `rabbitmq` or `worker` dashboard |
| 5 | **Streaming LLM responses** | Frontend mid-stream + browser Network → EventStream |
| 6 | **Resilient retry mechanisms** | DLQ message count + worker retry metrics panel |

**Slide 6 caption:** Exponential backoff + jitter · max 5 retries · DLQ for poison messages

---

## 60-second demo script (screen recording)

1. **0:00–0:10** — `docker compose ps` or README architecture diagram  
2. **0:10–0:25** — Upload 2 PDFs on http://localhost:3000, show **Processing → Indexed**  
3. **0:25–0:45** — Ask a question; show **streaming** answer + **Sources** expand  
4. **0:45–0:55** — Grafana: queue depth + chat latency panel  
5. **0:55–1:00** — Optional: RabbitMQ DLQ after uploading a bad PDF (`make e2e`)

---

## Interview talking points

### “Why event-driven?”

Uploads are bursty and slow (parse, embed, vector write). Queuing keeps the API responsive and lets workers scale independently. Chat analytics are optional side-effects — perfect as fire-and-forget events.

### “How do retries work?”

Two layers: (1) API publish retries for transient broker issues; (2) Celery task retries with exponential backoff + jitter for Gemini rate limits and Qdrant errors. Permanent failures and exhausted retries go to the **DLQ** via RabbitMQ dead-letter exchange.

### “How is chat independent of the worker queue?”

Chat embeds and retrieves inline in the API process. Only analytics optionally hit RabbitMQ. If the broker is down, users still get answers; analytics may drop.

### “What would you add for real production?”

Auth, TLS, secrets manager, horizontal pod autoscaling on queue depth, managed MQ/Redis, alerting on DLQ growth and p95 chat latency, and integration tests in CI.

---

## GitHub README badge ideas (optional HTML)

```markdown
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?logo=rabbitmq)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus)
![Grafana](https://img.shields.io/badge/Grafana-F46800?logo=grafana)
```

---

## Keywords for ATS / recruiter search

Event-driven architecture · message queue · RabbitMQ · Celery · distributed systems · microservices · RAG · retrieval-augmented generation · vector database · Qdrant · LLM · Gemini · streaming SSE · observability · OpenTelemetry · Prometheus · Grafana · dead letter queue · retry backoff · FastAPI · React · Docker
