const API_BASE_URL = (
  process.env.NEXT_PUBLIC_TRACEQA_API_URL ??
  "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export type TestStatus = "pass" | "fail" | "skip";
export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface TestRun {
  id: number;
  timestamp: string;
  source_drive: string;
  source_file: string | null;
  run_status: string;
}

export interface TestResult {
  id: number;
  run_id: number;
  test_name: string;
  status: TestStatus;
  execution_time: number;
  error_log: string | null;
  flakiness_score: number;
}

export interface ProactiveFix {
  test_name?: string | null;
  action?: string;
  rationale?: string;
  [key: string]: unknown;
}

export interface TestInsight {
  id: number;
  run_id: number;
  degradation_warning: string | null;
  proactive_fixes: ProactiveFix[];
  summary: string;
  test_name: string | null;
  execution_date: number | null;
  status: "passed" | "failed" | "skipped" | null;
  test_cases_passed: string | null;
  test_cases_failed: string | null;
  failed_test_case_list: string[];
  ai_analysis: string | null;
  instruction_to_qa: string[];
}

export interface ManualTestCase {
  title?: string;
  preconditions?: string[];
  steps?: string[];
  expected_result?: string;
  priority?: RiskLevel;
  [key: string]: unknown;
}

export interface CommitImpact {
  id: number;
  commit_hash: string;
  branch: string;
  summary: string;
  regression_risk_level: RiskLevel;
  suggested_automated_tests: string[];
  suggested_manual_tests: ManualTestCase[];
}

export interface RuntimeSettings {
  test_logs_directory: string;
  llm_model: string;
  llm_api_base: string;
  llm_api_key_configured: boolean;
  github_token_configured: boolean;
  github_webhook_secret_configured: boolean;
}

export interface RuntimeSettingsUpdate {
  test_logs_directory?: string;
  llm_model?: string;
  llm_api_base?: string;
  llm_api_key?: string;
  github_token?: string;
  github_webhook_secret?: string;
}

export interface DashboardData {
  runs: TestRun[];
  results: TestResult[];
  insights: TestInsight[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `TraceQA API request failed (${response.status})`;
    if (response.headers.get("content-type")?.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function getDashboardData(): Promise<DashboardData> {
  const [runs, results, insights] = await Promise.all([
    request<TestRun[]>("/test-runs?limit=100"),
    request<TestResult[]>("/test-results?limit=100"),
    request<TestInsight[]>("/ai-test-insights?limit=100"),
  ]);
  return { runs, results, insights };
}

export function getCommitImpacts(): Promise<CommitImpact[]> {
  return request<CommitImpact[]>("/commit-impacts?limit=100");
}

export function ingestTestReports(): Promise<unknown> {
  return request("/ingestion/runs", { method: "POST" });
}

export function getRuntimeSettings(): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/settings/runtime");
}

export function updateRuntimeSettings(
  payload: RuntimeSettingsUpdate,
): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/settings/runtime", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
