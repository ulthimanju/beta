# Pillar 3: Methodology

Focus: Test Pyramid (Unit, Integration, E2E ratio), CI/CD pipeline definitions (.github/workflows), 12-Factor App readiness, environment separation, Docker/IaC.

## What to look for

**Test Pyramid** — locate test directories/files and estimate the ratio of unit : integration : e2e tests. A healthy pyramid is unit-heavy, with fewer integration tests, and few e2e tests (roughly 70/20/10 as a loose reference, not a hard rule). Flag:
- **Inverted pyramid** (mostly e2e/integration, few unit tests) — slow, brittle test suite
- **No tests at all** — critical finding regardless of other pillar scores
- **Test-to-code ratio** — rough sanity check via file counts/line counts

**CI/CD** — check `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `Jenkinsfile`, `azure-pipelines.yml`. If present, note what stages run (lint, test, build, deploy) and whether tests actually gate merges/deploys or just run informationally.

**12-Factor App readiness** — check against the relevant factors:
1. Codebase: one codebase tracked in version control (assume yes if it's a git repo)
2. Dependencies: explicitly declared (manifest file present, no unpinned/global dependency reliance)
3. Config: stored in environment, not hardcoded (look for `.env.example`, absence of hardcoded connection strings/URLs in source)
4. Backing services: treated as attached resources (DB/cache/queue connections configurable, not hardcoded hostnames)
5. Build/release/run: distinct stages (CI/CD pipeline separates these, or Dockerfile multi-stage build does)
6. Processes: stateless where applicable
7. Port binding: services self-contained, not relying on runtime-injected app servers
8. Concurrency: process model documented/configurable if relevant
9. Disposability: fast startup/graceful shutdown handling (signal handlers, health checks)
10. Dev/prod parity: Docker/containerization narrows this gap
11. Logs: treated as event streams (stdout/structured logging, not writing to local log files assuming a persistent disk)
12. Admin processes: one-off admin/management tasks run as separate processes, not embedded ad hoc in app code

Don't score all 12 individually in the checklist — collapse into the 3-4 that matter most for the repo's context (config externalization, backing services as attached resources, logs as streams, and build/release/run separation are usually the highest-signal ones).

**Docker / IaC** — presence and quality of `Dockerfile` (multi-stage builds, non-root user, pinned base image versions), `docker-compose.yml` for local dev parity, and any IaC (`terraform/`, `pulumi/`, `cloudformation/`, `k8s/` manifests).

**Environment separation** — evidence of distinct dev/staging/prod configuration (e.g. `.env.development`, `.env.production`, environment-specific config files or feature flags) vs. a single hardcoded environment.

**Git hygiene** — `.gitignore` completeness (are `node_modules/`, `.env`, build artifacts excluded?), commit message quality if `git log` is accessible, branch naming conventions if visible.

## Evaluation checklist (produce pass/fail + note for each)

1. Automated tests exist
2. Test pyramid shape is healthy (unit-heavy) rather than inverted, or the imbalance is explainable/acceptable for the project type
3. CI pipeline exists and runs tests/lint on changes
4. CI gates merges/deploys on passing checks (not purely informational)
5. Configuration is externalized (env vars/config files), not hardcoded in source
6. Backing services (DB, cache, queues) are configurable, not hardcoded
7. Containerization (Docker) is present and reasonably well-constructed
8. `.gitignore` excludes secrets, dependencies, and build artifacts appropriately
9. Environment separation (dev/staging/prod) is evident

## Scoring guidance

- **90-100**: Healthy test pyramid, full CI/CD gating, strong 12-factor compliance, clean containerization
- **80-89**: Good test coverage and CI present, minor gaps (e.g. no staging config, thin IaC)
- **70-79**: Tests exist but pyramid is skewed or CI is informational-only; partial 12-factor compliance
- **60-69**: Sparse/inconsistent tests, no real CI gating, hardcoded config in places
- **<60**: No tests, no CI, hardcoded config/secrets, no containerization — critical test/security void
