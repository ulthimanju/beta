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
    <div className="mx-auto max-w-5xl my-6 space-y-6">
      {/* 8-Step Lifecycle Stepper Card */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
          <div>
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              <span>Analysis Execution Pipeline</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground font-mono">
                8 Stages
              </span>
            </h2>
            <p className="text-xs text-muted-foreground">
              Lifecycle orchestrated by microservice &amp; CLI AI Agent
            </p>
          </div>
          {isAnalyzing && (
            <div className="flex items-center gap-2 text-xs text-accent font-medium">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Step {currentStepIndex + 1} of 8</span>
            </div>
          )}
        </div>

        {/* Responsive Stepper Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {steps.map((step) => {
            const isCompleted = step.status === "completed";
            const isRunning = step.status === "running";

            return (
              <div
                key={step.id}
                className={`relative rounded-lg border p-3 text-left transition-all ${
                  isRunning
                    ? "border-primary bg-primary/5 shadow-xs ring-1 ring-primary/40"
                    : isCompleted
                    ? "border-border bg-card text-foreground"
                    : "border-border/60 bg-muted/40 opacity-70"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                      isCompleted
                        ? "bg-primary text-primary-foreground"
                        : isRunning
                        ? "bg-accent text-accent-foreground animate-pulse"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {step.id}
                  </span>

                  <div>
                    {isCompleted ? (
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    ) : isRunning ? (
                      <Loader2 className="h-4 w-4 text-accent animate-spin" />
                    ) : (
                      <Circle className="h-4 w-4 text-muted-foreground/40" />
                    )}
                  </div>
                </div>

                <div className="mt-2">
                  <h3 className="text-xs font-semibold text-foreground leading-tight">
                    {step.title}
                  </h3>
                  <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2">
                    {step.shortDesc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* CLI Agent Terminal Output Viewer */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* Terminal Header */}
        <div className="flex items-center justify-between bg-muted/60 px-4 py-2.5 border-b border-border">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            <span className="font-mono text-xs font-medium text-foreground">
              CLI AI Agent Execution Stream
            </span>
            <span className="rounded bg-background px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground border border-border">
              query: "analyze this repo using repo-analyzer skill"
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyLogs}
              className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              title="Copy terminal logs"
            >
              {copied ? <Check className="h-3 w-3 text-accent" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
            <button
              onClick={() => setShowTerminal(!showTerminal)}
              className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              title={showTerminal ? "Collapse terminal" : "Expand terminal"}
            >
              {showTerminal ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              <span>{showTerminal ? "Collapse" : "Expand"}</span>
            </button>
          </div>
        </div>

        {/* Terminal Body */}
        {showTerminal && (
          <div className="bg-background/95 p-4 font-mono text-xs max-h-64 overflow-y-auto space-y-1 select-text">
            {logs.length === 0 ? (
              <div className="text-muted-foreground italic py-2">
                Waiting for pipeline initiation...
              </div>
            ) : (
              logs.map((log, index) => {
                let badgeClass = "text-muted-foreground";
                if (log.level === "agent") badgeClass = "text-accent font-semibold";
                if (log.level === "system") badgeClass = "text-primary font-semibold";
                if (log.level === "warn") badgeClass = "text-destructive font-semibold";

                return (
                  <div key={index} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-muted-foreground/60 select-none text-[10px]">
                      {log.timestamp}
                    </span>
                    <span className={`text-[10px] uppercase ${badgeClass} shrink-0`}>
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
