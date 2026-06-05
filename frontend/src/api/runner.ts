import { apiClient } from "./client"
import type { AIAnalysis, CoverageGap, Run, RunAccepted, RunCreatePayload, TestResult } from "./types"

export async function triggerRun(
  suiteId: string,
  payload: RunCreatePayload,
): Promise<RunAccepted> {
  const { data } = await apiClient.post<RunAccepted>(
    `/test-suites/${suiteId}/runs`,
    payload,
  )
  return data
}

export async function listRuns(suiteId: string): Promise<Run[]> {
  const { data } = await apiClient.get<Run[]>(
    `/test-suites/${suiteId}/runs`,
  )
  return data
}

export async function getRun(runId: string): Promise<Run> {
  const { data } = await apiClient.get<Run>(`/runs/${runId}`)
  return data
}

export async function getRunResults(runId: string): Promise<TestResult[]> {
  const { data } = await apiClient.get<TestResult[]>(`/runs/${runId}/results`)
  return data
}

export async function getRunGaps(runId: string): Promise<CoverageGap[]> {
  const { data } = await apiClient.get<CoverageGap[]>(`/runs/${runId}/gaps`)
  return data
}

export async function getSuiteGaps(suiteId: string): Promise<CoverageGap[]> {
  const { data } = await apiClient.get<CoverageGap[]>(
    `/test-suites/${suiteId}/gaps`,
  )
  return data
}

export async function getAnalysis(resultId: string): Promise<AIAnalysis> {
  const { data } = await apiClient.get<AIAnalysis>(
    `/test-results/${resultId}/analysis`,
  )
  return data
}
