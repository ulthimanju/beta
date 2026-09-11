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
    <section className="relative pt-12 pb-12">
      <div className="mx-auto max-w-4xl text-center">
        {/* Top Tagline Chip - 8-point: mb-6 (24px), px-4 py-2 (16px/8px) */}
        <div className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-muted-foreground soft-btn mb-6">
          <span className="flex h-2 w-2 rounded-full bg-accent animate-pulse shadow-[0_0_8px_rgba(46,204,113,0.8)]" />
          <span>Open-Access Automated Architecture Review</span>
        </div>

        {/* Hero Headline - 8-point: mb-4 (16px) */}
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl mb-4">
          Deep Codebase &amp; Architecture Audit
        </h1>
        {/* Subtitle - 8-point: mb-8 (32px) */}
        <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto mb-8 leading-relaxed">
          Input any public GitHub repository. Our CLI AI Agent inspects structural boundaries,
          evaluates methodologies, and verifies software principles using the{" "}
          <span className="font-mono text-xs font-semibold text-primary bg-secondary/60 px-2 py-1 rounded-md border border-border">
            repo-analyzer
          </span>{" "}
          skill.
        </p>

        {/* Input Bar Form - 8-point: p-2 (8px), gap-2 (8px), h-16 (64px) container */}
        <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
          <div className="relative flex items-center rounded-3xl soft-inset p-2 transition-all focus-within:ring-2 focus-within:ring-primary">
            <div className="flex items-center pl-4 pr-2 text-muted-foreground shrink-0">
              <svg className="h-5 w-5 fill-current" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
            </div>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
              disabled={isAnalyzing}
              className="w-full bg-transparent px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none font-mono"
            />
            {/* Action Button - 8-point: h-12 (48px), px-6 (24px) */}
            <button
              type="submit"
              disabled={isAnalyzing || !url.trim()}
              className="flex h-12 items-center gap-2 rounded-2xl soft-btn-primary px-6 text-sm font-bold shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {isAnalyzing ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <span>Analyze Repo</span>
                  <ArrowRight className="h-4 w-4" strokeWidth={2.2} />
                </>
              )}
            </button>
          </div>
        </form>

        {/* Quick Presets - 8-point: mt-6 (24px), gap-2 (8px) / gap-4 (16px) */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Try sample repo:</span>
          {PRESET_REPOS.map((preset) => (
            <button
              key={preset.name}
              type="button"
              onClick={() => handleSelectPreset(preset.url)}
              disabled={isAnalyzing}
              className="rounded-full soft-btn px-4 py-2 text-xs text-foreground cursor-pointer"
            >
              <span className="font-mono font-medium">{preset.name}</span>
            </button>
          ))}
        </div>

        {/* 4 Pillars Grid - 8-point: mt-12 (48px), gap-6 (24px), p-6 (24px) */}
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
          {/* Pillar 1 */}
          <div className="rounded-3xl soft-card p-6 flex flex-col justify-between">
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary soft-btn mb-4">
                <Layers className="h-5 w-5" strokeWidth={2.1} />
              </div>
              <h3 className="font-bold text-foreground text-sm mb-2">Architecture</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Clean, Hexagonal, Modular Monolith &amp; Layer Isolation
              </p>
            </div>
          </div>

          {/* Pillar 2 */}
          <div className="rounded-3xl soft-card p-6 flex flex-col justify-between">
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent/15 text-accent soft-btn mb-4">
                <GitFork className="h-5 w-5" strokeWidth={2.1} />
              </div>
              <h3 className="font-bold text-foreground text-sm mb-2">Ideology</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Domain-Driven Design (DDD) &amp; Functional vs OOP Paradigm
              </p>
            </div>
          </div>

          {/* Pillar 3 */}
          <div className="rounded-3xl soft-card p-6 flex flex-col justify-between">
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary soft-btn mb-4">
                <ShieldCheck className="h-5 w-5" strokeWidth={2.1} />
              </div>
              <h3 className="font-bold text-foreground text-sm mb-2">Methodology</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Test Pyramid, CI/CD Automation &amp; 12-Factor Verification
              </p>
            </div>
          </div>

          {/* Pillar 4 */}
          <div className="rounded-3xl soft-card p-6 flex flex-col justify-between">
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent/15 text-accent soft-btn mb-4">
                <Cpu className="h-5 w-5" strokeWidth={2.1} />
              </div>
              <h3 className="font-bold text-foreground text-sm mb-2">Software Principles</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                SOLID, DRY, KISS, Error Handling &amp; Security Posture
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
