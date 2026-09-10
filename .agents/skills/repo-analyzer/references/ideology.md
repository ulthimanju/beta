# Pillar 2: Ideology

Focus: Domain-Driven Design (entities, value objects, aggregates), Event-Driven Architecture, Functional vs OOP adherence, Contract-First design, strong type safety.

## What to look for

**Domain-Driven Design (DDD)** — is there evidence of:
- **Entities**: objects with identity/lifecycle distinct from their attribute values (e.g. `User` with an `id` that persists across attribute changes)
- **Value Objects**: immutable objects compared by value, not identity (e.g. `Money`, `Address`, `EmailAddress` as dedicated types rather than raw primitives)
- **Aggregates**: a root entity that owns and enforces invariants across a cluster of related objects, with all external access going through the root
- **Anemic domain model anti-pattern**: entities that are just data bags (getters/setters, no behavior) with all logic living in separate "service" classes — this is a common DDD violation worth flagging explicitly if present
- **Ubiquitous language**: does the code's naming match domain terminology a business stakeholder would recognize, or is it generic/technical (`DataManager`, `Helper`, `Processor`)?

**Event-Driven Architecture (EDA)** — presence of event emitters/listeners, message queues (Kafka, RabbitMQ, SQS, etc.), event sourcing patterns, pub/sub. If present, check whether events are well-named (past-tense domain facts like `OrderPlaced`) vs. vague (`UpdateEvent`).

**Functional vs OOP adherence** — identify which paradigm the codebase is committing to, and whether it's applied consistently:
- If OOP: proper encapsulation, appropriate use of inheritance vs composition, avoidance of deep inheritance chains
- If Functional: immutability discipline, pure functions where possible, explicit handling of side effects (not scattered ad hoc)
- **Paradigm mixing** isn't automatically bad, but inconsistent/accidental mixing (e.g. mutating shared state inside supposedly pure functions) is a real anti-pattern worth flagging

**Contract-First design** — are API contracts (OpenAPI/Swagger specs, GraphQL schemas, Protobuf definitions, tRPC types) defined and treated as source of truth, or is the contract implicit/inferred from route handlers only?

**Strong type safety** — for typed languages, how strict is the configuration (`strict: true` in `tsconfig.json`, mypy strictness settings, etc.)? For dynamically typed languages, is there compensating discipline (type hints, runtime validation via schemas like Zod/Pydantic)?

## Evaluation checklist (produce pass/fail + note for each)

1. Domain concepts are modeled as explicit types (entities/value objects), not primitives-only ("primitive obsession")
2. Domain entities carry behavior, not just data (no pervasive anemic domain model)
3. Naming reflects ubiquitous/domain language, not generic technical terms
4. If EDA is used, events are well-named domain facts and flow is traceable
5. A single paradigm (functional or OOP) is chosen and applied consistently where it matters
6. If OOP, composition is favored over deep/fragile inheritance chains
7. If contracts exist (API/schema), they're treated as source of truth rather than inferred from implementation
8. Type safety is enforced meaningfully (strict typing config, or runtime validation compensating for dynamic typing)

## Scoring guidance

- **90-100**: Rich domain model, consistent paradigm, contracts-first, strong typing enforced
- **80-89**: Solid domain modeling with minor primitive obsession or occasional anemic classes
- **70-79**: Domain concepts present but thin; some paradigm inconsistency
- **60-69**: Mostly anemic model, generic naming throughout, weak/absent typing discipline
- **<60**: No domain modeling evidence, pure CRUD-over-database with no ideology, untyped/unchecked throughout
