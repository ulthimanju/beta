import { useState, useEffect, useCallback } from "react";
import { Terminal, Sun, Moon, RefreshCw, Activity } from "lucide-react";

interface NavbarProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onReset: () => void;
  isAnalyzing: boolean;
  hasResult: boolean;
}

interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  debug: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  darkMode,
  onToggleDarkMode,
  onReset,
  isAnalyzing,
  hasResult,
}) => {
  const [healthStatus, setHealthStatus] = useState<"checking" | "healthy" | "offline">("checking");
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      let res = await fetch("/api/v1/health").catch(() => null);
      if (!res || !res.ok) {
        res = await fetch("http://localhost:8000/api/v1/health").catch(() => null);
      }

      if (res && res.ok) {
        const data: HealthResponse = await res.json();
        if (data.status === "healthy") {
          setHealthStatus("healthy");
          setHealthData(data);
          return;
        }
      }
      setHealthStatus("offline");
    } catch {
      setHealthStatus("offline");
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <header className="sticky top-0 z-50 w-full glass-header">
      {/* 8-Point Grid: h-16 (64px), px-6 (24px) / lg:px-8 (32px) */}
      <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-8">
        {/* Brand Group */}
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl soft-btn text-primary shrink-0">
            <Terminal className="h-5 w-5" strokeWidth={2.1} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-foreground text-base sm:text-lg">
                RepoAnalyzer
              </span>
              <span className="rounded-full bg-accent/15 px-2 py-1 text-[11px] font-bold text-accent border border-accent/25">
                AI Agent
              </span>
            </div>
            <p className="text-xs text-muted-foreground hidden sm:block">
              CLI Agent &middot; Architecture &amp; Software Principles Auditor
            </p>
          </div>
        </div>

        {/* Right Status Controls - 8-Point Spacing Rhythm */}
        <div className="flex items-center gap-4">
          {/* Backend Health Pill Button */}
          <button
            onClick={checkHealth}
            className="flex h-10 items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-foreground soft-btn cursor-pointer"
            title={
              healthData
                ? `Backend: ${healthData.service} (${healthData.environment}) - Click to refresh`
                : "Click to refresh health check"
            }
          >
            <Activity className="h-4 w-4 text-muted-foreground" strokeWidth={2.1} />
            <span
              className={`h-2 w-2 rounded-full ${
                healthStatus === "healthy"
                  ? "bg-accent shadow-[0_0_8px_rgba(46,204,113,0.8)]"
                  : healthStatus === "checking"
                  ? "bg-primary animate-pulse"
                  : "bg-destructive shadow-[0_0_8px_rgba(217,56,41,0.8)]"
              }`}
            />
            <span className="font-mono text-xs hidden sm:inline">
              {healthStatus === "healthy"
                ? "Backend Healthy"
                : healthStatus === "checking"
                ? "Checking..."
                : "Backend Offline"}
            </span>
          </button>

          {/* Analysis Status Pill */}
          <div className="hidden lg:flex h-10 items-center gap-2 rounded-full px-4 py-2 text-xs text-muted-foreground soft-btn">
            <span
              className={`h-2 w-2 rounded-full ${
                isAnalyzing
                  ? "bg-accent animate-pulse shadow-[0_0_8px_rgba(46,204,113,0.8)]"
                  : hasResult
                  ? "bg-primary"
                  : "bg-muted-foreground/50"
              }`}
            />
            <span className="font-medium text-foreground">
              {isAnalyzing
                ? "Agent Analyzing..."
                : hasResult
                ? "Audit Complete"
                : "Agent Standby"}
            </span>
          </div>

          {/* New Audit Reset Pill */}
          {hasResult && !isAnalyzing && (
            <button
              onClick={onReset}
              className="flex h-10 items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-foreground soft-btn cursor-pointer"
              title="Reset analysis"
            >
              <RefreshCw className="h-4 w-4" strokeWidth={2.1} />
              <span className="hidden sm:inline">New Audit</span>
            </button>
          )}

          {/* Theme Toggle Soft Circle Button */}
          <button
            onClick={onToggleDarkMode}
            className="flex h-10 w-10 items-center justify-center rounded-full soft-btn text-foreground cursor-pointer"
            aria-label="Toggle theme"
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {darkMode ? (
              <Sun className="h-4 w-4 text-accent" strokeWidth={2.1} />
            ) : (
              <Moon className="h-4 w-4 text-foreground" strokeWidth={2.1} />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
