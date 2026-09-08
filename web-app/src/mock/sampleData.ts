import type { AnalysisReport, WorkflowStep } from "../types/analysis";

export const INITIAL_WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: 1,
    title: "Receive Repository URL",
    shortDesc: "Validate URL & parse metadata",
    detail: "User submits GitHub repository URL. Format and schema validated.",
    status: "idle",
  },
  {
    id: 2,
    title: "Clone Repository",
    shortDesc: "Temporary directory clone",
    detail: "Clones repository shallowly (--depth 1) into an isolated sandbox temporary directory.",
    status: "idle",
  },
  {
    id: 3,
    title: "Set Working Directory",
    shortDesc: "Context switch to cloned repo",
    detail: "Configures current process execution context directly inside the cloned codebase directory.",
    status: "idle",
  },
  {
    id: 4,
    title: "Execute CLI AI Agent",
    shortDesc: "Terminal command invocation",
    detail: "Spawns the CLI AI agent process from the repository directory root.",
    status: "idle",
  },
  {
    id: 5,
    title: "Dispatch Query",
    shortDesc: 'Query: "analyze this repo using repo-analyzer skill"',
    detail: 'Sends query to the CLI AI agent using its default configured model.',
    status: "idle",
  },
  {
    id: 6,
    title: "Load Skill",
    shortDesc: "repo-analyzer skill loaded",
    detail: "The AI agent detects, mounts, and applies the repo-analyzer skill rules and schemas.",
    status: "idle",
  },
  {
    id: 7,
    title: "Perform Repository Analysis",
    shortDesc: "Deep architectural audit",
    detail: "Agent traverses AST, evaluates boundaries, ideology, methodology, and software principles.",
    status: "idle",
  },
  {
    id: 8,
    title: "Generate Formatted Output",
    shortDesc: "Skill-compliant synthesis",
    detail: "Produces structured analysis output strictly adhering to repo-analyzer specifications.",
    status: "idle",
  },
];

