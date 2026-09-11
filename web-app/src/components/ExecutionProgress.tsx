import { useEffect, useRef, useState } from "react";
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
} from "lucide-react";

interface ExecutionProgressProps {
  steps: WorkflowStep[];
  logs: TerminalLogEntry[];
  currentStepIndex: number;
  isAnalyzing: boolean;
}

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

  return (
    <div className="mx-auto max-w-5xl my-8 space-y-8">
      {/* 8-Step Lifecycle Stepper Card - 8-point: p-8 (32px), rounded-[32px] */}
      <div className="rounded-[32px] soft-card p-8">
        {/* Header - 8-point: pb-4 (16px), mb-6 (24px) */}
        <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <span>Analysis Execution Pipeline</span>
              <span className="rounded-full bg-secondary/80 px-2 py-1 text-xs font-mono font-bold text-foreground border border-border">
                8 Stages
              </span>
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Deterministic lifecycle orchestrated by Session Sandbox &amp; CLI AI Agent
            </p>
          </div>
          {isAnalyzing && (
            <div className="flex items-center gap-2 text-xs text-accent font-bold soft-btn rounded-full px-4 py-2">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2.1} />
              <span>Stage {currentStepIndex + 1} of 8</span>
            </div>
          )}
        </div>

        {/* Stepper Grid - 8-point: gap-4 (16px) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {steps.map((step) => {
            const isCompleted = step.status === "completed";
            const isRunning = step.status === "running";

            return (
              <div
                key={step.id}
                className={`relative rounded-2xl p-4 text-left transition-all ${
                  isRunning
                    ? "soft-card ring-2 ring-primary bg-primary/5"
                    : isCompleted
                    ? "soft-card bg-surface-white"
                    : "soft-inset opacity-70"
                }`}
              >
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

                <div className="mt-4">
                  <h3 className="text-xs font-bold text-foreground leading-tight">
                    {step.title}
                  </h3>
                  <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2 leading-snug">
                    {step.shortDesc}
                  </p>
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
