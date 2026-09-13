import { useEffect, useRef, useState, useMemo } from "react";
import type { WorkflowStep, TerminalLogEntry } from "../types/analysis";
import {
  CheckCircle2,
  Circle,
  Loader2,
  Terminal,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Timer,
  Clock,
  Zap,
} from "lucide-react";

interface ExecutionProgressProps {
  steps: WorkflowStep[];
  logs: TerminalLogEntry[];
  currentStepIndex: number;
  isAnalyzing: boolean;
}

/**
 * Format milliseconds into human-readable duration
 * < 1000ms: 420ms
 * < 60s: 14.24s
 * >= 60s: 1m 24.3s
 */
export function formatDuration(ms: number | undefined | null): string {
  if (ms === undefined || ms === null) return "--";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = ((ms % 60000) / 1000).toFixed(1);
  return `${mins}m ${secs}s`;
}

/**
 * Live / Final Time Calculator component for an individual step
 */
interface StepTimeCalculatorProps {
  step: WorkflowStep;
  totalPipelineMs: number;
}

const StepTimeCalculator: React.FC<StepTimeCalculatorProps> = ({ step, totalPipelineMs }) => {
  const [elapsedMs, setElapsedMs] = useState<number>(() => {
    if (step.durationMs !== undefined) return step.durationMs;
    if (step.status === "running" && step.startTime) return Math.max(0, Date.now() - step.startTime);
    return 0;
  });

  useEffect(() => {
    if (step.status !== "running" || !step.startTime) {
      if (step.durationMs !== undefined) {
        setElapsedMs(step.durationMs);
      }
      return;
    }

    const start = step.startTime;
    const interval = setInterval(() => {
      setElapsedMs(Date.now() - start);
    }, 60);

    return () => clearInterval(interval);
  }, [step.status, step.startTime, step.durationMs]);

  if (step.status === "idle") {
    return (
      <div className="flex items-center gap-1 text-[11px] font-mono text-muted-foreground/60">
        <Timer className="h-3 w-3 text-muted-foreground/40" strokeWidth={2.1} />
        <span>--</span>
      </div>
    );
  }

  if (step.status === "running") {
    return (
      <div className="flex items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-1 text-[11px] font-mono font-bold text-accent border border-accent/25 animate-pulse shadow-[0_0_8px_rgba(46,204,113,0.3)]">
        <Timer className="h-3.5 w-3.5 animate-spin" strokeWidth={2.2} />
        <span>{formatDuration(elapsedMs)}</span>
      </div>
    );
  }

  if (step.status === "failed") {
    return (
      <div className="flex items-center gap-1.5 rounded-full bg-destructive/15 px-2.5 py-1 text-[11px] font-mono font-bold text-destructive border border-destructive/25">
        <Timer className="h-3.5 w-3.5" strokeWidth={2.1} />
        <span>{formatDuration(step.durationMs ?? elapsedMs)}</span>
      </div>
    );
  }

  // Completed State
  const duration = step.durationMs ?? elapsedMs;
  const percentage =
    totalPipelineMs > 0 && duration > 0 ? Math.round((duration / totalPipelineMs) * 100) : null;

  return (
    <div className="flex items-center gap-1.5 rounded-full soft-btn px-2.5 py-1 text-[11px] font-mono font-bold text-primary">
      <Timer className="h-3.5 w-3.5 text-primary" strokeWidth={2.1} />
      <span>{formatDuration(duration)}</span>
      {percentage !== null && percentage > 0 && (
        <span className="text-[10px] font-medium text-muted-foreground">({percentage}%)</span>
      )}
    </div>
  );
};

