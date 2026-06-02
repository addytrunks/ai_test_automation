export interface User {
  id: string
  email: string
  name: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
}

export interface RegisterPayload {
  email: string
  password: string
  name?: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface ApiError {
  detail: string
}

export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  target_base_url: string | null
  created_at: string
}

export interface Spec {
  id: string
  project_id: string
  version: string
  parsed_at: string
  created_at: string
}

export interface Endpoint {
  id: string
  spec_id: string
  method: string
  path: string
  summary: string | null
  parameters: Record<string, unknown>[] | null
  request_body: Record<string, unknown> | null
  responses: Record<string, unknown> | null
  security: Record<string, unknown>[] | null
}

export interface ProjectCreatePayload {
  name: string
  description?: string
  target_base_url?: string
}

export interface ProjectUpdatePayload {
  name?: string
  description?: string
  target_base_url?: string
}

export interface TestSuite {
  id: string
  project_id: string
  spec_id: string
  name: string
  status: "pending" | "generating" | "ready" | "error"
  created_at: string
  updated_at: string
}

export interface TestAssertion {
  type: string
  target?: string
  op?: string
  expected?: unknown
}

export interface Test {
  id: string
  test_suite_id: string
  endpoint_id: string
  name: string
  description: string | null
  scenario_type: string
  method: string
  path: string
  path_params: Record<string, unknown> | null
  query_params: Record<string, unknown> | null
  headers: Record<string, unknown> | null
  body: Record<string, unknown> | null
  expected_status: number
  assertions: TestAssertion[] | null
  extract: Record<string, string> | null
  static_context: Record<string, string> | null
}

export interface TestSuiteCreatePayload {
  name: string
  spec_id: string
  endpoint_ids: string[]
  scenarios?: string[]
}

// ---------------------------------------------------------------------------
// Runner types
// ---------------------------------------------------------------------------

export interface RunSummary {
  total: number
  passed: number
  failed: number
  errors: number
  skipped?: number
}

export interface Run {
  id: string
  test_suite_id: string
  target_base_url: string
  status: "pending" | "running" | "analyzing" | "completed" | "error"
  summary: RunSummary | null
  parent_run_id: string | null
  loop_iteration: number
  started_at: string | null
  completed_at: string | null
}

export interface RunCreatePayload {
  target_base_url: string
}

export interface AssertionResult {
  assertion: TestAssertion
  passed: boolean
  actual?: unknown
  error?: string | null
}

export interface TestResult {
  id: string
  run_id: string
  test_id: string
  status: "passed" | "failed" | "error" | "skipped"
  response_status: number | null
  response_headers: Record<string, unknown> | null
  response_body: unknown
  duration_ms: number | null
  assertion_results: AssertionResult[] | null
  error_message: string | null
  created_at: string
}

export interface AIAnalysis {
  id: string
  test_result_id: string
  explanation: string
  likely_cause: string
  suggested_fix: string
  created_at: string
}
