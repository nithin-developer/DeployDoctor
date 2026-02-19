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
        <div className="mx-auto max-w-5xl space-y-6">
          {/* Back button */}
          <Button variant="ghost" size="sm" asChild>
            <Link to="/analysis">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Analysis
            </Link>
          </Button>

          {/* If still loading / polling */}
          {loading && !result && !error && (
            <AnalysisPollingView
              status={status}
              onCancel={handleCancel}
            />
          )}

          {/* Error state */}
          {error && !result && (
            <Card className="border-destructive/50">
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <XCircle className="h-12 w-12 text-destructive mb-4" />
                <h2 className="text-xl font-semibold">Analysis Failed</h2>
                <p className="text-muted-foreground mt-2 max-w-md">{error}</p>
                <Button className="mt-6" onClick={() => navigate("/analysis")}>
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
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardContent className="relative flex flex-col items-center justify-center py-16 text-center">
        <div className="relative mb-6">
          <div className="h-20 w-20 rounded-full border-4 border-primary/20 flex items-center justify-center">
            <Loader2 className="h-10 w-10 text-primary animate-spin" />
          </div>
        </div>

        <h2 className="text-xl font-semibold">Analyzing Repository</h2>
        <p className="text-muted-foreground mt-2 max-w-md">
          {status?.message || "Initializing the multi-agent analysis pipeline..."}
        </p>

        {/* Progress bar */}
        <div className="w-full max-w-sm mt-6 space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span className="capitalize">{status?.current_step?.replace(/_/g, " ") || "Starting"}</span>
            <span>{status?.progress ?? 0}%</span>
          </div>
          <Progress value={status?.progress ?? 0} className="h-2" />
        </div>

        {/* Pipeline steps */}
        <div className="mt-8 grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-3">
          <PipelineStep label="Clone Repo" active={statusInRange(status, 0, 15)} done={statusPast(status, 15)} />
          <PipelineStep label="Code Review" active={statusInRange(status, 15, 35)} done={statusPast(status, 35)} />
          <PipelineStep label="Run Tests" active={statusInRange(status, 35, 55)} done={statusPast(status, 55)} />
          <PipelineStep label="Fix Issues" active={statusInRange(status, 55, 75)} done={statusPast(status, 75)} />
          <PipelineStep label="Generate Tests" active={statusInRange(status, 75, 90)} done={statusPast(status, 90)} />
          <PipelineStep label="Push to GitHub" active={statusInRange(status, 90, 100)} done={statusPast(status, 100)} />
        </div>

        <Button variant="outline" className="mt-8" onClick={onCancel}>
          Cancel Analysis
        </Button>
      </CardContent>
    </Card>
  );
}

function PipelineStep({ label, active, done }: { label: string; active: boolean; done: boolean }) {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
        done
          ? "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
          : active
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-border/40 text-muted-foreground"
      }`}
    >
      {done ? (
        <CheckCircle2 className="h-3.5 w-3.5" />
      ) : active ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Clock className="h-3.5 w-3.5" />
      )}
      <span className="font-medium">{label}</span>
    </div>
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
  const totalTests = result.test_results?.length ?? 0;
  const passedTests = result.test_results?.filter((t) => t.passed).length ?? 0;
  const failedTests = totalTests - passedTests;
  const duration = result.total_time_taken
    ? `${result.total_time_taken.toFixed(1)}s`
    : "—";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Analysis Result
            </h1>
            <StatusBadge status={result.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {result.team_name} &middot; {result.team_leader_name}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" asChild>
            <a
              href={analysisApi.getJsonReportUrl(analysisId)}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Download className="mr-2 h-4 w-4" />
              JSON
            </a>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <a
              href={analysisApi.getPdfReportUrl(analysisId)}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Download className="mr-2 h-4 w-4" />
              PDF
            </a>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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

      {/* Repository info card */}
      <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
        <CardHeader className="relative">
          <CardTitle className="flex items-center gap-2 text-base">
            <GitBranch className="h-5 w-5 text-primary" />
            Repository Details
          </CardTitle>
        </CardHeader>
        <CardContent className="relative">
          <div className="grid gap-4 sm:grid-cols-2">
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

      {/* Tabs: Fixes / Tests / Generated Tests */}
      <Tabs defaultValue="fixes" className="space-y-4">
        <TabsList>
          <TabsTrigger value="fixes" className="flex items-center gap-1.5">
            <Wrench className="h-4 w-4" />
            Fixes ({result.fixes?.length ?? 0})
          </TabsTrigger>
          <TabsTrigger value="tests" className="flex items-center gap-1.5">
            <FlaskConical className="h-4 w-4" />
            Tests ({totalTests})
          </TabsTrigger>
          {result.generated_tests && result.generated_tests.length > 0 && (
            <TabsTrigger value="generated" className="flex items-center gap-1.5">
              <Shield className="h-4 w-4" />
              Generated ({result.generated_tests.length})
            </TabsTrigger>
          )}
          {result.summary && (
            <TabsTrigger value="summary" className="flex items-center gap-1.5">
              <BarChart3 className="h-4 w-4" />
              Summary
            </TabsTrigger>
          )}
        </TabsList>

        {/* Fixes Tab */}
        <TabsContent value="fixes">
          <FixesTable fixes={result.fixes ?? []} />
        </TabsContent>

        {/* Tests Tab */}
        <TabsContent value="tests">
          <TestsTable tests={result.test_results ?? []} />
        </TabsContent>

        {/* Generated Tests Tab */}
        {result.generated_tests && result.generated_tests.length > 0 && (
          <TabsContent value="generated">
            <GeneratedTestsList tests={result.generated_tests} />
          </TabsContent>
        )}

        {/* Summary Tab */}
        {result.summary && (
          <TabsContent value="summary">
            <SummaryView summary={result.summary} />
          </TabsContent>
        )}
      </Tabs>
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
