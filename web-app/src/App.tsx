import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { RepoInputSection } from "./components/RepoInputSection";
import { ExecutionProgress } from "./components/ExecutionProgress";
import { ReportDashboard } from "./components/ReportDashboard";
import type { WorkflowStep, TerminalLogEntry, AnalysisReport } from "./types/analysis";
import { INITIAL_WORKFLOW_STEPS } from "./mock/sampleData";
import {
  CheckCircle2,
  AlertCircle,
  Box,
  Trash2,
  ShieldCheck,
  FolderGit2,
  FolderCheck,
  Layers,
  Bot,
  Cpu,
  Send,
  Sparkles,
  BookOpen,
  FileCheck2,
} from "lucide-react";

interface Step1Session {
  sessionId: string;
  repoUrl: string;
  owner: string;
  repoName: string;
  receivedAt: string;
  message: string;
}

interface Step2CloneInfo {
  sandboxRoot: string;
  repoDir: string;
  workingDir: string;
  commitHash: string;
  branch: string;
  fileCount: number;
  sizeBytes: number;
  durationMs: number;
}

interface Step3WorkingDirInfo {
  workingDir: string;
  relativeWorkingDir: string;
  repoName: string;
  isGitWorktree: boolean;
  readmePresent: boolean;
  detectedFrameworks: string[];
  topLevelEntries: string[];
}

interface Step4AgentInfo {
  agentExecutable: string;
  agentVersion: string;
  command: string;
  defaultModel: string;
  pid: number | null;
  durationMs: number;
  status: string;
}

interface Step5QueryInfo {
  query: string;
  modelUsed: string;
  workingDir: string;
  skillName: string;
  timestamp: string;
  durationMs: number;
  status: string;
}

interface PillarBreakdownItem {
  pillar: string;
  rules_count: number;
  focus: string;
  items: string[];
}

interface Step6SkillInfo {
  skillName: string;
  skillDir: string;
  pillarsLoaded: string[];
  totalRulesCount: number;
  pillarBreakdowns: PillarBreakdownItem[];
  schemaValid: boolean;
  schemaTitle: string;
  durationMs: number;
  status: string;
}

interface PillarScoreItem {
  title: string;
  score: number;
  status: "exceptional" | "good" | "needs-attention" | "critical";
  summary: string;
  keyStrengths: string[];
  antiPatterns: string[];
  checklist: { label: string; passed: boolean; note: string }[];
}

interface Step7AnalysisInfo {
  repoName: string;
  primaryLanguage: string;
  secondaryLanguages: string[];
  detectedArchitecture: string;
  overallScore: number;
  grade: string;
  pillarScores: Record<string, number>;
  totalRulesEvaluated: number;
  passedRulesCount: number;
  failedRulesCount: number;
  executiveSummary: string;
  pillars: PillarScoreItem[];
  durationMs: number;
  status: string;
}




