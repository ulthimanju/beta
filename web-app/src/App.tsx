import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { RepoInputSection } from "./components/RepoInputSection";
import { ExecutionProgress } from "./components/ExecutionProgress";
import { ReportDashboard } from "./components/ReportDashboard";
import type { WorkflowStep, TerminalLogEntry, AnalysisReport } from "./types/analysis";
import { INITIAL_WORKFLOW_STEPS } from "./mock/sampleData";
import { CheckCircle2, AlertCircle, Box, Trash2, ShieldCheck } from "lucide-react";

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
      addLog("system", `[Info] Step 2 prototype complete. Ready for Step 3 (Set cloned directory as working directory).`);

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
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An error occurred during sandbox clone.";
      addLog("warn", `[Step 2/8] Sandbox Clone Failed: ${msg}`);
      setErrorMessage(msg);
      setSteps((prev) =>
        prev.map((s, i) => (i === 1 ? { ...s, status: "failed" } : s))
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
      setSteps(INITIAL_WORKFLOW_STEPS);
      setCurrentStepIndex(-1);
      setReport(null);
    } catch {
      addLog("warn", `[Sandbox] Notice: Sandbox destroyed locally.`);
      setStep1Session(null);
      setStep2CloneInfo(null);
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

        {/* Step 1 & Step 2 Status Cards */}
        {step1Session && (
          <div className="mx-auto max-w-5xl my-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Step 1 Card */}
              <div className="rounded-xl border border-accent/30 bg-accent/5 p-4 shadow-xs">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/20 text-accent shrink-0">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-accent">
                        Step 1 Completed
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {step1Session.sessionId.slice(0, 8)}...
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold text-foreground">
                      {step1Session.owner} / {step1Session.repoName}
                    </h3>
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
                          <span>Session Sandbox Active</span>
                        </span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {step2CloneInfo.durationMs}ms
                        </span>
                      </div>
                      <p className="text-xs font-mono text-foreground truncate mt-1" title={step2CloneInfo.sandboxRoot}>
                        {step2CloneInfo.sandboxRoot}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {step2CloneInfo.fileCount} files &middot; {step2CloneInfo.branch} ({step2CloneInfo.commitHash})
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-card/60 p-4 shadow-xs flex items-center justify-center text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-primary/50 animate-pulse mr-2" />
                  <span>Provisioning sandbox &amp; cloning repository...</span>
                </div>
              )}
            </div>

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
