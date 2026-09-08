import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { RepoInputSection } from "./components/RepoInputSection";
import { ExecutionProgress } from "./components/ExecutionProgress";
import { ReportDashboard } from "./components/ReportDashboard";
import type { WorkflowStep, TerminalLogEntry, AnalysisReport } from "./types/analysis";
import { INITIAL_WORKFLOW_STEPS, SAMPLE_REPORT } from "./mock/sampleData";

export function App() {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  const [steps, setSteps] = useState<WorkflowStep[]>(INITIAL_WORKFLOW_STEPS);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [logs, setLogs] = useState<TerminalLogEntry[]>([]);
  const [report, setReport] = useState<AnalysisReport | null>(SAMPLE_REPORT);

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

  const handleStartAnalysis = (repoUrl: string) => {
    setIsAnalyzing(true);
    setReport(null);
    setLogs([]);

    const repoSlug = repoUrl.replace("https://github.com/", "");

    // Reset steps
    const freshSteps = INITIAL_WORKFLOW_STEPS.map((s) => ({ ...s, status: "idle" as const }));
    setSteps(freshSteps);

    // Run realistic simulation of the 8 steps
    const stepTimings = [700, 1100, 600, 800, 900, 1000, 1800, 800];

    const runStep = (index: number) => {
      if (index >= 8) {
        setIsAnalyzing(false);
        setCurrentStepIndex(-1);
        addLog("system", "Pipeline completed successfully. Rendering architectural report.");
        setReport({
          ...SAMPLE_REPORT,
          repoUrl,
          repoName: repoSlug.split("/").pop() || "analyzed-repo",
          analyzedAt: "Just now",
        });
        return;
      }

      setCurrentStepIndex(index);

      // Set running status
      setSteps((prev) =>
        prev.map((s, i) => {
          if (i === index) return { ...s, status: "running" };
          if (i < index) return { ...s, status: "completed" };
          return { ...s, status: "idle" };
        })
      );

      // Emit realistic step logs
      switch (index) {
        case 0:
          addLog("info", `[Step 1/8] Received repository target: ${repoUrl}`);
          addLog("info", `[Step 1/8] GitHub URL format verified. Remote head accessible.`);
          break;
        case 1:
          addLog("system", `[Step 2/8] Creating temporary sandbox directory: /tmp/repo-sandbox-${Date.now().toString(36)}`);
          addLog("system", `[Step 2/8] Executing git clone --depth 1 ${repoUrl}...`);
          addLog("info", `[Step 2/8] Clone complete. 142 files indexed, 12.4 MB unpack.`);
          break;
        case 2:
          addLog("system", `[Step 3/8] Process current working directory switched to sandbox root.`);
          addLog("info", `[Step 3/8] Working directory verified: Cwd set successfully.`);
          break;
        case 3:
          addLog("agent", `[Step 4/8] Executing CLI AI agent terminal command from repository root...`);
          addLog("agent", `[Step 4/8] Process spawned. Agent CLI bridge initialized.`);
          break;
        case 4:
          addLog("agent", `[Step 5/8] Dispatching query: "analyze this repo using repo-analyzer skill"`);
          addLog("info", `[Step 5/8] Query delivered to CLI AI agent using default model.`);
          break;
        case 5:
          addLog("agent", `[Step 6/8] CLI AI agent loading skill: 'repo-analyzer'`);
          addLog("agent", `[Step 6/8] Skill loaded: Rubrics for Architecture, Ideology, Methodology & Principles loaded.`);
          break;
        case 6:
          addLog("agent", `[Step 7/8] AI agent actively analyzing codebase tree & source files...`);
          addLog("info", `[Step 7/8] Inspecting directory boundaries and inward dependency directions.`);
          addLog("info", `[Step 7/8] Evaluating Domain-Driven Design aggregates & service layers.`);
          addLog("info", `[Step 7/8] Inspecting testing pyramid and CI workflow definitions.`);
          addLog("info", `[Step 7/8] Validating SOLID principles, DRY violations, and security headers.`);
          break;
        case 7:
          addLog("agent", `[Step 8/8] Synthesizing evaluation output strictly to repo-analyzer specification...`);
          addLog("info", `[Step 8/8] Output verified against schema. Preparing response payload.`);
          break;
      }

      setTimeout(() => {
        setSteps((prev) =>
          prev.map((s, i) => (i === index ? { ...s, status: "completed" } : s))
        );
        runStep(index + 1);
      }, stepTimings[index]);
    };

    runStep(0);
  };

  const handleReset = () => {
    setSteps(INITIAL_WORKFLOW_STEPS);
    setCurrentStepIndex(-1);
    setIsAnalyzing(false);
    setLogs([]);
    setReport(null);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans transition-colors selection:bg-primary/20 selection:text-primary">
      {/* Navigation */}
      <Navbar
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode(!darkMode)}
        onReset={handleReset}
        isAnalyzing={isAnalyzing}
        hasResult={report !== null}
      />

      {/* Main Container */}
      <main className="flex-1 container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
        {/* Repo Input Bar & 4 Pillar Badges */}
        <RepoInputSection
          onStartAnalysis={handleStartAnalysis}
          isAnalyzing={isAnalyzing}
        />

        {/* 8-Step Lifecycle Stepper & CLI Terminal Drawer */}
        <ExecutionProgress
          steps={steps}
          logs={logs}
          currentStepIndex={currentStepIndex}
          isAnalyzing={isAnalyzing}
        />

        {/* Audit Report Presentation */}
        {report && <ReportDashboard report={report} />}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6 text-center text-xs text-muted-foreground">
        <div className="container mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>
            <strong className="font-semibold text-foreground">RepoAnalyzer Prototype</strong> &middot; Automated Codebase &amp; Architecture Audit
          </p>
          <div className="flex items-center gap-4 text-[11px]">
            <span>FastAPI Microservice Bridge</span>
            <span>&middot;</span>
            <span>CLI AI Agent Protocol</span>
            <span>&middot;</span>
            <span>repo-analyzer Skill</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
