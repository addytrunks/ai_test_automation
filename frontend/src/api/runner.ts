import { apiClient } from "./client"
import type { AIAnalysis, Run, RunCreatePayload, TestResult } from "./types"

export async function triggerRun(
  suiteId: string,
  payload: RunCreatePayload,
): Promise<Run> {
  const { data } = await apiClient.post<Run>(
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

export async function getAnalysis(resultId: string): Promise<AIAnalysis> {
  const { data } = await apiClient.get<AIAnalysis>(
    `/test-results/${resultId}/analysis`,
  )
  return data
}
