import { useQuery } from "@tanstack/react-query"
import { useParams } from "react-router-dom"
import { useState } from "react"
import { JsonView, darkStyles } from "react-json-view-lite"
import "react-json-view-lite/dist/index.css"

import { getRun, getRunResults, getRunGaps } from "@/api/runner"
import { getTests } from "@/api/generator"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"
import AssertionList from "@/components/AssertionList"
import AIAnalysisPanel from "@/components/AIAnalysisPanel"
import CoverageGapList from "@/components/CoverageGapList"
import type { TestResult, Test } from "@/api/types"

const STATUS_ICON: Record<string, string> = {
  passed: "✅",
  failed: "❌",
  error: "⚠️",
  skipped: "⏭️",
}

const STATUS_BG: Record<string, string> = {
  passed: "border-l-emerald-500",
  failed: "border-l-red-500",
  error: "border-l-amber-500",
  skipped: "border-l-slate-400",
}

const RUN_STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-700 animate-pulse",
  analyzing: "bg-amber-100 text-amber-700 animate-pulse",
  completed: "bg-emerald-100 text-emerald-700",
  error: "bg-red-100 text-red-700",
}

const RUN_STATUS_MSG: Record<string, string> = {
  pending: "Preparing run…",
  running: "Running tests against the target API…",
  analyzing: "Tests complete. AI is analyzing failures…",
  completed: "Run complete.",
  error: "Run encountered an error.",
}

