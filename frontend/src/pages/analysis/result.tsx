import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  CheckCircle2,
  XCircle,
  Clock,
  GitBranch,
  FileCode,
  Bug,
  Wrench,
  FlaskConical,
  Download,
  ArrowLeft,
  Loader2,
  ExternalLink,
  Timer,
  Hash,
  BarChart3,
  Shield,
  Copy,
  Check,
  GitPullRequest,
  GitMerge,
  PlayCircle,
  RefreshCw,
  Zap,
  AlertTriangle,
  Activity,
  Target,
  Layers,
} from "lucide-react";
import { toast } from "sonner";

import { Header } from "@/components/layout/header";
import { Main } from "@/components/layout/main";
import { Search } from "@/components/search";
import { ThemeSwitch } from "@/components/theme-switch";
import { ProfileDropdown } from "@/components/profile-dropdown";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

import {
  analysisApi,
  type AnalysisStatus,
  type AnalysisResult,
  type CodeFix,
  type TestResult,
  type CIStatusResponse,
} from "@/api/analysis";

// ============ STATUS POLLING PAGE ============

export default function AnalysisResultPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const navigate = useNavigate();

  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchResult = useCallback(async () => {
    if (!analysisId) return;
    try {
      const res = await analysisApi.getResult(analysisId);
      if (res.status === "completed" && res.result) {
        setResult(res.result);
        setStatus({
          status: "completed",
          progress: 100,
          current_step: "completed",
          message: "Analysis completed",
        });
        // Stop polling
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setLoading(false);
        return true;
      }
    } catch {
      // Result not yet available — that's fine
    }
    return false;
  }, [analysisId]);

  const pollStatus = useCallback(async () => {
    if (!analysisId) return;
    try {
      const s = await analysisApi.getStatus(analysisId);
      setStatus(s);

      if (s.status === "completed") {
        await fetchResult();
      } else if (s.status === "error") {
        setError(s.message || "Analysis failed");
        setLoading(false);
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    } catch (err: any) {
      if (err?.response?.status === 404) {
        // Perhaps already done, try fetching result directly
        const found = await fetchResult();
        if (!found) {
          setError("Analysis not found");
          setLoading(false);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      }
    }
  }, [analysisId, fetchResult]);

  useEffect(() => {
    if (!analysisId) {
      setError("No analysis ID provided");
      setLoading(false);
      return;
    }

    // Initial fetch
    fetchResult().then((found) => {
      if (!found) {
        pollStatus();
        // Start polling every 3s
        pollRef.current = setInterval(pollStatus, 3000);
      }
    });

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [analysisId, fetchResult, pollStatus]);

  const handleCancel = async () => {
    if (!analysisId) return;
    try {
      await analysisApi.cancelAnalysis(analysisId);
      toast.info("Analysis cancelled");
      navigate("/analysis");
    } catch {
      toast.error("Failed to cancel analysis");
    }
  };

  // ============ RENDER ============

  return (
    <>
      <Header>
        <Search />
        <div className="ml-auto flex items-center space-x-4">
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className="w-full space-y-6">
          {/* Navigation */}
          <div className="flex items-center justify-between">
            <Button variant="ghost" size="sm" asChild className="gap-2">
              <Link to="/analysis">
                <ArrowLeft className="h-4 w-4" />
                Back to Analysis
              </Link>
            </Button>
            {analysisId && (
              <Badge variant="outline" className="font-mono text-xs">
                ID: {analysisId.slice(0, 8)}...
              </Badge>
            )}
          </div>

          {/* If still loading / polling */}
          {loading && !result && !error && (
            <AnalysisPollingView
              status={status}
              onCancel={handleCancel}
            />
          )}

          {/* Error state */}
          {error && !result && (
            <Card className="relative overflow-hidden border-destructive/30 bg-destructive/5">
              <div className="absolute inset-0 bg-gradient-to-br from-destructive/5 via-transparent to-destructive/10" />
              <CardContent className="relative flex flex-col items-center justify-center py-16 text-center">
                <div className="h-16 w-16 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
                  <XCircle className="h-8 w-8 text-destructive" />
                </div>
                <h2 className="text-2xl font-semibold">Analysis Failed</h2>
                <p className="text-muted-foreground mt-3 max-w-md">{error}</p>
                <Button className="mt-8" size="lg" onClick={() => navigate("/analysis")}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Try Again
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Completed result */}
          {result && (
            <AnalysisResultView
              result={result}
              analysisId={analysisId!}
            />
          )}
        </div>
      </Main>
    </>
  );
}

// ============ POLLING VIEW ============

function AnalysisPollingView({
  status,
  onCancel,
}: {
  status: AnalysisStatus | null;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-6">
      {/* Hero Loading Section */}
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90">
        <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:32px_32px]" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />
        
        <CardContent className="relative py-16">
          <div className="flex flex-col lg:flex-row lg:items-center gap-12">
            {/* Left: Animation */}
            <div className="flex-shrink-0 flex justify-center lg:justify-start">
              <div className="relative">
                <div className="h-32 w-32 rounded-full border-4 border-primary/20 flex items-center justify-center bg-card shadow-2xl">
                  <Loader2 className="h-14 w-14 text-primary animate-spin" />
                </div>
                <div className="absolute -top-2 -right-2 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center animate-pulse">
                  <Activity className="h-4 w-4 text-primary" />
                </div>
                <div className="absolute -bottom-1 -left-1 h-6 w-6 rounded-full bg-green-500/20 flex items-center justify-center animate-pulse delay-300">
                  <Zap className="h-3 w-3 text-green-500" />
                </div>
              </div>
            </div>

            {/* Right: Content */}
            <div className="flex-1 text-center lg:text-left space-y-6">
              <div className="space-y-2">
                <div className="flex items-center justify-center lg:justify-start gap-3">
                  <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                    <Activity className="h-3 w-3 mr-1.5 animate-pulse" />
                    In Progress
                  </Badge>
                </div>
                <h2 className="text-3xl font-bold tracking-tight">Analyzing Repository</h2>
                <p className="text-muted-foreground max-w-lg">
                  {status?.message || "Initializing the multi-agent analysis pipeline..."}
                </p>
              </div>

              {/* Progress Section */}
              <div className="max-w-lg mx-auto lg:mx-0 space-y-3">
                <div className="flex justify-between items-center text-sm">
                  <span className="font-medium capitalize text-foreground">
                    {status?.current_step?.replace(/_/g, " ") || "Starting"}
                  </span>
                  <span className="text-primary font-bold">{status?.progress ?? 0}%</span>
                </div>
                <div className="relative">
                  <Progress value={status?.progress ?? 0} className="h-3" />
                  <div 
                    className="absolute top-0 h-3 bg-primary/30 rounded-full blur-sm transition-all duration-500"
                    style={{ width: `${status?.progress ?? 0}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Steps Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <PipelineStep 
          label="Clone Repo" 
          icon={GitBranch}
          active={statusInRange(status, 0, 15)} 
          done={statusPast(status, 15)} 
          step={1}
        />
        <PipelineStep 
          label="Code Review" 
          icon={Bug}
          active={statusInRange(status, 15, 35)} 
          done={statusPast(status, 35)} 
          step={2}
        />
        <PipelineStep 
          label="Run Tests" 
          icon={FlaskConical}
          active={statusInRange(status, 35, 55)} 
          done={statusPast(status, 55)} 
          step={3}
        />
        <PipelineStep 
          label="Fix Issues" 
          icon={Wrench}
          active={statusInRange(status, 55, 75)} 
          done={statusPast(status, 75)} 
          step={4}
        />
        <PipelineStep 
          label="Generate Tests" 
          icon={Shield}
          active={statusInRange(status, 75, 90)} 
          done={statusPast(status, 90)} 
          step={5}
        />
        <PipelineStep 
          label="Push to GitHub" 
          icon={GitPullRequest}
          active={statusInRange(status, 90, 100)} 
          done={statusPast(status, 100)} 
          step={6}
        />
      </div>

      {/* Cancel Button */}
      <div className="flex justify-center">
        <Button variant="outline" size="lg" onClick={onCancel} className="gap-2">
          <XCircle className="h-4 w-4" />
          Cancel Analysis
        </Button>
      </div>
    </div>
  );
}

function PipelineStep({ 
  label, 
  icon: Icon,
  active, 
  done,
  step 
}: { 
  label: string; 
  icon: React.ComponentType<{ className?: string }>;
  active: boolean; 
  done: boolean;
  step: number;
}) {
  return (
    <Card className={`relative overflow-hidden transition-all duration-300 ${
      done
        ? "border-green-500/40 bg-green-500/5"
        : active
        ? "border-primary/40 bg-primary/5 shadow-lg shadow-primary/10"
        : "border-border/40 bg-card/50"
    }`}>
      <CardContent className="p-4 flex flex-col items-center text-center gap-3">
        <div className={`relative h-12 w-12 rounded-xl flex items-center justify-center transition-colors ${
          done
            ? "bg-green-500/10 text-green-600"
            : active
            ? "bg-primary/10 text-primary"
            : "bg-muted text-muted-foreground"
        }`}>
          {done ? (
            <CheckCircle2 className="h-6 w-6" />
          ) : active ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Icon className="h-6 w-6" />
          )}
          <span className={`absolute -top-1 -right-1 h-5 w-5 rounded-full text-[10px] font-bold flex items-center justify-center ${
            done
              ? "bg-green-500 text-white"
              : active
              ? "bg-primary text-primary-foreground"
              : "bg-muted-foreground/20 text-muted-foreground"
          }`}>
            {step}
          </span>
        </div>
        <span className={`text-sm font-medium ${
          done
            ? "text-green-600 dark:text-green-400"
            : active
            ? "text-primary"
            : "text-muted-foreground"
        }`}>
          {label}
        </span>
      </CardContent>
    </Card>
  );
}

function statusInRange(status: AnalysisStatus | null, from: number, to: number) {
  const p = status?.progress ?? 0;
  return p >= from && p < to;
}

function statusPast(status: AnalysisStatus | null, threshold: number) {
  return (status?.progress ?? 0) >= threshold;
}

// ============ RESULT VIEW ============

function AnalysisResultView({
  result,
  analysisId,
}: {
  result: AnalysisResult;
  analysisId: string;
}) {
  const [ciStatus, setCIStatus] = useState<CIStatusResponse | null>(null);
  const [ciLoading, setCILoading] = useState(false);
  const [merging, setMerging] = useState(false);
  const ciPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  const totalTests = result.test_results?.length ?? 0;
  const passedTests = result.test_results?.filter((t) => t.passed).length ?? 0;
  const failedTests = totalTests - passedTests;
  const duration = result.total_time_taken
    ? `${result.total_time_taken.toFixed(1)}s`
    : "—";

  // Fetch CI status
  const fetchCIStatus = useCallback(async () => {
    if (!result.pr_url || !result.pr_number) return;
    setCILoading(true);
    try {
      const status = await analysisApi.getCIStatus(analysisId);
      setCIStatus(status);
      
      // Stop polling if CI completed
      if (status.status === "success" || status.status === "failure") {
        if (ciPollRef.current) {
          clearInterval(ciPollRef.current);
          ciPollRef.current = null;
        }
      }
    } catch (err) {
      console.error("Error fetching CI status:", err);
    } finally {
      setCILoading(false);
    }
  }, [analysisId, result.pr_url, result.pr_number]);

  // Start CI polling if PR exists
  useEffect(() => {
    if (result.pr_url && result.pr_number && !result.merged) {
      fetchCIStatus();
      // Poll every 10 seconds
      ciPollRef.current = setInterval(fetchCIStatus, 10000);
    }
    return () => {
      if (ciPollRef.current) clearInterval(ciPollRef.current);
    };
  }, [result.pr_url, result.pr_number, result.merged, fetchCIStatus]);

  // Manual merge handler
  const handleMerge = async () => {
    if (!result.pr_number) return;
    setMerging(true);
    try {
      // Note: In production, you'd pass the actual token
      const res = await analysisApi.mergePR(analysisId, "");
      if (res.status === "merged") {
        toast.success("PR merged successfully!");
        setCIStatus(prev => prev ? { ...prev, merged: true } : null);
      } else if (res.status === "already_merged") {
        toast.info("PR was already merged");
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to merge PR");
    } finally {
      setMerging(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Hero Header Section */}
      <Card className="relative overflow-hidden border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90">
        <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:32px_32px]" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-green-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />
        
        <CardContent className="relative py-10">
          <div className="flex flex-col lg:flex-row lg:items-center gap-8">
            {/* Left: Status Icon */}
            <div className="flex-shrink-0 flex justify-center lg:justify-start">
              <div className="relative">
                <div className={`h-24 w-24 rounded-2xl flex items-center justify-center shadow-2xl ${
                  result.status === "completed" 
                    ? "bg-gradient-to-br from-green-500/20 to-green-600/10 border-2 border-green-500/30" 
                    : "bg-gradient-to-br from-destructive/20 to-destructive/10 border-2 border-destructive/30"
                }`}>
                  {result.status === "completed" ? (
                    <CheckCircle2 className="h-12 w-12 text-green-500" />
                  ) : (
                    <XCircle className="h-12 w-12 text-destructive" />
                  )}
                </div>
                <div className="absolute -bottom-2 -right-2 h-8 w-8 rounded-full bg-primary flex items-center justify-center shadow-lg">
                  <Target className="h-4 w-4 text-primary-foreground" />
                </div>
              </div>
            </div>

            {/* Center: Info */}
            <div className="flex-1 text-center lg:text-left space-y-3">
              <div className="flex items-center justify-center lg:justify-start gap-3 flex-wrap">
                <StatusBadge status={result.status} />
                {result.pr_url && (
                  <Badge variant="outline" className="bg-purple-500/10 text-purple-600 border-purple-500/30">
                    <GitPullRequest className="h-3 w-3 mr-1" />
                    PR Created
                  </Badge>
                )}
              </div>
              <h1 className="text-3xl font-bold tracking-tight">Analysis Complete</h1>
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">{result.team_name}</span>
                <span className="mx-2">•</span>
                {result.team_leader_name}
              </p>
            </div>

            {/* Right: Actions */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button variant="outline" size="default" asChild className="gap-2">
                <a
                  href={analysisApi.getJsonReportUrl(analysisId)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Download className="h-4 w-4" />
                  JSON Report
                </a>
              </Button>
              <Button size="default" asChild className="gap-2">
                <a
                  href={analysisApi.getPdfReportUrl(analysisId)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Download className="h-4 w-4" />
                  PDF Report
                </a>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Statistics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={Bug}
          label="Issues Detected"
          value={result.total_failures_detected}
          color="destructive"
        />
        <SummaryCard
          icon={Wrench}
          label="Fixes Applied"
          value={result.total_fixes_applied}
          color="primary"
        />
        <SummaryCard
          icon={FlaskConical}
          label="Tests"
          value={`${passedTests}/${totalTests}`}
          sub={failedTests > 0 ? `${failedTests} failed` : "All passing"}
          color={failedTests > 0 ? "warning" : "success"}
        />
        <SummaryCard
          icon={Timer}
          label="Duration"
          value={duration}
          color="default"
        />
      </div>

      {/* Repository & PR Section - Two Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Repository info card */}
        <Card className="relative overflow-hidden border border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90">
          <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:24px_24px]" />
          <div className="absolute top-0 right-0 w-48 h-48 bg-primary/5 rounded-full blur-2xl -translate-y-1/4 translate-x-1/4" />
          <CardHeader className="relative pb-2">
            <CardTitle className="flex items-center gap-3 text-lg">
              <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
                <Layers className="h-5 w-5 text-primary" />
              </div>
              Repository Details
            </CardTitle>
          </CardHeader>
          <CardContent className="relative pt-2">
            <div className="space-y-3">
              <InfoRow label="Repository" value={result.repo_url} isLink />
              <InfoRow label="Branch" value={result.branch_name} icon={<GitBranch className="h-4 w-4" />} />
              <InfoRow label="Team" value={result.team_name} />
              <InfoRow label="Leader" value={result.team_leader_name} />
              {result.commit_sha && (
                <InfoRow label="Commit" value={result.commit_sha.slice(0, 8)} copyValue={result.commit_sha} />
              )}
              {result.branch_url && (
                <InfoRow label="Branch URL" value={result.branch_url} isLink />
              )}
            </div>
          </CardContent>
        </Card>

        {/* PR and CI Status card */}
        {(result.pr_url || result.pr_number) && (
          <Card className="relative overflow-hidden border border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90">
            <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:24px_24px]" />
            <div className="absolute top-0 right-0 w-48 h-48 bg-green-500/5 rounded-full blur-2xl -translate-y-1/4 translate-x-1/4" />
            <CardHeader className="relative pb-2">
              <CardTitle className="flex items-center gap-3 text-lg">
                <div className="h-10 w-10 rounded-xl bg-green-500/10 flex items-center justify-center ring-1 ring-green-500/20">
                  <GitPullRequest className="h-5 w-5 text-green-600" />
                </div>
                Pull Request & CI
              </CardTitle>
            </CardHeader>
            <CardContent className="relative pt-2">
              <div className="space-y-4">
                {/* PR Info Row */}
                {result.pr_url && (
                  <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                    <span className="text-sm font-medium text-muted-foreground">Pull Request</span>
                    <a
                      href={result.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                    >
                      <Badge variant="outline" className="bg-purple-500/10 text-purple-600 border-purple-500/30">
                        #{result.pr_number}
                      </Badge>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                )}
                
                {/* CI Status Row */}
                <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                  <span className="text-sm font-medium text-muted-foreground">CI Status</span>
                  <div className="flex items-center gap-2">
                    {ciLoading && !ciStatus ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    ) : (
                      <CIStatusBadge status={ciStatus?.status || result.ci_status || "pending"} />
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={fetchCIStatus}
                      disabled={ciLoading}
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${ciLoading ? "animate-spin" : ""}`} />
                    </Button>
                  </div>
                </div>
                
                {/* Workflow URL */}
                {ciStatus?.workflow_url && (
                  <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                    <span className="text-sm font-medium text-muted-foreground">Workflow</span>
                    <a
                      href={ciStatus.workflow_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                    >
                      View Actions
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                )}
                
                {/* Merge Status Row */}
                <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                  <span className="text-sm font-medium text-muted-foreground">Merge Status</span>
                  {(ciStatus?.merged || result.merged) ? (
                    <Badge className="bg-purple-600">
                      <GitMerge className="mr-1 h-3 w-3" />
                      Merged
                    </Badge>
                  ) : (
                    <Badge variant="outline">Not Merged</Badge>
                  )}
                </div>
              </div>
              
              {/* Merge Button */}
              {!result.merged && !ciStatus?.merged && ciStatus?.status === "success" && (
                <div className="mt-6 pt-4 border-t border-border/40">
                  <Button
                    onClick={handleMerge}
                    disabled={merging}
                    className="w-full bg-purple-600 hover:bg-purple-700"
                    size="lg"
                  >
                    {merging ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Merging...
                      </>
                    ) : (
                      <>
                        <GitMerge className="mr-2 h-4 w-4" />
                        Merge Pull Request
                      </>
                    )}
                  </Button>
                  <p className="mt-3 text-xs text-center text-muted-foreground">
                    CI passed! You can now merge the pull request.
                  </p>
                </div>
              )}
              
              {/* CI Failed Message */}
              {ciStatus?.status === "failure" && (
                <div className="mt-4 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-destructive">CI Workflow Failed</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Please check the workflow logs and fix any issues before merging.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Detailed Results Section */}
      <Card className="relative overflow-hidden border border-border/40 bg-gradient-to-br from-card via-card/95 to-card/90">
        <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:24px_24px]" />
        <CardHeader className="relative border-b border-border/40 pb-4">
          <CardTitle className="flex items-center gap-3 text-lg">
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
              <BarChart3 className="h-5 w-5 text-primary" />
            </div>
            Detailed Analysis
          </CardTitle>
          <CardDescription>
            Explore fixes applied, test results, and AI-generated tests
          </CardDescription>
        </CardHeader>
        <CardContent className="relative pt-6">
          <Tabs defaultValue="fixes" className="space-y-6">
            <TabsList className="w-full justify-start bg-muted/50 p-1">
              <TabsTrigger value="fixes" className="flex items-center gap-2 data-[state=active]:bg-background">
                <Wrench className="h-4 w-4" />
                <span>Fixes</span>
                <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                  {result.fixes?.length ?? 0}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="tests" className="flex items-center gap-2 data-[state=active]:bg-background">
                <FlaskConical className="h-4 w-4" />
                <span>Tests</span>
                <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                  {totalTests}
                </Badge>
              </TabsTrigger>
              {result.generated_tests && result.generated_tests.length > 0 && (
                <TabsTrigger value="generated" className="flex items-center gap-2 data-[state=active]:bg-background">
                  <Shield className="h-4 w-4" />
                  <span>Generated</span>
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {result.generated_tests.length}
                  </Badge>
                </TabsTrigger>
              )}
              {result.summary && (
                <TabsTrigger value="summary" className="flex items-center gap-2 data-[state=active]:bg-background">
                  <BarChart3 className="h-4 w-4" />
                  <span>Summary</span>
                </TabsTrigger>
              )}
            </TabsList>

            {/* Fixes Tab */}
            <TabsContent value="fixes" className="mt-0">
              <FixesTable fixes={result.fixes ?? []} />
            </TabsContent>

            {/* Tests Tab */}
            <TabsContent value="tests" className="mt-0">
              <TestsTable tests={result.test_results ?? []} />
            </TabsContent>

            {/* Generated Tests Tab */}
            {result.generated_tests && result.generated_tests.length > 0 && (
              <TabsContent value="generated" className="mt-0">
                <GeneratedTestsList tests={result.generated_tests} />
              </TabsContent>
            )}

            {/* Summary Tab */}
            {result.summary && (
              <TabsContent value="summary" className="mt-0">
                <SummaryView summary={result.summary} />
              </TabsContent>
            )}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

// ============ SUB-COMPONENTS ============

function StatusBadge({ status }: { status: string }) {
  const isCompleted = status === "completed";
  const isError = status === "error" || status === "failed";
  return (
    <Badge
      variant={isCompleted ? "default" : isError ? "destructive" : "secondary"}
      className={
        isCompleted
          ? "bg-green-500/10 text-green-600 border-green-500/30 dark:text-green-400"
          : ""
      }
    >
      {isCompleted ? (
        <CheckCircle2 className="mr-1 h-3 w-3" />
      ) : isError ? (
        <XCircle className="mr-1 h-3 w-3" />
      ) : (
        <Clock className="mr-1 h-3 w-3" />
      )}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

function CIStatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { variant: "default" | "destructive" | "secondary" | "outline"; className: string; icon: React.ReactNode; label: string }> = {
    success: {
      variant: "default",
      className: "bg-green-500/10 text-green-600 border-green-500/30 dark:text-green-400",
      icon: <CheckCircle2 className="mr-1 h-3 w-3" />,
      label: "Passed"
    },
    failure: {
      variant: "destructive",
      className: "",
      icon: <XCircle className="mr-1 h-3 w-3" />,
      label: "Failed"
    },
    running: {
      variant: "secondary",
      className: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
      icon: <PlayCircle className="mr-1 h-3 w-3 animate-pulse" />,
      label: "Running"
    },
    pending: {
      variant: "outline",
      className: "bg-amber-500/10 text-amber-600 border-amber-500/30 dark:text-amber-400",
      icon: <Clock className="mr-1 h-3 w-3" />,
      label: "Pending"
    },
    unknown: {
      variant: "outline",
      className: "",
      icon: <Clock className="mr-1 h-3 w-3" />,
      label: "Unknown"
    }
  };

  const config = statusConfig[status] || statusConfig.unknown;
  
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.icon}
      {config.label}
    </Badge>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  const colorClasses: Record<string, string> = {
    primary: "bg-primary/10 ring-primary/20 text-primary",
    destructive: "bg-destructive/10 ring-destructive/20 text-destructive",
    success: "bg-green-500/10 ring-green-500/20 text-green-600 dark:text-green-400",
    warning: "bg-amber-500/10 ring-amber-500/20 text-amber-600 dark:text-amber-400",
    default: "bg-muted ring-border text-foreground",
  };

  const iconClass = colorClasses[color] || colorClasses.default;

  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardContent className="relative p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
          <div
            className={`h-12 w-12 rounded-xl ring-1 flex items-center justify-center ${iconClass}`}
          >
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InfoRow({
  label,
  value,
  isLink,
  icon,
  copyValue,
}: {
  label: string;
  value: string;
  isLink?: boolean;
  icon?: React.ReactNode;
  copyValue?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(copyValue || value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/40 p-3">
      <span className="text-xs font-medium text-muted-foreground min-w-[80px] pt-0.5">
        {label}
      </span>
      <span className="text-sm font-medium flex items-center gap-1.5 truncate flex-1">
        {icon}
        {isLink ? (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline truncate flex items-center gap-1"
          >
            {value}
            <ExternalLink className="h-3 w-3 flex-shrink-0" />
          </a>
        ) : (
          <span className="truncate">{value}</span>
        )}
        {copyValue && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 flex-shrink-0"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-green-500" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy full SHA</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </span>
    </div>
  );
}

// ============ FIXES TABLE ============

function FixesTable({ fixes }: { fixes: CodeFix[] }) {
  if (fixes.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-500 mb-3" />
          <p className="font-medium">No issues found</p>
          <p className="text-sm text-muted-foreground">
            The repository passed all checks.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardHeader className="relative">
        <CardTitle className="text-base">Code Fixes</CardTitle>
        <CardDescription>
          {fixes.filter((f) => f.status === "FIXED").length} of {fixes.length}{" "}
          issues resolved
        </CardDescription>
      </CardHeader>
      <CardContent className="relative p-0">
        <div className="overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead className="w-[70px]">Line</TableHead>
                <TableHead className="w-[120px]">Type</TableHead>
                <TableHead className="w-[90px]">Status</TableHead>
                <TableHead>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fixes.map((fix, i) => (
                <TableRow key={i}>
                  <TableCell className="font-mono text-xs max-w-[200px] truncate">
                    <div className="flex items-center gap-1.5">
                      <FileCode className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                      <span className="truncate">{fix.file_path}</span>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <div className="flex items-center gap-1">
                      <Hash className="h-3 w-3 text-muted-foreground" />
                      {fix.line_number}
                    </div>
                  </TableCell>
                  <TableCell>
                    <BugTypeBadge type={fix.bug_type} />
                  </TableCell>
                  <TableCell>
                    <FixStatusBadge status={fix.status} />
                  </TableCell>
                  <TableCell className="text-xs max-w-[250px] truncate">
                    {fix.description || fix.commit_message}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function BugTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    SYNTAX: "bg-red-500/10 text-red-600 border-red-500/30 dark:text-red-400",
    LOGIC: "bg-amber-500/10 text-amber-600 border-amber-500/30 dark:text-amber-400",
    IMPORT: "bg-blue-500/10 text-blue-600 border-blue-500/30 dark:text-blue-400",
    TYPE_ERROR: "bg-purple-500/10 text-purple-600 border-purple-500/30 dark:text-purple-400",
    LINTING: "bg-sky-500/10 text-sky-600 border-sky-500/30 dark:text-sky-400",
    INDENTATION: "bg-teal-500/10 text-teal-600 border-teal-500/30 dark:text-teal-400",
    TEST_FAILURE: "bg-orange-500/10 text-orange-600 border-orange-500/30 dark:text-orange-400",
  };

  return (
    <Badge variant="outline" className={`text-xs ${colors[type] || ""}`}>
      {type.replace(/_/g, " ")}
    </Badge>
  );
}

function FixStatusBadge({ status }: { status: string }) {
  const isFixed = status === "FIXED";
  return (
    <Badge
      variant="outline"
      className={`text-xs ${
        isFixed
          ? "bg-green-500/10 text-green-600 border-green-500/30 dark:text-green-400"
          : "bg-red-500/10 text-red-600 border-red-500/30 dark:text-red-400"
      }`}
    >
      {isFixed ? (
        <CheckCircle2 className="mr-1 h-3 w-3" />
      ) : (
        <XCircle className="mr-1 h-3 w-3" />
      )}
      {status}
    </Badge>
  );
}

// ============ TESTS TABLE ============

function TestsTable({ tests }: { tests: TestResult[] }) {
  if (tests.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <FlaskConical className="h-10 w-10 text-muted-foreground mb-3" />
          <p className="font-medium">No test results</p>
          <p className="text-sm text-muted-foreground">
            No tests were found or executed.
          </p>
        </CardContent>
      </Card>
    );
  }

  const passed = tests.filter((t) => t.passed).length;

  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardHeader className="relative">
        <CardTitle className="text-base">Test Results</CardTitle>
        <CardDescription>
          {passed} of {tests.length} tests passed
          {passed === tests.length && (
            <span className="ml-2 text-green-600 dark:text-green-400">
              — All tests passing!
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="relative p-0">
        <div className="overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[50px]">Status</TableHead>
                <TableHead>Test Name</TableHead>
                <TableHead className="w-[90px]">Duration</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tests.map((test, i) => (
                <TableRow key={i}>
                  <TableCell>
                    {test.passed ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs max-w-[300px] truncate">
                    {test.test_name}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {test.duration != null
                      ? `${test.duration.toFixed(3)}s`
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs max-w-[250px] truncate text-destructive">
                    {test.error_message || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

// ============ GENERATED TESTS ============

function GeneratedTestsList({ tests }: { tests: Record<string, any>[] }) {
  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardHeader className="relative">
        <CardTitle className="text-base">AI-Generated Test Cases</CardTitle>
        <CardDescription>
          {tests.length} test case{tests.length !== 1 && "s"} generated
        </CardDescription>
      </CardHeader>
      <CardContent className="relative">
        <Accordion type="multiple" className="space-y-2">
          {tests.map((test, i) => (
            <AccordionItem
              key={i}
              value={`test-${i}`}
              className="rounded-lg border border-border/40 px-4"
            >
              <AccordionTrigger className="text-sm hover:no-underline">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <span className="font-medium">
                    {test.test_name || `Test ${i + 1}`}
                  </span>
                  <Badge variant="outline" className="text-xs ml-2">
                    {test.test_framework || "pytest"}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2 text-xs">
                  {test.target_file && (
                    <p className="text-muted-foreground">
                      Target: <span className="font-mono">{test.target_file}</span>
                    </p>
                  )}
                  {test.test_code && (
                    <pre className="mt-2 rounded-lg bg-muted p-3 overflow-auto text-xs font-mono">
                      {test.test_code}
                    </pre>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}

// ============ SUMMARY VIEW ============

function SummaryView({ summary }: { summary: Record<string, any> }) {
  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardHeader className="relative">
        <CardTitle className="text-base">Detailed Summary</CardTitle>
        <CardDescription>
          Full analysis iteration details
        </CardDescription>
      </CardHeader>
      <CardContent className="relative">
        <pre className="rounded-lg bg-muted p-4 overflow-auto text-xs font-mono max-h-[500px]">
          {JSON.stringify(summary, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}