export const SAMPLE_REPORT: AnalysisReport = {
  repoUrl: "https://github.com/fastapi/full-stack-fastapi-template",
  repoName: "full-stack-fastapi-template",
  analyzedAt: "Just now",
  commitHash: "7b4c91a",
  branch: "master",
  primaryLanguage: "Python / TypeScript",
  overallScore: 89,
  grade: "A",
  primaryArchitecture: "Layered Modular Monolith with Hexagonal Domain Boundaries",
  executiveSummary:
    "The repository demonstrates high architectural maturity. Core domain models remain isolated from database ORM dependencies, API routers follow a RESTful resource hierarchy, and dependency injection is utilized consistently for database sessions and security handlers. Areas for refinement include test mock isolation and reducing tight coupling between domain entities and pydantic transport schemas.",
  pillars: {
    architecture: {
      title: "Application Architecture",
      score: 92,
      status: "exceptional",
      summary:
        "Clean separation between API routing, business domain logic, and data storage infrastructure. Dependency direction flows inwards towards domain models.",
      strengths: [
        "Inward dependency flow: routers depend on services, services on repositories, domain remains agnostic.",
        "Modular directory structure with clear feature isolation in backend/app/api/.",
        "Centralized configuration loading with Pydantic BaseSettings preventing environmental drift.",
      ],
      antiPatterns: [
        "Minor leak: Some API endpoints directly invoke SQLAlchemy queries instead of going through dedicated repository layers.",
      ],
      checklist: [
        { label: "Clear boundary between domain and infrastructure", passed: true },
        { label: "Inward dependency rule enforced", passed: true },
        { label: "Explicit entrypoints and service factories", passed: true },
        { label: "Circular dependency free", passed: true },
      ],
    },
    ideology: {
      title: "Ideology & Paradigms",
      score: 87,
      status: "good",
      summary:
        "Strong adherence to Domain-Driven Design (DDD) aggregate boundaries and declarative data validation. Good balance between functional composition and OOP services.",
      strengths: [
        "Rich domain models with validated invariants rather than anemic data structures.",
        "Consistent declarative schema validation across all request/response boundaries.",
        "Stateless service functions facilitating horizontal scalability.",
      ],
      antiPatterns: [
        "Mixed paradigm: Some business logic is embedded inside Pydantic field validators instead of pure domain services.",
      ],
      checklist: [
        { label: "Domain-Driven Design (DDD) aggregate boundaries", passed: true },
        { label: "Declarative request/response contracts", passed: true },
        { label: "Consistent paradigm conventions across modules", passed: true },
        { label: "Separation of validation vs business logic", passed: false, note: "Pydantic models contain heavy custom validation logic" },
      ],
    },
    methodology: {
      title: "Methodology & Testing",
      score: 85,
      status: "good",
      summary:
        "Solid test suite with Pytest fixtures and Dockerized Postgres test runners. CI/CD pipelines automate linting, type checks, and integration tests.",
      strengths: [
        "Well-structured pytest fixtures providing transactional DB rollbacks for isolated test runs.",
        "GitHub Actions CI pipeline enforces strict type checking and security linting before merge.",
        "Coverage report shows >84% statement coverage across core routes.",
      ],
      antiPatterns: [
        "Heavy reliance on integration tests over unit tests; execution time exceeds 4 minutes due to database spin-up.",
      ],
      checklist: [
        { label: "Automated test suite presence", passed: true },
        { label: "CI/CD automated verification pipeline", passed: true },
        { label: "Balanced Test Pyramid (Unit > Integration > E2E)", passed: false, note: "Inverted pyramid: heavy integration tests" },
        { label: "Mocking external services and side-effects", passed: true },
      ],
    },
    principles: {
      title: "Software Principles (SOLID, DRY)",
      score: 93,
      status: "exceptional",
      summary:
        "High compliance with SOLID principles, particularly Single Responsibility (SRP) and Dependency Inversion (DIP). DRY violations are minimal.",
      strengths: [
        "Single Responsibility: Handlers delegate business validation immediately to specialized service functions.",
        "Dependency Inversion: FastAPI Depends() mechanism used systematically for DB sessions, authentication, and external clients.",
        "Open/Closed Principle respected via pluggable auth providers and extensible middleware hooks.",
      ],
      antiPatterns: [
        "Minor DRY violation: Repetitive pagination and filtering logic across multiple router handlers.",
      ],
      checklist: [
        { label: "Single Responsibility Principle (SRP)", passed: true },
        { label: "Open/Closed Principle (OCP)", passed: true },
        { label: "Liskov Substitution & Interface Segregation", passed: true },
        { label: "Dependency Inversion Principle (DIP)", passed: true },
        { label: "DRY & KISS compliance", passed: true },
      ],
    },
  },
  evidence: [
    {
      path: "backend/app/api/routes/items.py",
      lineRange: "L45-L72",
      observation: "Clean Dependency Injection pattern using Depends(get_db) and explicit HTTP response status schemas.",
      type: "positive",
    },
    {
      path: "backend/app/models.py",
      lineRange: "L120-L145",
      observation: "Direct coupling between SQLModel table definition and client serialization format.",
      type: "warning",
    },
    {
      path: "backend/app/core/config.py",
      lineRange: "L1-L85",
      observation: "Exemplary 12-Factor App environment configuration management using Pydantic Settings.",
      type: "positive",
    },
    {
      path: "backend/app/api/deps.py",
      lineRange: "L30-L55",
      observation: "Reusable security token verification dependency with robust exception handling and early returns.",
      type: "positive",
    },
  ],
  recommendations: [
    {
      id: "REC-01",
      priority: "High",
      title: "Decouple ORM Entities from API Transfer DTOs",
      impact: "Prevents internal database schema leakage and eliminates unintended mass-assignment vulnerabilities.",
      effort: "Low",
      description:
        "Introduce distinct ItemCreate, ItemUpdate, and ItemRead schemas that do not inherit from database model classes directly.",
      affectedPillar: "Architecture",
    },
    {
      id: "REC-02",
      priority: "Medium",
      title: "Extract Generic Pagination Dependency",
      impact: "Reduces code duplication across 6 distinct router modules and standardizes pagination metadata contracts.",
      effort: "Low",
      description:
        "Create a reusable PaginationParams dependency returning skip, limit, and computed next/prev links.",
      affectedPillar: "Principles",
    },
    {
      id: "REC-03",
      priority: "Medium",
      title: "Enhance Pure Domain Unit Test Ratio",
      impact: "Reduces CI feedback time from ~4 minutes to under 30 seconds by mocking database IO for pure business rules.",
      effort: "Medium",
      description:
        "Extract business calculations and access policy checks into pure service functions and test without spawning DB instances.",
      affectedPillar: "Methodology",
    },
  ],
  rawMarkdownOutput: `# Architectural Audit Report: full-stack-fastapi-template
Generated by **repo-analyzer** skill

## Executive Summary
- **Overall Grade**: A (89/100)
- **Primary Architecture**: Layered Modular Monolith
- **Domain Boundaries**: Clean, inwards-facing dependency graph
- **Key Recommendation**: Decouple API schemas from persistent entity models

### Pillar Scorecard
1. **Application Architecture**: 92/100 (Exceptional)
2. **Ideology & Paradigms**: 87/100 (Good)
3. **Methodology & Testing**: 85/100 (Good)
4. **Software Principles**: 93/100 (Exceptional)

### Target Areas for Refactoring
- [High] Separate ItemRead / ItemCreate DTOs from SQLAlchemy models.
- [Medium] Consolidate pagination parameters into a unified dependency.
- [Medium] Increase test speed by adding pure unit tests.
`,
};
