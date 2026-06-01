# RAG Knowledge Assistant — Frontend

A lightweight React + TypeScript + Vite + Tailwind frontend for the Multi-Agent
RAG backend. Two-panel layout: multi-PDF upload (left) and streaming RAG chat
(right).

**Project docs:** [../README.md](../README.md) · [../ARCHITECTURE.md](../ARCHITECTURE.md) · [../docs/PORTFOLIO.md](../docs/PORTFOLIO.md)

## Features

- **Multi-PDF upload** — drag-and-drop or file picker, multiple files at once
- **Client-side validation** — PDF type + size (max 50 MB, mirrors the backend)
- **Live upload progress** + **processing status** polled from the API
  (`Queued → Uploading → Processing → Processed`, with retry on failure)
- **Streaming RAG chat** — token-by-token Gemini responses over SSE, with
  expandable retrieved sources and per-answer latency/token stats
- **Robust error handling** — unsupported type, oversized file, network
  interruption, API downtime, and broker-unavailable (503) are all surfaced

## Stack

React 19 · TypeScript · Vite 6 · Tailwind CSS 4 · Axios · lucide-react

## Getting started

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server proxies `/api/*` to `http://localhost:8000` (the FastAPI
backend), so no CORS setup is needed for local development. Make sure the
backend stack is running (`docker compose up -d` in the project root).

### Configuration

| Variable             | Purpose                                                        |
| -------------------- | -------------------------------------------------------------- |
| `VITE_API_BASE_URL`  | API origin for a static build (e.g. `http://localhost:8000`).  |
| `VITE_PROXY_TARGET`  | Dev-only: override the proxy target (defaults to `:8000`).     |

If `VITE_API_BASE_URL` is unset, the app calls `/api` and relies on the Vite
proxy (dev). For `npm run build` + `npm run preview`, set `VITE_API_BASE_URL`
(the backend already enables CORS).

## API endpoints used

| Action            | Endpoint                  |
| ----------------- | ------------------------- |
| Upload a PDF      | `POST /ingest/upload`     |
| Poll status       | `GET /ingest/{id}`        |
| Streaming chat    | `POST /chat/stream` (SSE) |

## Scripts

```bash
npm run dev        # start dev server
npm run build      # typecheck + production build
npm run preview    # preview the production build
npm run typecheck  # type-check only
```

## Project structure

```
src/
  api/         axios client, types, document + chat calls (SSE parser)
  hooks/       useUploads (upload + status polling), useChat (streaming)
  components/
    upload/    UploadPanel, UploadDropzone, UploadProgress, UploadStatusList
    chat/      ChatPanel, MessageList, MessageBubble, ChatInput, Sources
  lib/         validation, formatting helpers
```
