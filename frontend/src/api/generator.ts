import { apiClient } from "./client"
import type { Test, TestSuite, TestSuiteCreatePayload } from "./types"

export async function createTestSuite(
  projectId: string,
  payload: TestSuiteCreatePayload,
): Promise<TestSuite> {
  const { data } = await apiClient.post<TestSuite>(
    `/projects/${projectId}/test-suites`,
    payload,
  )
  return data
}

export async function getTestSuites(projectId: string): Promise<TestSuite[]> {
  const { data } = await apiClient.get<TestSuite[]>(
    `/projects/${projectId}/test-suites`,
  )
  return data
}

export async function getTestSuite(suiteId: string): Promise<TestSuite> {
  const { data } = await apiClient.get<TestSuite>(`/test-suites/${suiteId}`)
  return data
}

export async function getTests(suiteId: string): Promise<Test[]> {
  const { data } = await apiClient.get<Test[]>(`/test-suites/${suiteId}/tests`)
  return data
}

export async function deleteTestSuite(suiteId: string): Promise<void> {
  await apiClient.delete(`/test-suites/${suiteId}`)
}