function ResultCard({
  result,
  test,
  isRunAnalyzing,
}: {
  result: TestResult
  test: Test | undefined
  isRunAnalyzing: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card
      id={`result-${result.id}`}
      className={`overflow-hidden border-l-4 ${STATUS_BG[result.status] ?? ""} cursor-pointer transition-shadow hover:shadow-md`}
      onClick={() => setExpanded(!expanded)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center gap-3">
          <span className="text-lg">{STATUS_ICON[result.status]}</span>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-sm truncate">
              {test?.name ?? "Unknown test"}
            </CardTitle>
            {test?.description && (
              <p className="text-xs text-slate-500 mt-0.5 truncate">
                {test.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {test && (
              <span className="text-xs font-mono text-slate-400">
                {test.method.toUpperCase()} {test.path}
              </span>
            )}
            {test?.auto_generated && (
              <span className="rounded px-1.5 py-0.5 text-xs font-medium bg-violet-100 text-violet-700">
                🤖
              </span>
            )}
            {result.response_status && (
              <span
                className={`rounded px-2 py-0.5 text-xs font-bold ${result.response_status < 400
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-red-100 text-red-700"
                  }`}
              >
                {result.response_status}
              </span>
            )}
            {result.duration_ms != null && (
              <span className="text-xs text-slate-400">
                {result.duration_ms}ms
              </span>
            )}
            <span className="text-xs text-slate-400">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent
          className="pt-0 space-y-4"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Error message */}
          {result.error_message && (
            <div className="rounded-md bg-red-50 p-3 text-xs text-red-700">
              <p className="font-medium">Error</p>
              <p className="mt-1">{result.error_message}</p>
            </div>
          )}

          {/* Assertion results */}
          {result.assertion_results && result.assertion_results.length > 0 && (
            <AssertionList results={result.assertion_results} />
          )}

          {/* Response body */}
          {result.response_body != null && (
            <div>
              <p className="text-xs font-medium text-slate-500 mb-1">
                Response Body
              </p>
              <div className="rounded-lg bg-slate-900 p-3 overflow-x-auto text-xs max-h-64 overflow-y-auto">
                {typeof result.response_body === "object" ? (
                  <JsonView
                    data={result.response_body as object}
                    style={darkStyles}
                  />
                ) : (
                  <pre className="text-slate-300 whitespace-pre-wrap">
                    {String(result.response_body)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* AI Analysis for failed tests */}
          {result.status === "failed" && (
            <AIAnalysisPanel
              resultId={result.id}
              isRunAnalyzing={isRunAnalyzing}
            />
          )}
        </CardContent>
      )}
    </Card>
  )
}

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  // Poll run status while active
  const { data: run, isLoading: runLoading } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (
        status === "pending" ||
        status === "running" ||
        status === "analyzing"
      )
        return 2000
      return false
    },
  })

  // Fetch results once run is at least in analyzing state
  const isActive =
    run?.status === "pending" || run?.status === "running"
  const hasResults = !isActive && !!run

  const { data: results } = useQuery({
    queryKey: ["run-results", runId],
    queryFn: () => getRunResults(runId!),
    enabled: hasResults,
    // Refetch once when run transitions from analyzing to completed
    refetchInterval: run?.status === "analyzing" ? 5000 : false,
  })

  // Fetch coverage gaps for this specific run
  const { data: gaps } = useQuery({
    queryKey: ["run-gaps", runId],
    queryFn: () => getRunGaps(runId!),
    enabled: run?.status === "completed",
  })

  // Fetch test definitions to map result → test metadata
  const { data: tests } = useQuery({
    queryKey: ["tests", run?.test_suite_id],
    queryFn: () => getTests(run!.test_suite_id),
    enabled: !!run?.test_suite_id,
  })

  const testMap = new Map<string, Test>()
  tests?.forEach((t) => testMap.set(t.id, t))

  const isRunAnalyzing = run?.status === "analyzing"
  const summary = run?.summary

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.history.back()}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            ← Back
          </button>
          <h1 className="text-2xl font-semibold">Run Results</h1>
          {run && (
            <>
              <span
                className={`inline-block rounded-full px-3 py-0.5 text-xs font-medium ${RUN_STATUS_STYLES[run.status] ?? "bg-slate-100"}`}
              >
                {run.status}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                Iteration {run.loop_iteration}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-600">{user?.email}</span>
          <Button
            variant="outline"
            onClick={() => {
              logout()
              window.location.href = "/login"
            }}
          >
            Log out
          </Button>
        </div>
      </header>

      {runLoading ? (
        <p className="text-sm text-slate-500">Loading run…</p>
      ) : !run ? (
        <p className="text-sm text-red-500">Run not found.</p>
      ) : (
        <>
          {/* Status message */}
          {run.status !== "completed" && (
            <Card className="max-w-lg mb-6">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-3">
                  {(run.status === "running" ||
                    run.status === "pending" ||
                    run.status === "analyzing") && (
                      <span className="relative flex h-3 w-3">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                        <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-500" />
                      </span>
                    )}
                  {RUN_STATUS_MSG[run.status]}
                </CardTitle>
              </CardHeader>
              {run.status === "analyzing" && (
                <CardContent>
                  <p className="text-sm text-slate-500">
                    All tests have been executed. The AI is now analyzing failed
                    test results and generating explanations. Results will appear
                    progressively below.
                  </p>
                </CardContent>
              )}
            </Card>
          )}

          {/* Summary bar */}
          {summary && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
              <div className="rounded-xl bg-white border p-4 text-center">
                <p className="text-2xl font-bold text-slate-800">
                  {summary.total}
                </p>
                <p className="text-xs text-slate-500 mt-1">Total</p>
              </div>
              <div className="rounded-xl bg-white border p-4 text-center">
                <p className="text-2xl font-bold text-emerald-600">
                  {summary.passed}
                </p>
                <p className="text-xs text-slate-500 mt-1">Passed</p>
              </div>
              <div className="rounded-xl bg-white border p-4 text-center">
                <p className="text-2xl font-bold text-red-600">
                  {summary.failed}
                </p>
                <p className="text-xs text-slate-500 mt-1">Failed</p>
              </div>
              <div className="rounded-xl bg-white border p-4 text-center">
                <p className="text-2xl font-bold text-amber-600">
                  {summary.errors}
                </p>
                <p className="text-xs text-slate-500 mt-1">Errors</p>
              </div>
              <div className="rounded-xl bg-white border p-4 text-center">
                <p className="text-2xl font-bold text-slate-600">
                  {summary.skipped || 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">Skipped</p>
              </div>
            </div>
          )}

          {/* Coverage Gaps for this run */}
          {gaps && gaps.length > 0 && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-base">
                  Coverage Gaps ({gaps.length})
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Untested scenarios identified during this iteration.
                </p>
              </CardHeader>
              <CardContent>
                <CoverageGapList gaps={gaps} />
              </CardContent>
            </Card>
          )}

          {/* Test results */}
          {results && results.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-500 mb-2">
                {results.length} test result
                {results.length !== 1 ? "s" : ""}
              </p>
              {results.map((result) => (
                <ResultCard
                  key={result.id}
                  result={result}
                  test={testMap.get(result.test_id)}
                  isRunAnalyzing={!!isRunAnalyzing}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
