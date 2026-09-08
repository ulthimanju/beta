import { useState } from "react";
import { ArrowRight, ShieldCheck, Layers, GitFork, Cpu } from "lucide-react";

interface RepoInputSectionProps {
  onStartAnalysis: (url: string) => void;
  isAnalyzing: boolean;
}

const PRESET_REPOS = [
  {
    name: "fastapi/full-stack-fastapi-template",
    url: "https://github.com/fastapi/full-stack-fastapi-template",
    tag: "Python / Fullstack",
  },
  {
    name: "trpc/trpc",
    url: "https://github.com/trpc/trpc",
    tag: "TypeScript / Monorepo",
  },
  {
    name: "golang-standards/project-layout",
    url: "https://github.com/golang-standards/project-layout",
    tag: "Go / Standards",
  },
];

export const RepoInputSection: React.FC<RepoInputSectionProps> = ({
  onStartAnalysis,
  isAnalyzing,
}) => {
  const [url, setUrl] = useState("https://github.com/fastapi/full-stack-fastapi-template");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim() && !isAnalyzing) {
      onStartAnalysis(url.trim());
    }
  };

  const handleSelectPreset = (presetUrl: string) => {
    setUrl(presetUrl);
    if (!isAnalyzing) {
      onStartAnalysis(presetUrl);
    }
  };

  return (
    <section className="relative pt-8 pb-10">
      <div className="mx-auto max-w-4xl text-center">
        {/* Headline */}
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground shadow-xs mb-4">
          <span className="flex h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
          <span>Open-Access Automated Architecture Review</span>
        </div>

        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl md:text-5xl">
          Deep Codebase &amp; Architecture Audit
        </h1>
        <p className="mt-3 text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto">
          Input any public GitHub repository. Our CLI AI Agent inspects structural boundaries,
          evaluates methodologies, and verifies software principles using the{" "}
          <span className="font-mono text-xs text-foreground bg-muted px-1.5 py-0.5 rounded border border-border">
            repo-analyzer
          </span>{" "}
          skill.
        </p>

        {/* Input Bar Form */}
        <form onSubmit={handleSubmit} className="mt-8 max-w-2xl mx-auto">
          <div className="relative flex items-center rounded-xl border border-border bg-card p-1.5 shadow-sm transition-all focus-within:ring-2 focus-within:ring-primary focus-within:border-primary">
            <div className="flex items-center pl-3 text-muted-foreground">
              <svg className="h-5 w-5 fill-current" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </div>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
              disabled={isAnalyzing}
              className="w-full bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none font-mono"
            />
            <button
              type="submit"
              disabled={isAnalyzing || !url.trim()}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {isAnalyzing ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-primary-foreground border-t-transparent animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <span>Analyze Repo</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>

        {/* Quick Presets */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Try sample repo:</span>
          {PRESET_REPOS.map((preset) => (
            <button
              key={preset.name}
              type="button"
              onClick={() => handleSelectPreset(preset.url)}
              disabled={isAnalyzing}
              className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground hover:bg-muted transition-colors shadow-xs"
            >
              <span className="font-mono">{preset.name}</span>
            </button>
          ))}
        </div>

        {/* 4 Pillars Mini-Badges */}
        <div className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3 text-left">
          <div className="rounded-lg border border-border bg-card p-3 shadow-xs">
            <div className="flex items-center gap-2 text-primary font-medium text-xs mb-1">
              <Layers className="h-3.5 w-3.5" />
              <span>Architecture</span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              Clean, Hexagonal, Modular Monolith &amp; Layer Isolation
            </p>
          </div>

          <div className="rounded-lg border border-border bg-card p-3 shadow-xs">
            <div className="flex items-center gap-2 text-accent font-medium text-xs mb-1">
              <GitFork className="h-3.5 w-3.5" />
              <span>Ideology</span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              Domain-Driven Design (DDD) &amp; Functional vs OOP
            </p>
          </div>

          <div className="rounded-lg border border-border bg-card p-3 shadow-xs">
            <div className="flex items-center gap-2 text-primary font-medium text-xs mb-1">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Methodology</span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              Test Pyramid, CI/CD Readiness &amp; 12-Factor Rules
            </p>
          </div>

          <div className="rounded-lg border border-border bg-card p-3 shadow-xs">
            <div className="flex items-center gap-2 text-accent font-medium text-xs mb-1">
              <Cpu className="h-3.5 w-3.5" />
              <span>Software Principles</span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              SOLID, DRY, KISS, Error Handling &amp; Security Posture
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
