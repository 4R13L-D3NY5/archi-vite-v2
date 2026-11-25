# archi-vite-v2 — Engineering & Architecture Contract

## Overview

`archi-vite-v2` is the commercial evolution of `archi-vite`: a multi-tenant Document Management System (DMS) with external provider integrations (Google Drive, external DMS/storage) and asynchronous AI capabilities (OCR, classification, semantic search / RAG).

`archi-vite` remains frozen for thesis defense. Do not copy coupled persistence or single-tenant patterns from `archi-vite`.

## Architecture Rules (Non-Negotiable)

1. **Hexagonal Architecture (Ports & Adapters)** in `backend/`:
   - `domain/`: Pure business entities, value objects, domain events, and domain exceptions. **Zero** imports from FastAPI, SQLAlchemy, Pydantic HTTP schemas, or external SDKs.
   - `application/`: Use cases, command/query handlers, and Port interfaces (`StoragePort`, `DmsProviderPort`, `AiPipelinePort`, `AuthPort`). Depends only on `domain/`.
   - `infrastructure/`: Adapters implementing application ports (PostgreSQL/pgvector repositories, FastAPI routers, Google Drive adapter, external DMS adapter, Redis/worker queues, LLM/OCR clients).
2. **Multi-Tenancy & Security First**:
   - Every tenant-owned entity and query must be scoped by `tenant_id`.
   - Enforce RBAC and authorization checks in `application/` use cases, never scattered across HTTP route handlers.
3. **Asynchronous AI Processing**:
   - OCR, text extraction, chunking, embeddings, and classification must run in background workers (Redis queue), never inside synchronous HTTP request handlers.
4. **Frontend Modularity**:
   - Feature-based structure in `frontend/` using Container-Presentational separation where appropriate.

## Development Workflow (`gentle-ai` Harness)

- **Engram (Persistent Memory)**: Keep `archi-vite-v2` in its own Git repository with its own `origin` remote so Engram isolates project memories cleanly from `archi-vite`.
- **ODD (Organic Driven Development)**: Work in small, verifiable increments; write unit tests for `domain/` and `application/` without requiring a live DB or HTTP server.
- **Commits**: Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`). Never add `Co-Authored-By` or AI attribution.