export const ExecutionProgress: React.FC<ExecutionProgressProps> = ({
  steps,
  logs,
  currentStepIndex,
  isAnalyzing,
}) => {
  const [showTerminal, setShowTerminal] = useState(true);
  const [copied, setCopied] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (showTerminal && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, showTerminal]);

  const handleCopyLogs = () => {
    const raw = logs.map((l) => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`).join("\n");
    navigator.clipboard.writeText(raw);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Calculate total completed duration across steps
  const completedDurationMs = useMemo(() => {
    return steps
      .filter((s) => s.status === "completed" && s.durationMs !== undefined)
      .reduce((acc, s) => acc + (s.durationMs || 0), 0);
  }, [steps]);

  // Total Live Duration (Completed + current active step timer)
  const [liveTotalMs, setLiveTotalMs] = useState(completedDurationMs);

  useEffect(() => {
    if (!isAnalyzing) {
      setLiveTotalMs(completedDurationMs);
      return;
    }

    const interval = setInterval(() => {
      const runningStep = steps.find((s) => s.status === "running");
      const runningElapsed =
        runningStep && runningStep.startTime ? Date.now() - runningStep.startTime : 0;
      setLiveTotalMs(completedDurationMs + runningElapsed);
    }, 60);

    return () => clearInterval(interval);
  }, [isAnalyzing, completedDurationMs, steps]);

  const completedStepsCount = steps.filter((s) => s.status === "completed").length;

  return (
    <div className="mx-auto max-w-5xl my-8 space-y-8">
      {/* 8-Step Lifecycle Stepper Card - 8-point: p-8 (32px), rounded-[32px] */}
      <div className="rounded-[32px] soft-card p-8">
        {/* Header with Global Time Calculator - 8-point: pb-6 (24px), mb-6 (24px) */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-foreground">Analysis Execution Pipeline</h2>
              <span className="rounded-full bg-secondary/80 px-2 py-1 text-xs font-mono font-bold text-foreground border border-border">
                8 Stages
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Deterministic lifecycle orchestrated by Session Sandbox &amp; CLI AI Agent
            </p>
          </div>

          {/* Real-Time Total Pipeline Duration Calculator Widget */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Total Pipeline Time Badge */}
            <div className="flex items-center gap-2 rounded-full soft-btn px-4 py-2 text-xs font-mono font-bold text-foreground shadow-sm">
              <Clock className="h-4 w-4 text-primary" strokeWidth={2.1} />
              <span className="text-muted-foreground font-sans font-medium">Pipeline Time:</span>
              <span className="text-primary">{formatDuration(liveTotalMs)}</span>
            </div>

            {/* Stages Counter / Active Stage */}
            {isAnalyzing ? (
              <div className="flex items-center gap-2 text-xs text-accent font-bold soft-btn rounded-full px-4 py-2">
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2.1} />
                <span>Stage {currentStepIndex + 1} of 8</span>
              </div>
            ) : completedStepsCount === 8 ? (
              <div className="flex items-center gap-1.5 rounded-full bg-accent/15 px-3 py-1.5 text-xs font-bold text-accent border border-accent/25">
                <CheckCircle2 className="h-4 w-4" strokeWidth={2.1} />
                <span>All 8 Completed ({formatDuration(liveTotalMs)})</span>
              </div>
            ) : null}
          </div>
        </div>

        {/* Visual Timing Distribution Progress Bar (Active when stages complete) */}
        {liveTotalMs > 0 && (
          <div className="mb-6 space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
              <span className="flex items-center gap-1.5 font-medium">
                <Zap className="h-3.5 w-3.5 text-primary" strokeWidth={2.1} />
                <span>Stage Timing Distribution Calculator</span>
              </span>
              <span>
                {completedStepsCount}/8 Stages Finished &middot; Total: {formatDuration(liveTotalMs)}
              </span>
            </div>
            {/* Segmented Time Bar */}
            <div className="flex h-2.5 w-full rounded-full bg-secondary/60 overflow-hidden soft-inset p-0.5">
              {steps.map((step) => {
                const duration =
                  step.status === "completed"
                    ? step.durationMs || 0
                    : step.status === "running" && step.startTime
                    ? Date.now() - step.startTime
                    : 0;

                const widthPct = liveTotalMs > 0 ? (duration / liveTotalMs) * 100 : 0;
                if (widthPct <= 0) return null;

                const stepColors = [
                  "bg-accent",
                  "bg-primary",
                  "bg-amber-500",
                  "bg-emerald-500",
                  "bg-cyan-500",
                  "bg-indigo-500",
                  "bg-rose-500",
                  "bg-orange-500",
                ];

                return (
                  <div
                    key={step.id}
                    style={{ width: `${widthPct}%` }}
                    className={`h-full ${stepColors[(step.id - 1) % stepColors.length]} transition-all duration-300 first:rounded-l-full last:rounded-r-full`}
                    title={`Step ${step.id}: ${step.title} - ${formatDuration(duration)} (${Math.round(widthPct)}%)`}
                  />
                );
              })}
            </div>
          </div>
        )}

        {/* Stepper Grid - 8-point: gap-4 (16px) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {steps.map((step) => {
            const isCompleted = step.status === "completed";
            const isRunning = step.status === "running";

            return (
              <div
                key={step.id}
                className={`relative rounded-2xl p-4 text-left transition-all flex flex-col justify-between ${
                  isRunning
                    ? "soft-card ring-2 ring-primary bg-primary/5 shadow-md"
                    : isCompleted
                    ? "soft-card bg-surface-white"
                    : "soft-inset opacity-70"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    {/* Step ID Pill - 8-point: h-6 w-6 (24px) */}
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                        isCompleted
                          ? "bg-primary text-white"
                          : isRunning
                          ? "bg-accent text-white animate-pulse"
                          : "bg-muted-foreground/20 text-muted-foreground"
                      }`}
                    >
                      {step.id}
                    </span>

                    <div>
                      {isCompleted ? (
                        <CheckCircle2 className="h-5 w-5 text-accent" strokeWidth={2.1} />
                      ) : isRunning ? (
                        <Loader2 className="h-5 w-5 text-primary animate-spin" strokeWidth={2.1} />
                      ) : (
                        <Circle className="h-5 w-5 text-muted-foreground/30" strokeWidth={2.1} />
                      )}
                    </div>
                  </div>

                  <div className="mt-3">
                    <h3 className="text-xs font-bold text-foreground leading-tight">
                      {step.title}
                    </h3>
                    <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2 leading-snug">
                      {step.shortDesc}
                    </p>
                  </div>
                </div>

                {/* Individual Step Time Calculator Badge - 8-point: mt-4 (16px) */}
                <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                    Duration
                  </span>
                  <StepTimeCalculator step={step} totalPipelineMs={liveTotalMs} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* CLI Agent Terminal Output Viewer - 8-point: rounded-[32px] */}
      <div className="rounded-[32px] soft-card overflow-hidden">
        {/* Terminal Header - 8-point: px-6 (24px), py-4 (16px) */}
        <div className="flex items-center justify-between glass-header px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl soft-btn text-primary">
              <Terminal className="h-4 w-4" strokeWidth={2.1} />
            </div>
            <div>
              <span className="font-mono text-xs font-bold text-foreground block">
                CLI AI Agent Execution Stream
              </span>
              <span className="font-mono text-[10px] text-muted-foreground hidden sm:block">
                command: agy --prompt "analyze this repo using repo-analyzer skill"
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyLogs}
              className="flex items-center gap-1.5 rounded-full soft-btn px-4 py-2 text-xs font-semibold text-foreground cursor-pointer"
              title="Copy terminal logs"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-accent" strokeWidth={2.1} />
              ) : (
                <Copy className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={2.1} />
              )}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
            <button
              onClick={() => setShowTerminal(!showTerminal)}
              className="flex items-center gap-1.5 rounded-full soft-btn px-4 py-2 text-xs font-semibold text-foreground cursor-pointer"
              title={showTerminal ? "Collapse terminal" : "Expand terminal"}
            >
              {showTerminal ? (
                <ChevronUp className="h-3.5 w-3.5" strokeWidth={2.1} />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" strokeWidth={2.1} />
              )}
              <span>{showTerminal ? "Collapse" : "Expand"}</span>
            </button>
          </div>
        </div>

        {/* Terminal Body - 8-point: p-6 (24px) */}
        {showTerminal && (
          <div className="soft-inset m-4 rounded-2xl p-6 font-mono text-xs max-h-80 overflow-y-auto space-y-2 select-text">
            {logs.length === 0 ? (
              <div className="text-muted-foreground italic py-4 text-center">
                Waiting for pipeline initiation...
              </div>
            ) : (
              logs.map((log, index) => {
                let badgeClass = "text-muted-foreground";
                if (log.level === "agent") badgeClass = "text-accent font-bold";
                if (log.level === "system") badgeClass = "text-primary font-bold";
                if (log.level === "warn") badgeClass = "text-destructive font-bold";

                return (
                  <div key={index} className="flex items-start gap-3 leading-relaxed">
                    <span className="text-muted-foreground/60 select-none text-[10px] shrink-0 font-mono">
                      {log.timestamp}
                    </span>
                    <span className={`text-[10px] uppercase ${badgeClass} shrink-0 font-mono`}>
                      [{log.level}]
                    </span>
                    <span className="text-foreground/90 whitespace-pre-wrap">{log.message}</span>
                  </div>
                );
              })
            )}
            <div ref={terminalEndRef} />
          </div>
        )}
      </div>
    </div>
  );
};
