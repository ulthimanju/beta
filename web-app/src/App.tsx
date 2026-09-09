import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { RepoInputSection } from "./components/RepoInputSection";
import { ExecutionProgress } from "./components/ExecutionProgress";
import { ReportDashboard } from "./components/ReportDashboard";
import type { WorkflowStep, TerminalLogEntry, AnalysisReport } from "./types/analysis";
import { INITIAL_WORKFLOW_STEPS } from "./mock/sampleData";
import { CheckCircle2, AlertCircle } from "lucide-react";

interface Step1Session {
  sessionId: string;
  repoUrl: string;
  owner: string;
  repoName: string;
  receivedAt: string;
  message: string;
}

export function App() {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  const [steps, setSteps] = useState<WorkflowStep[]>(INITIAL_WORKFLOW_STEPS);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [logs, setLogs] = useState<TerminalLogEntry[]>([]);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [step1Session, setStep1Session] = useState<Step1Session | null>(null);
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
    setLogs([]);

    // Initialize all steps to idle
    const freshSteps = INITIAL_WORKFLOW_STEPS.map((s) => ({ ...s, status: "idle" as const }));
    setSteps(freshSteps);

    // Set Step 1 to running
    setCurrentStepIndex(0);
    setSteps((prev) =>
      prev.map((s, i) => (i === 0 ? { ...s, status: "running" } : s))
    );

    addLog("info", `[Step 1/8] Initiating Step 1: Receiving & validating repository URL...`);
    addLog("info", `[Step 1/8] Target URL: ${repoUrl}`);

    try {
      // Call backend API endpoint for Step 1
      let res = await fetch("/api/v1/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      }).catch(() => null);

      // Fallback directly to localhost:8000 if proxy fails
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

      // Step 1 Success
      addLog("system", `[Step 1/8] Session generated: ${data.session_id}`);
      addLog("info", `[Step 1/8] Repository verified: ${data.owner}/${data.repo_name}`);
      addLog("agent", `[Step 1/8] Step 1 Complete: Repository URL received and verified.`);
      addLog("system", `[Info] Step 1 prototype complete. Ready for Step 2 (Clone repository into temporary directory).`);

      setStep1Session({
        sessionId: data.session_id,
        repoUrl: data.repo_url,
        owner: data.owner,
        repoName: data.repo_name,
        receivedAt: data.received_at,
        message: data.message,
      });

      // Mark Step 1 as completed, remaining steps stay idle
      setSteps((prev) =>
        prev.map((s, i) => (i === 0 ? { ...s, status: "completed" } : s))
      );
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      addLog("warn", `[Step 1/8] Validation Failed: ${msg}`);
      setErrorMessage(msg);
      setSteps((prev) =>
        prev.map((s, i) => (i === 0 ? { ...s, status: "failed" } : s))
      );
      setCurrentStepIndex(-1);
      setIsAnalyzing(false);
    }
  };

  const handleReset = () => {
    setSteps(INITIAL_WORKFLOW_STEPS);
    setCurrentStepIndex(-1);
    setIsAnalyzing(false);
    setLogs([]);
    setReport(null);
    setStep1Session(null);
    setErrorMessage(null);
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
              <strong className="font-semibold block">Step 1 Error</strong>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Step 1 Completion Card */}
        {step1Session && (
          <div className="mx-auto max-w-5xl my-4 rounded-xl border border-accent/30 bg-accent/5 p-4 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/20 text-accent">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-accent">
                      Step 1 Completed
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">
                      Session: {step1Session.sessionId.slice(0, 8)}...
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">
                    {step1Session.owner} / {step1Session.repoName}
                  </h3>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono bg-card px-3 py-1.5 rounded-lg border border-border shrink-0">
                <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                <span>Ready for Step 2: Clone to temp directory</span>
              </div>
            </div>
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
            <strong className="font-semibold text-foreground">RepoAnalyzer Prototype</strong> &middot; Step-by-Step Architecture Pipeline
          </p>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Step 1/8 Live</span>
            <span>&middot;</span>
            <span>FastAPI Backend Connected</span>
            <span>&middot;</span>
            <span>Pydantic URL Validator</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
