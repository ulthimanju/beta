import { useState } from "react";
import type { AnalysisReport, PillarScore } from "../types/analysis";
import {
  Layers,
  GitFork,
  ShieldCheck,
  Cpu,
  FileCode2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Download,
  ExternalLink,
  FileText,
} from "lucide-react";

interface ReportDashboardProps {
  report: AnalysisReport;
}

export const ReportDashboard: React.FC<ReportDashboardProps> = ({ report }) => {
  const [activeTab, setActiveTab] = useState<"pillars" | "evidence" | "recommendations" | "raw">("pillars");

  const handleDownloadReport = () => {
    const blob = new Blob([report.rawMarkdownOutput], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${report.repoName}-architecture-audit.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="mx-auto max-w-5xl my-8 space-y-6">
      {/* Top Level Scorecard Hero */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          {/* Repo Info & Grade */}
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary border border-primary/20">
                Audit Completed
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                Branch: {report.branch} &middot; Commit: {report.commitHash}
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <span>{report.repoName}</span>
              <a
                href={report.repoUrl}
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="View on GitHub"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </h1>

            <p className="text-sm font-medium text-foreground/90">
              Pattern:{" "}
              <span className="text-primary font-semibold">
                {report.primaryArchitecture}
              </span>
            </p>
          </div>

          {/* Overall Grade Card */}
          <div className="flex items-center gap-4 bg-muted/50 rounded-xl p-4 border border-border shrink-0">
            <div className="text-center">
              <div className="text-3xl font-black text-foreground leading-none">
                {report.grade}
              </div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mt-1">
                Grade
              </div>
            </div>

            <div className="h-10 w-px bg-border" />

            <div className="text-center">
              <div className="text-3xl font-black text-primary leading-none">
                {report.overallScore}
                <span className="text-sm font-medium text-muted-foreground">/100</span>
              </div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mt-1">
                Index
              </div>
            </div>

            <div className="h-10 w-px bg-border hidden sm:block" />

            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground shadow-xs hover:opacity-90 transition-opacity"
              title="Download Markdown Report"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Export Report</span>
            </button>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="mt-6 pt-5 border-t border-border">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Executive Summary
          </h3>
          <p className="text-sm text-foreground/90 leading-relaxed">
            {report.executiveSummary}
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-border gap-2 text-sm">
        <button
          onClick={() => setActiveTab("pillars")}
          className={`flex items-center gap-2 pb-3 px-3 font-medium border-b-2 transition-colors ${
            activeTab === "pillars"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Layers className="h-4 w-4" />
          <span>Evaluation Pillars</span>
        </button>

        <button
          onClick={() => setActiveTab("evidence")}
          className={`flex items-center gap-2 pb-3 px-3 font-medium border-b-2 transition-colors ${
            activeTab === "evidence"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileCode2 className="h-4 w-4" />
          <span>Code Evidence ({report.evidence.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("recommendations")}
          className={`flex items-center gap-2 pb-3 px-3 font-medium border-b-2 transition-colors ${
            activeTab === "recommendations"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Lightbulb className="h-4 w-4" />
          <span>Actionable Roadmap ({report.recommendations.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("raw")}
          className={`flex items-center gap-2 pb-3 px-3 font-medium border-b-2 transition-colors ${
            activeTab === "raw"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>repo-analyzer Output</span>
        </button>
      </div>

      {/* Tab 1: 4 Core Evaluation Pillars */}
      {activeTab === "pillars" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <PillarCard
            title={report.pillars.architecture.title}
            pillar={report.pillars.architecture}
            icon={<Layers className="h-4 w-4 text-primary" />}
          />
          <PillarCard
            title={report.pillars.ideology.title}
            pillar={report.pillars.ideology}
            icon={<GitFork className="h-4 w-4 text-accent" />}
          />
          <PillarCard
            title={report.pillars.methodology.title}
            pillar={report.pillars.methodology}
            icon={<ShieldCheck className="h-4 w-4 text-primary" />}
          />
          <PillarCard
            title={report.pillars.principles.title}
            pillar={report.pillars.principles}
            icon={<Cpu className="h-4 w-4 text-accent" />}
          />
        </div>
      )}

      {/* Tab 2: Code Evidence */}
      {activeTab === "evidence" && (
        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          {report.evidence.map((item, idx) => (
            <div key={idx} className="p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-foreground">
                    {item.path}
                  </span>
                  {item.lineRange && (
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                      {item.lineRange}
                    </span>
                  )}
                </div>
                <p className="text-xs text-foreground/80 leading-relaxed">
                  {item.observation}
                </p>
              </div>

              <div className="shrink-0">
                {item.type === "positive" && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary border border-primary/20">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Conforms</span>
                  </span>
                )}
                {item.type === "warning" && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2.5 py-0.5 text-[11px] font-medium text-destructive border border-destructive/20">
                    <AlertTriangle className="h-3 w-3" />
                    <span>Warning</span>
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Actionable Recommendations */}
      {activeTab === "recommendations" && (
        <div className="space-y-3">
          {report.recommendations.map((rec) => (
            <div
              key={rec.id}
              className="rounded-xl border border-border bg-card p-4 shadow-xs space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                      rec.priority === "High"
                        ? "bg-destructive/15 text-destructive border border-destructive/30"
                        : rec.priority === "Medium"
                        ? "bg-accent/15 text-accent border border-accent/30"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {rec.priority} Priority
                  </span>
                  <span className="font-mono text-xs text-muted-foreground font-semibold">
                    {rec.id}
                  </span>
                  <span className="rounded bg-muted px-2 py-0.5 text-[11px] font-medium text-foreground">
                    {rec.affectedPillar}
                  </span>
                </div>

                <div className="text-xs text-muted-foreground flex items-center gap-2">
                  <span>Effort: <strong className="text-foreground">{rec.effort}</strong></span>
                </div>
              </div>

              <h4 className="text-sm font-semibold text-foreground">
                {rec.title}
              </h4>

              <p className="text-xs text-muted-foreground leading-relaxed">
                {rec.description}
              </p>

              <div className="pt-2 border-t border-border flex items-center gap-1 text-xs text-foreground/90">
                <strong className="text-primary font-medium">Impact:</strong>
                <span>{rec.impact}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 4: Raw Skill Markdown */}
      {activeTab === "raw" && (
        <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
            <span className="text-xs font-mono text-muted-foreground">
              Direct CLI Output strictly conforming to repo-analyzer skill schema
            </span>
            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-1 text-xs text-primary hover:underline font-medium"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download Raw Markdown</span>
            </button>
          </div>
          <pre className="font-mono text-xs text-foreground bg-muted/40 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {report.rawMarkdownOutput}
          </pre>
        </div>
      )}
    </div>
  );
};

interface PillarCardProps {
  title: string;
  pillar: PillarScore;
  icon: React.ReactNode;
}

const PillarCard: React.FC<PillarCardProps> = ({ title, pillar, icon }) => {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-xs flex flex-col justify-between space-y-4">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-foreground">
              {pillar.score}
              <span className="text-xs font-normal text-muted-foreground">/100</span>
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${pillar.score}%` }}
          />
        </div>

        {/* Summary */}
        <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
          {pillar.summary}
        </p>

        {/* Checklist */}
        <div className="mt-3 space-y-1.5 border-t border-border pt-3">
          <h4 className="text-[11px] font-semibold text-foreground/80 uppercase tracking-wider">
            Verification Checks
          </h4>
          {pillar.checklist.map((item, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              {item.passed ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
              ) : (
                <XCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-0.5" />
              )}
              <span className={item.passed ? "text-foreground" : "text-destructive font-medium"}>
                {item.label}
                {item.note && (
                  <span className="block text-[10px] text-muted-foreground font-normal">
                    {item.note}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Strengths & Anti-Patterns */}
      <div className="space-y-2 border-t border-border pt-3">
        {pillar.strengths.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-primary uppercase tracking-wider">
              Strong Patterns
            </span>
            <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
              {pillar.strengths.map((s, idx) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {pillar.antiPatterns.length > 0 && (
          <div className="space-y-1 pt-1">
            <span className="text-[10px] font-bold text-destructive uppercase tracking-wider">
              Potential Anti-Patterns
            </span>
            <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
              {pillar.antiPatterns.map((a, idx) => (
                <li key={idx}>{a}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
