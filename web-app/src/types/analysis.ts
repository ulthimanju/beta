export type StepStatus = "idle" | "running" | "completed" | "failed";

export interface WorkflowStep {
  id: number;
  title: string;
  shortDesc: string;
  detail: string;
  status: StepStatus;
  durationMs?: number;
}

export interface TerminalLogEntry {
  timestamp: string;
  level: "info" | "warn" | "error" | "agent" | "system";
  message: string;
}

export interface PillarScore {
  title: string;
  score: number; // 0 - 100
  status: "exceptional" | "good" | "needs-attention" | "critical";
  summary: string;
  strengths: string[];
  antiPatterns: string[];
  checklist: { label: string; passed: boolean; note?: string }[];
}

export interface AnalysisReport {
  repoUrl: string;
  repoName: string;
  analyzedAt: string;
  commitHash: string;
  branch: string;
  primaryLanguage: string;
  overallScore: number;
  grade: string;
  primaryArchitecture: string;
  executiveSummary: string;
  pillars: {
    architecture: PillarScore;
    ideology: PillarScore;
    methodology: PillarScore;
    principles: PillarScore;
  };
  rawMarkdownOutput: string;
}
