# Pillar 4: Software Principles

Focus: SOLID, DRY, KISS, YAGNI, centralized error handling & failure modes, structured logging & telemetry, security posture (no hardcoded secrets, dependency auditing).

## What to look for

**SOLID**
- **Single Responsibility**: do classes/modules have one clear reason to change, or are they doing multiple unrelated jobs?
- **Open/Closed**: is new behavior typically added via extension (new classes/strategies) rather than editing existing conditionals/switch statements repeatedly?
- **Liskov Substitution**: do subtypes actually honor the contracts of their base types (no subclasses throwing "not implemented" on inherited methods)?
- **Interface Segregation**: are interfaces small and focused, or are there "fat" interfaces forcing implementers to stub out irrelevant methods?
- **Dependency Inversion**: do high-level modules depend on abstractions (interfaces) rather than concrete low-level implementations? Is dependency injection used, or are dependencies instantiated directly inside consuming classes?

**DRY (Don't Repeat Yourself)** — grep for duplicated logic blocks, copy-pasted functions with minor variations, repeated magic numbers/strings that should be constants.

**KISS (Keep It Simple)** — look for unnecessary abstraction layers, over-engineered generic solutions for simple problems, deeply nested conditionals/callbacks.

**YAGNI (You Aren't Gonna Need It)** — speculative generality: unused configuration options, abstract base classes with only one implementation ever, feature flags for features that don't exist yet.

**Centralized error handling** — is there a consistent error-handling strategy (global exception handler/middleware, consistent error types/codes) or is error handling ad hoc (bare `except:`/`catch {}` blocks that swallow errors, inconsistent error shapes across the codebase)?

**Structured logging & telemetry** — is logging structured (JSON logs, log levels used correctly) and is there any observability tooling (APM, tracing, metrics) integrated, vs. scattered `print`/`console.log` debugging statements left in.

**Security posture**
- **Hardcoded secrets**: grep for patterns like `api_key\s*=`, `password\s*=`, `secret\s*=`, AWS key patterns (`AKIA[0-9A-Z]{16}`), connection strings with embedded credentials. This is a critical/blocking finding if found — flag prominently regardless of other scores.
- **Dependency auditing**: is there a lockfile (`package-lock.json`, `poetry.lock`, `Cargo.lock`, etc.)? Any evidence of dependency scanning (Dependabot config, `npm audit` in CI, Snyk config)?
- **Input validation**: is user input validated/sanitized at boundaries (API request validation, SQL parameterization vs string concatenation)?
- **Injection risks**: grep for raw string-concatenated SQL queries, unsanitized `eval()`/`exec()` usage, shell command construction from user input.

## Evaluation checklist (produce pass/fail + note for each)

1. Classes/modules generally follow single-responsibility (no obvious god-classes doing unrelated jobs)
2. Dependency inversion is used where it matters (interfaces/DI over direct concrete instantiation) for cross-layer dependencies
3. No significant code duplication detected (DRY)
4. No excessive/speculative abstraction relative to actual complexity (KISS/YAGNI)
5. Error handling is centralized and consistent, not ad hoc swallowed exceptions
6. Logging is structured and purposeful, not leftover debug prints
7. No hardcoded secrets/credentials found in source (**critical** if failed — flag prominently)
8. Dependencies are locked/pinned and there's some evidence of vulnerability awareness
9. User input is validated at trust boundaries; no obvious injection risk patterns found

## Scoring guidance

- **90-100**: SOLID broadly respected, no duplication/over-engineering, centralized error handling, no security findings
- **80-89**: Good discipline with minor DRY violations or a few ad hoc error-handling spots
- **70-79**: Noticeable SOLID violations or duplication in places, error handling inconsistent
- **60-69**: Several god-classes/duplication, ad hoc error handling throughout, weak dependency locking
- **<60**: Hardcoded secrets found, and/or pervasive duplication/god-classes, and/or injection-risk patterns present — treat any hardcoded secret finding as an automatic ceiling in this range regardless of other strengths
