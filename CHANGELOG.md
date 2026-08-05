# Changelog

All notable changes are recorded here. Procora follows Semantic Versioning.

## 1.0.0 - 2026-08-05

- Stabilized the exported Python API, immutable result/metadata models, public exception
  hierarchy, typed connection protocols, and custom backend contract.
- Discard unsafe pooled connections after failed preparation, reset, rollback, or an
  uncertain commit outcome; documented releaser/discarder ownership rules.
- Made unqualified schema resolution procedure-aware, including PostgreSQL effective
  `search_path` visibility and SQL Server default-schema then `dbo` fallback.
- Partitioned metadata by resolved schema and made TTL/LRU/single-flight cache
  invalidation race-safe with bounded generation bookkeeping.
- Expanded real procedure coverage for errors, defaults, output values, duplicate
  columns, multiple result sets, native values, timeout restoration, and connection reuse.
- Added exact-minimum and latest driver testing plus PostgreSQL 11/14/17, MySQL 8.0/8.4,
  and SQL Server 2019/2022 service matrices.
- Added an optional scheduled/manual Azure SQL smoke workflow.
- Raised failure-path coverage enforcement to 90% and upgraded GitHub Actions to the
  Node 24-based v7 releases.
- Documented SQL Server defaulted `OUTPUT` behavior, cache identifier casing, buffered
  results, backend-specific identifier limits, and the 1.x API stability policy.

## 0.9.0 - 2026-08-04

- Replaced the former web application with a database-neutral Python library.
- Added SQL Server, PostgreSQL, and MySQL procedure adapters.
- Added output parameters, multiple result sets, metadata discovery, pooling, and
  timeout handling.
- Added safe pooled-transaction cleanup and session-setting restoration.
- Added immutable result models, cache invalidation, and single-connection discovery.
- Added strict typing, package builds, Python 3.10–3.14 CI, and real database tests.