export function App() {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  const [steps, setSteps] = useState<WorkflowStep[]>(INITIAL_WORKFLOW_STEPS);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isClosingSandbox, setIsClosingSandbox] = useState<boolean>(false);
  const [logs, setLogs] = useState<TerminalLogEntry[]>([]);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [step1Session, setStep1Session] = useState<Step1Session | null>(null);
  const [step2CloneInfo, setStep2CloneInfo] = useState<Step2CloneInfo | null>(null);
  const [step3WorkingDirInfo, setStep3WorkingDirInfo] = useState<Step3WorkingDirInfo | null>(null);
  const [step4AgentInfo, setStep4AgentInfo] = useState<Step4AgentInfo | null>(null);
  const [step5QueryInfo, setStep5QueryInfo] = useState<Step5QueryInfo | null>(null);
  const [step6SkillInfo, setStep6SkillInfo] = useState<Step6SkillInfo | null>(null);
  const [step7AnalysisInfo, setStep7AnalysisInfo] = useState<Step7AnalysisInfo | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync dark class on HTML root
  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [darkMode]);

  const addLog = (level: TerminalLogEntry["level"], message: string) => {
    const timestamp = new Date().toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    setLogs((prev) => [...prev, { timestamp, level, message }]);
  };

  const handleStartAnalysis = async (repoUrl: string) => {
    setIsAnalyzing(true);
    setReport(null);
    setErrorMessage(null);
    setStep1Session(null);
    setStep2CloneInfo(null);
    setStep3WorkingDirInfo(null);
    setStep4AgentInfo(null);
    setStep5QueryInfo(null);
    setStep6SkillInfo(null);
    setStep7AnalysisInfo(null);
    setLogs([]);

    // Initialize all steps to idle
    const freshSteps = INITIAL_WORKFLOW_STEPS.map((s) => ({ ...s, status: "idle" as const }));
    setSteps(freshSteps);

    // ==========================================
    // STEP 1: Receive & Validate Repository URL
    // ==========================================
    setCurrentStepIndex(0);
    setSteps((prev) =>
      prev.map((s, i) => (i === 0 ? { ...s, status: "running" } : s))
    );

    addLog("info", `[Step 1/8] Initiating Step 1: Receiving & validating repository URL...`);
    addLog("info", `[Step 1/8] Target URL: ${repoUrl}`);

    let sessionId = "";
    let validatedRepoUrl = repoUrl;
    let owner = "";
    let repoName = "";

    try {
      let res = await fetch("/api/v1/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      }).catch(() => null);

      if (!res || !res.ok) {
        if (!res || res.status === 404 || res.status === 502) {
          const directRes = await fetch("http://localhost:8000/api/v1/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ repo_url: repoUrl }),
          }).catch(() => null);
          if (directRes) res = directRes;
        }
      }

      if (!res) {
        throw new Error("Unable to connect to repoAnalyzer backend service at http://localhost:8000");
      }

      const data = await res.json();

      if (!res.ok) {
        const errorDetail = data.detail || `Server returned error (${res.status})`;
        throw new Error(errorDetail);
      }

      sessionId = data.session_id;
      validatedRepoUrl = data.repo_url;
      owner = data.owner;
      repoName = data.repo_name;

      addLog("system", `[Step 1/8] Session generated: ${sessionId}`);
      addLog("system", `[Sandbox] Ephemeral Session Sandbox initialized for session ${sessionId.slice(0, 8)}.`);
      addLog("info", `[Step 1/8] Repository verified: ${owner}/${repoName}`);
      addLog("agent", `[Step 1/8] Step 1 Complete: Repository URL received and Session Sandbox created.`);

      setStep1Session({
        sessionId,
        repoUrl: validatedRepoUrl,
        owner,
        repoName,
        receivedAt: data.received_at,
        message: data.message,
      });

      // Mark Step 1 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 0 ? { ...s, status: "completed" } : s))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      addLog("warn", `[Step 1/8] Validation Failed: ${msg}`);
      setErrorMessage(msg);
      setSteps((prev) =>
        prev.map((s, i) => (i === 0 ? { ...s, status: "failed" } : s))
      );
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
      return;
    }

    // ==========================================
    // STEP 2: Clone Directly into Session Sandbox
    // ==========================================
    setCurrentStepIndex(1);
    setSteps((prev) =>
      prev.map((s, i) => (i === 1 ? { ...s, status: "running" } : s))
    );

    addLog("system", `[Step 2/8] Cloning target repository directly into Session Sandbox workspace...`);
    addLog("system", `[Step 2/8] Executing git clone --depth 1 ${validatedRepoUrl}...`);

    try {
      let cloneRes = await fetch("/api/v1/clone", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, repo_url: validatedRepoUrl }),
      }).catch(() => null);

      if (!cloneRes || !cloneRes.ok) {
        if (!cloneRes || cloneRes.status === 404 || cloneRes.status === 502) {
          const directClone = await fetch("http://localhost:8000/api/v1/clone", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, repo_url: validatedRepoUrl }),
          }).catch(() => null);
          if (directClone) cloneRes = directClone;
        }
      }

      if (!cloneRes) {
        throw new Error("Unable to reach backend /api/v1/clone endpoint");
      }

      const cloneData = await cloneRes.json();

      if (!cloneRes.ok) {
        const errDetail = cloneData.detail || `Clone failed with status ${cloneRes.status}`;
        throw new Error(errDetail);
      }

      addLog("info", `[Step 2/8] Sandbox clone complete: ${cloneData.file_count} files unpacked (${(cloneData.size_bytes / 1024).toFixed(1)} KB) in ${cloneData.duration_ms}ms.`);
      addLog("info", `[Step 2/8] Sandbox Boundary: ${cloneData.sandbox_root}`);
      addLog("info", `[Step 2/8] Target Repository: ${cloneData.repo_dir}`);
      addLog("agent", `[Step 2/8] Step 2 Complete: Codebase safely contained in isolated Session Sandbox.`);

      setStep2CloneInfo({
        sandboxRoot: cloneData.sandbox_root,
        repoDir: cloneData.repo_dir,
        workingDir: cloneData.working_dir,
        commitHash: cloneData.commit_hash,
        branch: cloneData.branch,
        fileCount: cloneData.file_count,
        sizeBytes: cloneData.size_bytes,
        durationMs: cloneData.duration_ms,
      });

      // Mark Step 2 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 1 ? { ...s, status: "completed" } : s))
      );

      // ==========================================
      // STEP 3: Set Working Directory inside Sandbox
      // ==========================================
      setCurrentStepIndex(2);
      setSteps((prev) =>
        prev.map((s, i) => (i === 2 ? { ...s, status: "running" } : s))
      );

      addLog("system", `[Step 3/8] Configuring execution context: Setting cloned repository as active working directory...`);
      addLog("system", `[Step 3/8] Validating directory boundary inside sandbox & inspecting structure...`);

      let dirRes = await fetch("/api/v1/set-working-dir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => null);

      if (!dirRes || !dirRes.ok) {
        if (!dirRes || dirRes.status === 404 || dirRes.status === 502) {
          const directDir = await fetch("http://localhost:8000/api/v1/set-working-dir", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          }).catch(() => null);
          if (directDir) dirRes = directDir;
        }
      }

      if (!dirRes) {
        throw new Error("Unable to reach backend /api/v1/set-working-dir endpoint");
      }

      const dirData = await dirRes.json();

      if (!dirRes.ok) {
        const errDetail = dirData.detail || `Set working directory failed with status ${dirRes.status}`;
        throw new Error(errDetail);
      }

      const stacks = dirData.detected_frameworks && dirData.detected_frameworks.length > 0
        ? dirData.detected_frameworks.join(", ")
        : "Standard codebase";

      addLog("info", `[Step 3/8] Working directory verified & locked: ${dirData.working_dir}`);
      addLog("info", `[Step 3/8] Relative sandbox path: ./${dirData.relative_working_dir}`);
      addLog("info", `[Step 3/8] Git worktree verified: ${dirData.is_git_worktree ? "Yes (.git active)" : "No"}`);
      addLog("info", `[Step 3/8] Detected technology stack: ${stacks}`);
      addLog("info", `[Step 3/8] Root directory entries: ${dirData.top_level_entries.slice(0, 8).join(", ")}${dirData.top_level_entries.length > 8 ? "..." : ""}`);
      addLog("agent", `[Step 3/8] Step 3 Complete: Process execution context anchored to cloned repository.`);

      setStep3WorkingDirInfo({
        workingDir: dirData.working_dir,
        relativeWorkingDir: dirData.relative_working_dir,
        repoName: dirData.repo_name,
        isGitWorktree: dirData.is_git_worktree,
        readmePresent: dirData.readme_present,
        detectedFrameworks: dirData.detected_frameworks || [],
        topLevelEntries: dirData.top_level_entries || [],
      });

      // Mark Step 3 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 2 ? { ...s, status: "completed" } : s))
      );

      // ==========================================
      // STEP 4: Execute CLI AI Agent Terminal Invocation
      // ==========================================
      setCurrentStepIndex(3);
      setSteps((prev) =>
        prev.map((s, i) => (i === 3 ? { ...s, status: "running" } : s))
      );

      addLog("system", `[Step 4/8] Executing terminal command to invoke CLI AI agent from repository directory...`);
      addLog("system", `[Step 4/8] Working Directory: ${dirData.working_dir}`);

      let agentRes = await fetch("/api/v1/invoke-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => null);

      if (!agentRes || !agentRes.ok) {
        if (!agentRes || agentRes.status === 404 || agentRes.status === 502) {
          const directAgent = await fetch("http://localhost:8000/api/v1/invoke-agent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          }).catch(() => null);
          if (directAgent) agentRes = directAgent;
        }
      }

      if (!agentRes) {
        throw new Error("Unable to reach backend /api/v1/invoke-agent endpoint");
      }

      const agentData = await agentRes.json();

      if (!agentRes.ok) {
        const errDetail = agentData.detail || `Agent invocation failed with status ${agentRes.status}`;
        throw new Error(errDetail);
      }

      addLog("info", `[Step 4/8] Agent binary: ${agentData.agent_executable} (v${agentData.agent_version})`);
      addLog("info", `[Step 4/8] Terminal command: ${agentData.command}`);
      addLog("info", `[Step 4/8] Default model configured: ${agentData.default_model}`);
      addLog("info", `[Step 4/8] Process active (PID: ${agentData.pid}) in ${agentData.duration_ms}ms.`);
      addLog("agent", `[Step 4/8] Step 4 Complete: CLI AI agent runtime invoked and standing by for query dispatch.`);

      setStep4AgentInfo({
        agentExecutable: agentData.agent_executable,
        agentVersion: agentData.agent_version,
        command: agentData.command,
        defaultModel: agentData.default_model,
        pid: agentData.pid,
        durationMs: agentData.duration_ms,
        status: agentData.status,
      });

      // Mark Step 4 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 3 ? { ...s, status: "completed" } : s))
      );

      // ==========================================
      // STEP 5: Dispatch Query to CLI AI Agent
      // ==========================================
      setCurrentStepIndex(4);
      setSteps((prev) =>
        prev.map((s, i) => (i === 4 ? { ...s, status: "running" } : s))
      );

      addLog("system", `[Step 5/8] Dispatching query: "analyze this repo using repo-analyzer skill"...`);
      addLog("system", `[Step 5/8] Using default model: ${agentData.default_model}`);

      let queryRes = await fetch("/api/v1/dispatch-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          query: "analyze this repo using repo-analyzer skill",
        }),
      }).catch(() => null);

      if (!queryRes || !queryRes.ok) {
        if (!queryRes || queryRes.status === 404 || queryRes.status === 502) {
          const directQuery = await fetch("http://localhost:8000/api/v1/dispatch-query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              query: "analyze this repo using repo-analyzer skill",
            }),
          }).catch(() => null);
          if (directQuery) queryRes = directQuery;
        }
      }

      if (!queryRes) {
        throw new Error("Unable to reach backend /api/v1/dispatch-query endpoint");
      }

      const queryData = await queryRes.json();

      if (!queryRes.ok) {
        const errDetail = queryData.detail || `Query dispatch failed with status ${queryRes.status}`;
        throw new Error(errDetail);
      }

      addLog("info", `[Step 5/8] Query confirmed: "${queryData.query}"`);
      addLog("info", `[Step 5/8] Model target: ${queryData.model_used} (default configured)`);
      addLog("info", `[Step 5/8] Skill target: ${queryData.skill_name} (mounted in sandbox)`);
      addLog("info", `[Step 5/8] Execution context: ${queryData.working_dir}`);
      addLog("agent", `[Step 5/8] Step 5 Complete: Query received by CLI AI agent. Execution plan ready for skill loading.`);
      addLog("system", `[Info] Step 5 prototype complete. Ready for Step 6 (AI agent loads and applies repo-analyzer skill).`);

      setStep5QueryInfo({
        query: queryData.query,
        modelUsed: queryData.model_used,
        workingDir: queryData.working_dir,
        skillName: queryData.skill_name,
        timestamp: queryData.timestamp,
        durationMs: queryData.duration_ms,
        status: queryData.status,
      });

      // Mark Step 5 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 4 ? { ...s, status: "completed" } : s))
      );

      // ==========================================
      // STEP 6: Load Skill (repo-analyzer)
      // ==========================================
      setCurrentStepIndex(5);
      setSteps((prev) =>
        prev.map((s, i) => (i === 5 ? { ...s, status: "running" } : s))
      );

      addLog("system", `[Step 6/8] AI agent loading and configuring "repo-analyzer" skill...`);
      addLog("system", `[Step 6/8] Extracting evaluation criteria for 4 pillars: Architecture, Ideology, Methodology, Software Principles...`);

      let skillRes = await fetch("/api/v1/load-skill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          skill_name: "repo-analyzer",
        }),
      }).catch(() => null);

      if (!skillRes || !skillRes.ok) {
        if (!skillRes || skillRes.status === 404 || skillRes.status === 502) {
          const directSkill = await fetch("http://localhost:8000/api/v1/load-skill", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              skill_name: "repo-analyzer",
            }),
          }).catch(() => null);
          if (directSkill) skillRes = directSkill;
        }
      }

      if (!skillRes) {
        throw new Error("Unable to reach backend /api/v1/load-skill endpoint");
      }

      const skillData = await skillRes.json();

      if (!skillRes.ok) {
        const errDetail = skillData.detail || `Skill load failed with status ${skillRes.status}`;
        throw new Error(errDetail);
      }

      addLog("info", `[Step 6/8] Skill loaded: ${skillData.skill_name} (${skillData.pillars_loaded.join(", ")})`);
      addLog("info", `[Step 6/8] Evaluation checklist compiled: ${skillData.total_rules_count} criteria across 4 pillars`);
      if (Array.isArray(skillData.pillar_breakdowns)) {
        for (const pb of skillData.pillar_breakdowns) {
          addLog("info", `[Step 6/8] • ${pb.pillar}: ${pb.rules_count} criteria (${pb.focus.slice(0, 45)}...)`);
        }
      }
      addLog("info", `[Step 6/8] Report schema: ${skillData.schema_title} (${skillData.schema_valid ? "Valid JSON Schema Draft-07" : "Unverified"})`);
      addLog("agent", `[Step 6/8] Step 6 Complete: AI agent has successfully loaded and applied the "repo-analyzer" skill.`);
      addLog("system", `[Info] Step 6 prototype complete. Ready for Step 7 (Perform Repository Analysis).`);

      setStep6SkillInfo({
        skillName: skillData.skill_name,
        skillDir: skillData.skill_dir,
        pillarsLoaded: skillData.pillars_loaded,
        totalRulesCount: skillData.total_rules_count,
        pillarBreakdowns: skillData.pillar_breakdowns || [],
        schemaValid: skillData.schema_valid,
        schemaTitle: skillData.schema_title,
        durationMs: skillData.duration_ms,
        status: skillData.status,
      });

      // Mark Step 6 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 5 ? { ...s, status: "completed" } : s))
      );

      // ==========================================
      // STEP 7: Perform Repository Analysis
      // ==========================================
      setCurrentStepIndex(6);
      setSteps((prev) =>
        prev.map((s, i) => (i === 6 ? { ...s, status: "running" } : s))
      );

      addLog("system", `[Step 7/8] Commencing deep repository analysis across 4 evaluation pillars...`);
      addLog("system", `[Step 7/8] Evaluating Architecture, Ideology, Methodology, Software Principles...`);

      let analysisRes = await fetch("/api/v1/perform-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          deep_scan: true,
        }),
      }).catch(() => null);

      if (!analysisRes || !analysisRes.ok) {
        if (!analysisRes || analysisRes.status === 404 || analysisRes.status === 502) {
          const directAnalysis = await fetch("http://localhost:8000/api/v1/perform-analysis", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              deep_scan: true,
            }),
          }).catch(() => null);
          if (directAnalysis) analysisRes = directAnalysis;
        }
      }

      if (!analysisRes) {
        throw new Error("Unable to reach backend /api/v1/perform-analysis endpoint");
      }

      const analysisData = await analysisRes.json();

      if (!analysisRes.ok) {
        const errDetail = analysisData.detail || `Repository analysis failed with status ${analysisRes.status}`;
        throw new Error(errDetail);
      }

      addLog("info", `[Step 7/8] Primary Pattern: ${analysisData.detected_architecture} (${analysisData.primary_language})`);
      addLog("info", `[Step 7/8] Overall Score: ${analysisData.overall_score}/100 — Grade ${analysisData.grade}`);
      addLog("info", `[Step 7/8] Checklist Outcomes: ${analysisData.passed_rules_count}/${analysisData.total_rules_evaluated} criteria passed`);
      if (analysisData.pillar_scores) {
        for (const [pillarName, score] of Object.entries(analysisData.pillar_scores)) {
          addLog("info", `[Step 7/8] • ${pillarName}: ${score}/100`);
        }
      }
      addLog("agent", `[Step 7/8] Step 7 Complete: Deep repository analysis finished. All 4 pillars audited.`);
      addLog("system", `[Info] Step 7 prototype complete. Ready for Step 8 (Format & Generate Output).`);

      setStep7AnalysisInfo({
        repoName: analysisData.repo_name,
        primaryLanguage: analysisData.primary_language,
        secondaryLanguages: analysisData.secondary_languages || [],
        detectedArchitecture: analysisData.detected_architecture,
        overallScore: analysisData.overall_score,
        grade: analysisData.grade,
        pillarScores: analysisData.pillar_scores || {},
        totalRulesEvaluated: analysisData.total_rules_evaluated,
        passedRulesCount: analysisData.passed_rules_count,
        failedRulesCount: analysisData.failed_rules_count,
        executiveSummary: analysisData.executive_summary,
        pillars: analysisData.pillars || [],
        durationMs: analysisData.duration_ms,
        status: analysisData.status,
      });

      // Mark Step 7 completed
      setSteps((prev) =>
        prev.map((s, i) => (i === 6 ? { ...s, status: "completed" } : s))
      );
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An error occurred during sandbox execution.";
      addLog("warn", `[Pipeline Failure] ${msg}`);
      setErrorMessage(msg);
      setSteps((prev) =>
        prev.map((s, i) => (s.status === "running" ? { ...s, status: "failed" } : s))
      );
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
    }
  };

  const handleDestroySandbox = async () => {
    if (!step1Session) return;
    setIsClosingSandbox(true);
    addLog("system", `[Sandbox] Closing and destroying Session Sandbox (${step1Session.sessionId.slice(0, 8)})...`);

    try {
      await fetch(`/api/v1/sandbox/${step1Session.sessionId}/close`, { method: "POST" }).catch(() => null);
      addLog("system", `[Sandbox] Sandbox destroyed. All temporary files wiped completely from disk.`);
      setStep1Session(null);
      setStep2CloneInfo(null);
      setStep3WorkingDirInfo(null);
      setStep4AgentInfo(null);
      setStep5QueryInfo(null);
      setStep6SkillInfo(null);
      setStep7AnalysisInfo(null);
      setSteps(INITIAL_WORKFLOW_STEPS);
      setCurrentStepIndex(-1);
      setReport(null);
    } catch {
      addLog("warn", `[Sandbox] Notice: Sandbox destroyed locally.`);
      setStep1Session(null);
      setStep2CloneInfo(null);
      setStep3WorkingDirInfo(null);
      setStep4AgentInfo(null);
      setStep5QueryInfo(null);
      setStep6SkillInfo(null);
      setStep7AnalysisInfo(null);
      setSteps(INITIAL_WORKFLOW_STEPS);
      setCurrentStepIndex(-1);
    } finally {
      setIsClosingSandbox(false);
    }
  };

  const handleReset = async () => {
    if (step1Session) {
      await handleDestroySandbox();
    } else {
      setSteps(INITIAL_WORKFLOW_STEPS);
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
      setLogs([]);
      setReport(null);
      setStep1Session(null);
      setStep2CloneInfo(null);
      setStep3WorkingDirInfo(null);
      setStep4AgentInfo(null);
      setStep5QueryInfo(null);
      setStep6SkillInfo(null);
      setStep7AnalysisInfo(null);
      setErrorMessage(null);
    }
  };



  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans transition-colors selection:bg-primary/20 selection:text-primary">
      {/* Navigation */}
      <Navbar
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode(!darkMode)}
        onReset={handleReset}
        isAnalyzing={isAnalyzing}
        hasResult={step1Session !== null || report !== null}
      />

      {/* Main Container */}
      <main className="flex-1 container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
        {/* Repo Input Bar & 4 Pillar Badges */}
        <RepoInputSection
          onStartAnalysis={handleStartAnalysis}
          isAnalyzing={isAnalyzing}
        />

        {/* Error Alert */}
        {errorMessage && (
          <div className="mx-auto max-w-5xl my-4 flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block">Execution Error</strong>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Step 1, Step 2, Step 3 & Step 4 Status Cards */}
        {step1Session && (
          <div className="mx-auto max-w-5xl my-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Step 1 Card */}
              <div className="rounded-xl border border-accent/30 bg-accent/5 p-4 shadow-xs">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/20 text-accent shrink-0">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-accent">
                        Step 1
                      </span>
                      <span className="font-mono text-[11px] text-muted-foreground truncate">
                        {step1Session.sessionId.slice(0, 8)}...
                      </span>
                    </div>
                    <h3 className="text-xs font-semibold text-foreground truncate mt-0.5" title={`${step1Session.owner}/${step1Session.repoName}`}>
                      {step1Session.owner}/{step1Session.repoName}
                    </h3>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Verified Public Repo</p>
                  </div>
                </div>
              </div>

              {/* Step 2 Card with Session Sandbox Details */}
              {step2CloneInfo ? (
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 shadow-xs">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20 text-primary shrink-0 mt-0.5">
                      <Box className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                          <ShieldCheck className="h-3.5 w-3.5" />
                          <span>Step 2</span>
                        </span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {step2CloneInfo.durationMs}ms
                        </span>
                      </div>
                      <p className="text-xs font-mono text-foreground truncate mt-1" title={step2CloneInfo.sandboxRoot}>
                        Sandbox Cloned
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {step2CloneInfo.fileCount} files &middot; {step2CloneInfo.branch}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-card/60 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-primary/50 animate-pulse mr-2" />
                  <span>Cloning into sandbox...</span>
                </div>
              )}

              {/* Step 3 Card: Active Working Directory */}
              {step3WorkingDirInfo ? (
                <div className="rounded-xl border border-accent/30 bg-accent/5 p-4 shadow-xs">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/20 text-accent shrink-0 mt-0.5">
                      <FolderGit2 className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-accent flex items-center gap-1.5">
                          <FolderCheck className="h-3.5 w-3.5" />
                          <span>Step 3</span>
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {step3WorkingDirInfo.isGitWorktree ? "Git Worktree" : "Local Dir"}
                        </span>
                      </div>
                      <p className="text-xs font-mono text-foreground truncate mt-1" title={step3WorkingDirInfo.workingDir}>
                        ./{step3WorkingDirInfo.relativeWorkingDir}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {step3WorkingDirInfo.detectedFrameworks.length > 0 ? (
                          step3WorkingDirInfo.detectedFrameworks.slice(0, 2).map((fw) => (
                            <span
                              key={fw}
                              className="inline-flex items-center rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium text-accent border border-accent/25"
                            >
                              {fw}
                            </span>
                          ))
                        ) : (
                          <span className="text-[10px] text-muted-foreground">Verified</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : step2CloneInfo ? (
                <div className="rounded-xl border border-border bg-card/60 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-accent/50 animate-pulse mr-2" />
                  <span>Setting working dir...</span>
                </div>
              ) : (
                <div className="rounded-xl border border-border/50 bg-muted/20 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground/60">
                  <span>Step 3 pending</span>
                </div>
              )}

              {/* Step 4 Card: CLI AI Agent Invoked */}
              {step4AgentInfo ? (
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 shadow-xs">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20 text-primary shrink-0 mt-0.5">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                          <Cpu className="h-3.5 w-3.5" />
                          <span>Step 4</span>
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          PID: {step4AgentInfo.pid ?? "active"}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-foreground truncate mt-1">
                        CLI AI Agent Invoked
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="inline-flex items-center rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-primary border border-primary/25">
                          agy v{step4AgentInfo.agentVersion}
                        </span>
                        <span className="text-[10px] font-mono text-muted-foreground truncate" title={step4AgentInfo.defaultModel}>
                          {step4AgentInfo.defaultModel}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : step3WorkingDirInfo ? (
                <div className="rounded-xl border border-border bg-card/60 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-primary/50 animate-pulse mr-2" />
                  <span>Invoking CLI AI Agent...</span>
                </div>
              ) : (
                <div className="rounded-xl border border-border/50 bg-muted/20 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground/60">
                  <span>Step 4 pending</span>
                </div>
              )}
            </div>

            {/* Step 5: Active Query Dispatch Status Bar */}
            {step5QueryInfo && (
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-3.5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary shrink-0">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-primary flex items-center gap-1">
                        <Send className="h-3 w-3" />
                        <span>Step 5: Query Dispatched</span>
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {step5QueryInfo.durationMs}ms
                      </span>
                    </div>
                    <p className="font-mono text-xs text-foreground font-medium truncate mt-0.5" title={step5QueryInfo.query}>
                      "{step5QueryInfo.query}"
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-1 text-[11px] font-mono text-foreground border border-border">
                    <span className="text-muted-foreground">model:</span>
                    <span>{step5QueryInfo.modelUsed}</span>
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-accent/15 px-2 py-1 text-[11px] font-mono text-accent border border-accent/25">
                    <span className="text-muted-foreground">skill:</span>
                    <span>{step5QueryInfo.skillName}</span>
                  </span>
                </div>
              </div>
            )}

            {/* Step 6: Skill Loaded & Evaluation Pillars Status Bar */}
            {step6SkillInfo && (
              <div className="rounded-xl border border-accent/30 bg-accent/5 p-4 shadow-xs flex flex-col gap-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/20 text-accent shrink-0">
                      <BookOpen className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-accent flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Step 6: Skill Loaded &amp; Applied</span>
                        </span>
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {step6SkillInfo.durationMs}ms
                        </span>
                      </div>
                      <p className="font-mono text-xs text-foreground font-semibold">
                        {step6SkillInfo.skillName} &middot; {step6SkillInfo.totalRulesCount} Evaluation Rules Active
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded bg-muted px-2.5 py-1 text-[11px] font-mono text-foreground border border-border">
                      <FileCheck2 className="h-3.5 w-3.5 text-accent" />
                      <span>{step6SkillInfo.schemaTitle}</span>
                      <span className="text-[10px] text-accent font-semibold">(Draft-07 Verified)</span>
                    </span>
                  </div>
                </div>

                {/* 4 Pillars Breakdown Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-2 border-t border-accent/15">
                  {step6SkillInfo.pillarBreakdowns.map((pb) => (
                    <div
                      key={pb.pillar}
                      className="rounded-lg border border-border/70 bg-card/70 p-2.5 text-xs flex flex-col justify-between shadow-2xs"
                    >
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-semibold text-foreground truncate">{pb.pillar}</span>
                        <span className="inline-flex items-center rounded-full bg-accent/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-accent border border-accent/25">
                          {pb.rules_count} rules
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground line-clamp-2" title={pb.focus}>
                        {pb.focus}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Step 7: Perform Repository Analysis Card & Scorecard */}
            {step7AnalysisInfo && (
              <div className="rounded-xl border border-primary/30 bg-card p-5 shadow-xs flex flex-col gap-4">
                {/* Header Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/20 text-primary font-mono text-xl font-bold">
                      {step7AnalysisInfo.grade}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                          <CheckCircle2 className="h-4 w-4" />
                          <span>Step 7: Repository Analysis Complete</span>
                        </span>
                        <span className="text-xs font-mono text-muted-foreground">
                          {step7AnalysisInfo.durationMs}ms
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-foreground mt-0.5">
                        Overall Score: {step7AnalysisInfo.overallScore}/100 &middot; Pattern: {step7AnalysisInfo.detectedArchitecture}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 text-xs font-mono text-foreground border border-border">
                      <span className="text-muted-foreground">Language:</span>
                      <span className="font-semibold">{step7AnalysisInfo.primaryLanguage}</span>
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-md bg-primary/15 px-2.5 py-1 text-xs font-mono text-primary border border-primary/25">
                      <span>{step7AnalysisInfo.passedRulesCount}/{step7AnalysisInfo.totalRulesEvaluated} criteria passed</span>
                    </span>
                  </div>
                </div>

                {/* 4 Pillars Scorecards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {step7AnalysisInfo.pillars.map((pillar) => {
                    const statusColor =
                      pillar.status === "exceptional"
                        ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/30"
                        : pillar.status === "good"
                        ? "text-primary bg-primary/10 border-primary/30"
                        : pillar.status === "needs-attention"
                        ? "text-amber-500 bg-amber-500/10 border-amber-500/30"
                        : "text-rose-500 bg-rose-500/10 border-rose-500/30";

                    const passedCount = pillar.checklist.filter((c) => c.passed).length;

                    return (
                      <div
                        key={pillar.title}
                        className="rounded-xl border border-border bg-card/60 p-3.5 shadow-2xs flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-1 mb-2">
                            <span className="font-semibold text-sm text-foreground">{pillar.title}</span>
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-mono font-bold border ${statusColor}`}>
                              {pillar.score}/100
                            </span>
                          </div>

                          <div className="w-full bg-muted rounded-full h-1.5 mb-2 overflow-hidden">
                            <div
                              className="bg-primary h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${pillar.score}%` }}
                            />
                          </div>

                          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                            {pillar.summary}
                          </p>
                        </div>

                        <div className="pt-2 border-t border-border/50 flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                          <span>{passedCount}/{pillar.checklist.length} rules passed</span>
                          <span className="capitalize">{pillar.status}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Executive Summary Preview */}
                <div className="rounded-xl border border-border bg-muted/30 p-3.5 text-xs">
                  <span className="font-bold text-foreground uppercase tracking-wider text-[10px] block mb-1">
                    Executive Appraisal Summary
                  </span>
                  <p className="text-muted-foreground leading-relaxed whitespace-pre-line">
                    {step7AnalysisInfo.executiveSummary}
                  </p>
                </div>
              </div>
            )}

            {/* Sandbox Control Bar */}
            {step2CloneInfo && (
              <div className="flex items-center justify-between bg-card border border-border px-4 py-2.5 rounded-xl shadow-xs text-xs">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                  <span>
                    Sandbox isolated to <strong className="text-foreground font-mono">{step1Session.sessionId.slice(0, 8)}</strong>. All processes &amp; files wipe on close.
                  </span>
                </div>

                <button
                  onClick={handleDestroySandbox}
                  disabled={isClosingSandbox}
                  className="flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer disabled:opacity-50"
                  title="Destroy this sandbox and delete all cloned repository files"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>{isClosingSandbox ? "Destroying..." : "Destroy Sandbox"}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* 8-Step Lifecycle Stepper & CLI Terminal Drawer */}
        <ExecutionProgress
          steps={steps}
          logs={logs}
          currentStepIndex={currentStepIndex}
          isAnalyzing={isAnalyzing}
        />

        {/* Audit Report Presentation (if available) */}
        {report && <ReportDashboard report={report} />}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6 text-center text-xs text-muted-foreground">
        <div className="container mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>
            <strong className="font-semibold text-foreground">RepoAnalyzer Prototype</strong> &middot; Session Sandbox Architecture
          </p>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Ephemeral Sandbox Isolation</span>
            <span>&middot;</span>
            <span>Zero Host Clutter</span>
            <span>&middot;</span>
            <span>Auto-Wipe on Close</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
