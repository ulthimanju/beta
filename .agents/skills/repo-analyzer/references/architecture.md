# Pillar 1: Architecture

Focus: Clean / Hexagonal / Ports & Adapters / Modular Monolith patterns, layer isolation, package structure, circular dependencies, domain boundary leaks.

## What to look for

**Pattern detection** — determine which architectural pattern (if any) the repo is attempting:
- **Layered / N-tier**: `controllers/`, `services/`, `repositories/`, `models/` at top level
- **Clean / Onion**: concentric dependency rule — domain has zero outward dependencies, infrastructure depends inward
- **Hexagonal / Ports & Adapters**: explicit `ports/` and `adapters/` folders, or interfaces defined in domain and implemented at the edges
- **Modular Monolith**: feature-based top-level folders (e.g. `billing/`, `users/`, `inventory/`) each with their own internal layers, avoiding cross-module reach-through
- **Microservices** (if repo is one service among many, or a monorepo of services): check service boundary clarity, shared-code leakage between services
- **No discernible pattern / "big ball of mud"**: flag explicitly if none of the above fit

**Layer isolation** — does business/domain logic leak into controllers or infrastructure code? Does infrastructure code (DB clients, HTTP clients) get imported directly into domain logic instead of through an abstraction?

**Circular dependencies** — trace import graphs, especially between top-level modules. Use `grep -r "^import\|^from\|require(" ` or language-appropriate equivalents to spot suspicious back-and-forth imports between modules that should be one-directional.

**Domain boundary leaks** — do unrelated modules reach into each other's internals (e.g. `billing` directly querying `users`' database tables/ORM models instead of going through an interface/service)?

**Package/folder cohesion** — are files grouped by technical role (`controllers/`, `models/` — "horizontal" slicing) or by business capability ("vertical" slicing)? Neither is automatically wrong, but note which one the repo uses and whether it's applied consistently.

**God objects / god modules** — any single file or module doing dramatically more than its peers (check file line counts: `find . -name "*.ext" | xargs wc -l | sort -rn | head`).

## Evaluation checklist (produce pass/fail + note for each)

1. A discernible, consistently-applied architecture pattern is present
2. Domain/business logic is isolated from framework and infrastructure code
3. Dependencies point inward (domain has no outward deps) or the pattern's dependency rule is otherwise respected
4. No circular dependencies detected between top-level modules
5. No cross-module boundary leaks (modules don't reach into each other's internals)
6. Folder/package structure is cohesive and consistently applied across the codebase
7. No god objects/modules (single files doing disproportionate work relative to codebase norms)
8. Entrypoint(s) wire dependencies cleanly (no business logic embedded directly in bootstrap/main files)

## Scoring guidance

- **90-100**: Clear pattern, consistently applied, clean dependency direction, no circular deps or leaks found
- **80-89**: Clear pattern mostly followed, 1-2 minor leaks or inconsistencies
- **70-79**: Pattern is present but drifting — some layers bypassed, occasional boundary leak
- **60-69**: Weak or inconsistent pattern, several boundary leaks, at least one circular dependency
- **<60**: No discernible architecture, pervasive coupling, domain logic scattered across layers
