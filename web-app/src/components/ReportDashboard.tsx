import { useState } from "react";
import type { AnalysisReport, PillarScore } from "../types/analysis";
import {
  Layers,
  GitFork,
  ShieldCheck,
  Cpu,
  CheckCircle2,
  XCircle,
  Download,
  ExternalLink,
  FileText,
} from "lucide-react";

interface ReportDashboardProps {
  report: AnalysisReport;
}

export const ReportDashboard: React.FC<ReportDashboardProps> = ({ report }) => {
  const [activeTab, setActiveTab] = useState<"pillars" | "raw">("pillars");

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
    <div className="mx-auto max-w-5xl my-8 space-y-8">
      {/* Top Level Scorecard Hero - 8-point: p-8 (32px), rounded-[32px], soft-card */}
      <div className="rounded-[32px] soft-card p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-8">
          {/* Repo Info & Grade */}
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-accent/15 px-4 py-1 text-xs font-bold text-accent border border-accent/25">
                Audit Completed
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                Branch: {report.branch} &middot; Commit: {report.commitHash}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-3">
              <span>{report.repoName}</span>
              <a
                href={report.repoUrl}
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="View on GitHub"
              >
                <ExternalLink className="h-5 w-5" strokeWidth={2.1} />
              </a>
            </h1>

            <p className="text-sm font-medium text-foreground">
              Primary Architecture Pattern:{" "}
              <span className="text-primary font-bold">
                {report.primaryArchitecture}
              </span>
            </p>
          </div>

          {/* Overall Grade Card - 8-point: p-6 (24px), gap-6 (24px) */}
          <div className="flex items-center gap-6 rounded-3xl soft-card p-6 shrink-0">
            <div className="text-center">
              <div className="text-4xl font-black text-foreground leading-none">
                {report.grade}
              </div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mt-2">
                Overall Grade
              </div>
            </div>

            <div className="h-12 w-px bg-border" />

            <div className="text-center">
              <div className="text-4xl font-black text-primary leading-none">
                {report.overallScore}
                <span className="text-sm font-medium text-muted-foreground">/100</span>
              </div>
              <div className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider mt-2">
                Health Index
              </div>
            </div>

            <div className="h-12 w-px bg-border hidden sm:block" />

            <button
              onClick={handleDownloadReport}
              className="flex h-12 items-center gap-2 rounded-2xl soft-btn-primary px-6 text-xs font-bold shadow-md cursor-pointer"
              title="Download Markdown Report"
            >
              <Download className="h-4 w-4" strokeWidth={2.2} />
              <span>Export Report</span>
            </button>
          </div>
        </div>

        {/* Executive Summary - 8-point: mt-8 (32px), pt-6 (24px) */}
        <div className="mt-8 pt-6 border-t border-border">
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
            Executive Summary
          </h3>
          <p className="text-sm text-foreground/90 leading-relaxed">
            {report.executiveSummary}
          </p>
        </div>
      </div>

      {/* Navigation Tabs - 8-point: gap-4 (16px), mb-6 (24px) */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => setActiveTab("pillars")}
          className={`flex items-center gap-2 rounded-full px-6 py-3 text-xs font-bold transition-all cursor-pointer ${
            activeTab === "pillars"
              ? "soft-btn-primary"
              : "soft-btn text-muted-foreground hover:text-foreground"
          }`}
        >
          <Layers className="h-4 w-4" strokeWidth={2.1} />
          <span>Evaluation Pillars (Scorecards)</span>
        </button>

        <button
          onClick={() => setActiveTab("raw")}
          className={`flex items-center gap-2 rounded-full px-6 py-3 text-xs font-bold transition-all cursor-pointer ${
            activeTab === "raw"
              ? "soft-btn-primary"
              : "soft-btn text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="h-4 w-4" strokeWidth={2.1} />
          <span>Skill Markdown Output</span>
        </button>
      </div>

      {/* Tab 1: 4 Core Evaluation Pillars - 8-point: gap-6 (24px) */}
      {activeTab === "pillars" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <PillarCard
            title={report.pillars.architecture.title}
            pillar={report.pillars.architecture}
            icon={<Layers className="h-5 w-5 text-primary" strokeWidth={2.1} />}
          />
          <PillarCard
            title={report.pillars.ideology.title}
            pillar={report.pillars.ideology}
            icon={<GitFork className="h-5 w-5 text-accent" strokeWidth={2.1} />}
          />
          <PillarCard
            title={report.pillars.methodology.title}
            pillar={report.pillars.methodology}
            icon={<ShieldCheck className="h-5 w-5 text-primary" strokeWidth={2.1} />}
          />
          <PillarCard
            title={report.pillars.principles.title}
            pillar={report.pillars.principles}
            icon={<Cpu className="h-5 w-5 text-accent" strokeWidth={2.1} />}
          />
        </div>
      )}

      {/* Tab 2: Raw Skill Markdown - 8-point: p-8 (32px), rounded-[32px] */}
      {activeTab === "raw" && (
        <div className="rounded-[32px] soft-card p-8">
          <div className="flex items-center justify-between pb-4 border-b border-border mb-6">
            <span className="text-xs font-mono text-muted-foreground">
              Direct CLI Output strictly conforming to repo-analyzer skill schema
            </span>
            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-1.5 rounded-full soft-btn px-4 py-2 text-xs font-bold text-primary cursor-pointer"
            >
              <Download className="h-3.5 w-3.5" strokeWidth={2.1} />
              <span>Download Raw Markdown</span>
            </button>
          </div>
          <pre className="soft-inset p-6 rounded-2xl font-mono text-xs text-foreground overflow-x-auto whitespace-pre-wrap leading-relaxed">
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
    <div className="rounded-3xl soft-card p-6 flex flex-col justify-between space-y-6">
      <div>
        {/* Header - 8-point: mb-4 (16px) */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl soft-btn">
              {icon}
            </div>
            <h3 className="text-base font-bold text-foreground">{title}</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-extrabold text-foreground">
              {pillar.score}
              <span className="text-xs font-normal text-muted-foreground">/100</span>
            </span>
          </div>
        </div>

        {/* Progress Bar - 8-point: h-2 (8px), rounded-full */}
        <div className="mt-2 h-2 w-full rounded-full bg-secondary/80 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${pillar.score}%` }}
          />
        </div>

        {/* Summary - 8-point: mt-4 (16px) */}
        <p className="mt-4 text-xs text-muted-foreground leading-relaxed">
          {pillar.summary}
        </p>

        {/* Checklist - 8-point: mt-6 (24px), pt-4 (16px), space-y-2 (8px) */}
        <div className="mt-6 space-y-2 border-t border-border pt-4">
          <h4 className="text-[11px] font-bold text-foreground/80 uppercase tracking-wider mb-2">
            Verification Checks
          </h4>
          {pillar.checklist.map((item, i) => (
            <div key={i} className="flex items-start gap-2 text-xs leading-snug">
              {item.passed ? (
                <CheckCircle2 className="h-4 w-4 text-accent shrink-0 mt-0.5" strokeWidth={2.1} />
              ) : (
                <XCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" strokeWidth={2.1} />
              )}
              <span className={item.passed ? "text-foreground" : "text-destructive font-semibold"}>
                {item.label}
                {item.note && (
                  <span className="block text-[11px] text-muted-foreground font-normal mt-0.5">
                    {item.note}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Strengths & Anti-Patterns - 8-point: border-t pt-4 (16px), space-y-4 (16px) */}
      <div className="space-y-4 border-t border-border pt-4">
        {pillar.strengths.length > 0 && (
          <div className="space-y-1">
            <span className="text-[11px] font-bold text-accent uppercase tracking-wider">
              Strong Patterns
            </span>
            <ul className="text-xs text-muted-foreground list-disc list-inside space-y-1">
              {pillar.strengths.map((s, idx) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {pillar.antiPatterns.length > 0 && (
          <div className="space-y-1">
            <span className="text-[11px] font-bold text-destructive uppercase tracking-wider">
              Potential Anti-Patterns
            </span>
            <ul className="text-xs text-muted-foreground list-disc list-inside space-y-1">
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
