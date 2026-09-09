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
      // First try relative path (proxied by Vite)
      let res = await fetch("/api/v1/health").catch(() => null);
      // Fallback directly to localhost:8000 if needed
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
    const interval = setInterval(checkHealth, 10000); // Poll every 10 seconds
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20 shadow-sm">
            <Terminal className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-tight text-foreground text-lg">
                RepoAnalyzer
              </span>
              <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-medium text-accent border border-accent/25">
                AI Agent
              </span>
            </div>
            <p className="text-xs text-muted-foreground hidden sm:block">
              CLI Agent &middot; Architecture &amp; Software Principles Auditor
            </p>
          </div>
        </div>

        {/* Status Badges and Actions */}
        <div className="flex items-center gap-3">
          {/* Backend Health Badge */}
          <button
            onClick={checkHealth}
            className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-foreground hover:bg-muted transition-colors shadow-xs cursor-pointer"
            title={
              healthData
                ? `Backend: ${healthData.service} (${healthData.environment}) - Click to refresh`
                : "Click to refresh health check"
            }
          >
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            <span
              className={`h-2 w-2 rounded-full ${
                healthStatus === "healthy"
                  ? "bg-accent shadow-[0_0_8px_rgba(132,204,22,0.6)]"
                  : healthStatus === "checking"
                  ? "bg-primary animate-pulse"
                  : "bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.6)]"
              }`}
            />
            <span className="font-mono text-[11px]">
              {healthStatus === "healthy"
                ? "Backend: Healthy"
                : healthStatus === "checking"
                ? "Checking..."
                : "Backend: Offline"}
            </span>
          </button>

          {/* Analysis Status Badge */}
          <div className="hidden lg:flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground shadow-xs">
            <span
              className={`h-2 w-2 rounded-full ${
                isAnalyzing
                  ? "bg-accent animate-pulse"
                  : hasResult
                  ? "bg-primary"
                  : "bg-muted-foreground/50"
              }`}
            />
            <span>
              {isAnalyzing
                ? "Agent Analyzing..."
                : hasResult
                ? "Audit Complete"
                : "Standby"}
            </span>
          </div>

          {/* Reset / New Analysis Button */}
          {hasResult && !isAnalyzing && (
            <button
              onClick={onReset}
              className="flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted transition-colors shadow-xs cursor-pointer"
              title="Reset analysis"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>New Audit</span>
            </button>
          )}

          {/* Theme Toggle */}
          <button
            onClick={onToggleDarkMode}
            className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted transition-colors shadow-xs cursor-pointer"
            aria-label="Toggle theme"
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {darkMode ? (
              <Sun className="h-4 w-4 text-accent" />
            ) : (
              <Moon className="h-4 w-4 text-foreground" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
