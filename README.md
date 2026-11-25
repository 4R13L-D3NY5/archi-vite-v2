# archi-vite-v2

Commercial, multi-tenant Document Management System (DMS) with external DMS/cloud integrations (Google Drive, S3/external DMS) and asynchronous AI pipelines (OCR, auto-classification, semantic search / RAG).

## Planned Phases

- **Phase 0**: Repository bootstrapping, architecture contract (`AGENTS.md`), and `gentle-ai` harness isolation.
- **Phase 1**: Hexagonal backend foundation (`domain/`, `application/`, `infrastructure/`), PostgreSQL + `pgvector`, Redis, and unit tests.
- **Phase 2**: Multi-tenancy, OAuth2/JWT authentication, RBAC, and audit logging.
- **Phase 3**: External integrations (`DmsProviderPort` adapters for Google Drive and secondary DMS).
- **Phase 4**: Asynchronous AI workers (OCR, chunking, embeddings, RAG respecting tenant permissions).
- **Phase 5**: Commercial React/Vite frontend, observability, rate limiting, and CI/CD.
