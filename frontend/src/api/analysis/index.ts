import { apiClient } from "../http";

// ============ REQUEST / RESPONSE TYPES ============

export interface AnalysisRequest {
  repo_url: string;
  team_name: string;
  team_leader_name: string;
  github_token?: string;
  generate_tests?: boolean;
  push_to_github?: boolean;
  create_pr?: boolean;
  auto_merge_on_ci_success?: boolean;
}

export interface AnalyzeResponse {
  analysis_id: string;
  message: string;
}

export interface AnalysisStatus {
  status: string;
  progress: number;
  current_step: string;
  message: string;
}

export interface CodeFix {
  file_path: string;
  bug_type: string;
  line_number: number;
  commit_message: string;
  status: string;
  original_code?: string;
  fixed_code?: string;
  description?: string;
}

export interface TestResult {
  test_name: string;
  passed: boolean;
  error_message?: string;
  duration?: number;
  file_path?: string;
  line_number?: number;
  failure_type?: string;
}

export interface AnalysisResult {
  repo_url: string;
  team_name: string;
  team_leader_name: string;
  branch_name: string;
  total_failures_detected: number;
  total_fixes_applied: number;
  total_time_taken: number;
  fixes: CodeFix[];
  test_results: TestResult[];
  start_time: string;
  end_time: string;
  status: string;
  summary?: Record<string, any>;
  generated_tests?: Record<string, any>[];
  commit_sha?: string;
  branch_url?: string;
  commit_message?: string;
  // PR and CI fields
  pr_url?: string;
  pr_number?: number;
  ci_status?: "pending" | "running" | "success" | "failure" | "unknown";
  merged?: boolean;
}

export interface CIStatusResponse {
  status: string;
  conclusion?: string;
  workflow_url?: string;
  pr_url?: string;
  pr_number?: number;
  merged: boolean;
  message: string;
}

export interface MergeResponse {
  status: string;
  message: string;
  merge_sha?: string;
}

export interface AnalysisResultResponse {
  status: string;
  result?: AnalysisResult;
  progress?: number;
  message?: string;
}

// ============ API METHODS ============

export const analysisApi = {
  /** Start a new analysis */
  async startAnalysis(data: AnalysisRequest): Promise<AnalyzeResponse> {
    const res = await apiClient.post("/api/analyze", data);
    return res.data;
  },

  /** Poll the status of an analysis */
  async getStatus(analysisId: string): Promise<AnalysisStatus> {
    const res = await apiClient.get(`/api/analyze/${analysisId}/status`);
    return res.data;
  },

  /** Get the completed result */
  async getResult(analysisId: string): Promise<AnalysisResultResponse> {
    const res = await apiClient.get(`/api/analyze/${analysisId}/result`);
    return res.data;
  },

  /** Cancel an analysis */
  async cancelAnalysis(analysisId: string): Promise<void> {
    await apiClient.delete(`/api/analyze/${analysisId}`);
  },

  /** Download JSON report */
  getJsonReportUrl(analysisId: string): string {
    const base = apiClient.defaults.baseURL || "";
    return `${base}/api/analyze/${analysisId}/report/json`;
  },

  /** Download PDF report */
  getPdfReportUrl(analysisId: string): string {
    const base = apiClient.defaults.baseURL || "";
    return `${base}/api/analyze/${analysisId}/report/pdf`;
  },

  /** Get CI/CD status for an analysis */
  async getCIStatus(analysisId: string, githubToken?: string): Promise<CIStatusResponse> {
    const params = githubToken ? { github_token: githubToken } : {};
    const res = await apiClient.get(`/api/analyze/${analysisId}/ci-status`, { params });
    return res.data;
  },

  /** Manually trigger PR merge */
  async mergePR(analysisId: string, githubToken: string): Promise<MergeResponse> {
    const res = await apiClient.post(`/api/analyze/${analysisId}/merge`, null, {
      params: { github_token: githubToken }
    });
    return res.data;
  },
};
