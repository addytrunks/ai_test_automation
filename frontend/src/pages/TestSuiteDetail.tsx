import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useParams, useNavigate } from "react-router-dom"
import { useState } from "react"
import { JsonView, darkStyles } from "react-json-view-lite"
import "react-json-view-lite/dist/index.css"

import { getTestSuite, getTests } from "@/api/generator"
import { triggerRun, listRuns, getSuiteGaps } from "@/api/runner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"
import RunLineageTree from "@/components/RunLineageTree"
import CoverageGapList from "@/components/CoverageGapList"
import type { Test } from "@/api/types"

const METHOD_COLORS: Record<string, string> = {
  get: "bg-emerald-100 text-emerald-800",
  post: "bg-blue-100 text-blue-800",
  put: "bg-amber-100 text-amber-800",
  patch: "bg-orange-100 text-orange-800",
  delete: "bg-red-100 text-red-800",
}

const SCENARIO_COLORS: Record<string, string> = {
  positive: "bg-emerald-100 text-emerald-800",
  negative: "bg-red-100 text-red-800",
  auth_bypass: "bg-amber-100 text-amber-800",
  bola: "bg-orange-100 text-orange-800",
  boundary: "bg-purple-100 text-purple-800",
  injection: "bg-rose-100 text-rose-800",
  mass_assignment: "bg-pink-100 text-pink-800",
  setup: "bg-teal-100 text-teal-800",
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  generating: "bg-blue-100 text-blue-700 animate-pulse",
  ready: "bg-emerald-100 text-emerald-700",
  error: "bg-red-100 text-red-700",
}

function TestCard({ test }: { test: Test }) {
  return (
    <Card id={`test-${test.id}`} className="overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${SCENARIO_COLORS[test.scenario_type] ?? "bg-slate-100 text-slate-700"}`}
          >
            {test.scenario_type.replace("_", " ")}
          </span>
          {test.auto_generated && (
            <span className="inline-block rounded px-2 py-0.5 text-xs font-medium bg-violet-100 text-violet-700">
              🤖 auto-generated
            </span>
          )}
          <span className="ml-auto text-xs font-mono text-slate-400">
            expects {test.expected_status}
          </span>
        </div>
        <CardTitle className="text-sm mt-2">{test.name}</CardTitle>
        {test.description && (
          <p className="text-xs text-slate-500 mt-1">{test.description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {/* Path params */}
        {test.path_params && Object.keys(test.path_params).length > 0 ? (
          <CollapsibleJson label="Path Params" data={test.path_params} />
        ) : (
          <EmptySection label="Path Params" message="No path parameters" />
        )}

        {/* Query params */}
        {test.query_params && Object.keys(test.query_params).length > 0 ? (
          <CollapsibleJson label="Query Params" data={test.query_params} />
        ) : (
          <EmptySection label="Query Params" message="No query parameters" />
        )}

        {/* Headers */}
        {test.headers && Object.keys(test.headers).length > 0 ? (
          <CollapsibleJson label="Headers" data={test.headers} />
        ) : (
          <EmptySection label="Headers" message="No headers required" />
        )}

        {/* Body */}
        {test.body && Object.keys(test.body).length > 0 ? (
          <CollapsibleJson label="Request Body" data={test.body} />
        ) : (
          <EmptySection label="Request Body" message="No request body" />
        )}

        {/* Assertions */}
        {test.assertions && test.assertions.length > 0 && (
          <CollapsibleJson label="Assertions" data={test.assertions} />
        )}

        {/* Extract & Static Context (setup tests) */}
        {test.extract && Object.keys(test.extract).length > 0 && (
          <CollapsibleJson label="Extract → Runtime Context" data={test.extract} />
        )}
        {test.static_context && Object.keys(test.static_context).length > 0 && (
          <CollapsibleJson label="Static → Runtime Context" data={test.static_context} />
        )}
      </CardContent>
    </Card>
  )
}

function CollapsibleJson({
  label,
  data,
}: {
  label: string
  data: unknown
}) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500 mb-1">{label}</p>
      <div className="rounded-lg bg-slate-900 p-3 overflow-x-auto text-xs">
        <JsonView data={data as object} style={darkStyles} />
      </div>
    </div>
  )
}

function EmptySection({ label, message }: { label: string; message: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500 mb-1">{label}</p>
      <p className="text-xs text-slate-400 italic pl-1">{message}</p>
    </div>
  )
}

export default function TestSuiteDetail() {
  const { suiteId } = useParams<{ suiteId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const [targetUrl, setTargetUrl] = useState("http://localhost:5001")
  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [loopActive, setLoopActive] = useState(false)

  // Poll suite status every 2s while pending/generating
  const { data: suite, isLoading: suiteLoading } = useQuery({
    queryKey: ["test-suite", suiteId],
    queryFn: () => getTestSuite(suiteId!),
    enabled: !!suiteId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "pending" || status === "generating") return 2000
      return false
    },
  })

  // Fetch tests once suite is ready
  const { data: tests, isLoading: testsLoading } = useQuery({
    queryKey: ["tests", suiteId],
    queryFn: () => getTests(suiteId!),
    enabled: suite?.status === "ready",
  })

  // Fetch runs — poll while agentic loop is active
  const { data: runs } = useQuery({
    queryKey: ["runs", suiteId],
    queryFn: () => listRuns(suiteId!),
    enabled: suite?.status === "ready",
    refetchInterval: loopActive ? 3000 : false,
  })

  // Fetch coverage gaps
  const { data: gaps } = useQuery({
    queryKey: ["suite-gaps", suiteId],
    queryFn: () => getSuiteGaps(suiteId!),
    enabled: suite?.status === "ready",
    refetchInterval: loopActive ? 5000 : false,
  })

  // Detect if any run is still in progress
  const hasActiveRun = runs?.some(
    (r) => r.status === "pending" || r.status === "running" || r.status === "analyzing",
  )

  // Auto-stop polling when all runs settle
  if (loopActive && runs && runs.length > 0 && !hasActiveRun) {
    setLoopActive(false)
  }

  const isGenerating =
    suite?.status === "pending" || suite?.status === "generating"

  async function handleRunTests() {
    if (!suiteId || !targetUrl.trim()) return
    setRunLoading(true)
    setRunError(null)
    try {
      await triggerRun(suiteId, { target_base_url: targetUrl.trim() })
      // Start polling for runs — don't navigate, since there's no single run ID
      setLoopActive(true)
      // Invalidate runs to start fetching immediately
      queryClient.invalidateQueries({ queryKey: ["runs", suiteId] })
      queryClient.invalidateQueries({ queryKey: ["suite-gaps", suiteId] })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to trigger run"
      setRunError(msg)
    } finally {
      setRunLoading(false)
    }
  }

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
          <h1 className="text-2xl font-semibold">
            {suite?.name ?? "Test Suite"}
          </h1>
          {suite && (
            <span
              className={`inline-block rounded-full px-3 py-0.5 text-xs font-medium ${STATUS_STYLES[suite.status] ?? "bg-slate-100"}`}
            >
              {suite.status}
            </span>
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

      {suiteLoading ? (
        <p className="text-sm text-slate-500">Loading test suite…</p>
      ) : isGenerating ? (
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-3">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-500" />
              </span>
              Generating tests…
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-500">
              The AI is analyzing your endpoints and generating test cases. This
              typically takes 10–30 seconds depending on the number of endpoints
              and scenarios selected.
            </p>
          </CardContent>
        </Card>
      ) : suite?.status === "error" ? (
        <Card className="max-w-lg border-red-200">
          <CardHeader>
            <CardTitle className="text-base text-red-700">
              Generation Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-500">
              Something went wrong during test generation. Check the backend
              logs for details and try again.
            </p>
          </CardContent>
        </Card>
      ) : suite?.status === "ready" ? (
        <>
          {testsLoading ? (
            <p className="text-sm text-slate-500">Loading tests…</p>
          ) : tests && tests.length > 0 ? (
            <>
              {/* Run Tests panel */}
              <Card className="mb-6">
                <CardContent className="pt-6">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label
                        htmlFor="target-url"
                        className="text-xs font-medium text-slate-500 mb-1 block"
                      >
                        Target Base URL
                      </label>
                      <input
                        id="target-url"
                        type="url"
                        value={targetUrl}
                        onChange={(e) => setTargetUrl(e.target.value)}
                        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        placeholder="http://localhost:5001"
                      />
                    </div>
                    <Button
                      onClick={handleRunTests}
                      disabled={runLoading || !targetUrl.trim() || !!hasActiveRun}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      {runLoading ? "Starting…" : hasActiveRun ? "⏳ Loop Running…" : "▶ Run Tests"}
                    </Button>
                  </div>
                  {runError && (
                    <p className="text-xs text-red-600 mt-2">{runError}</p>
                  )}
                  {(loopActive || hasActiveRun) && (
                    <div className="mt-3 flex items-center gap-2 text-sm text-blue-600">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-500" />
                      </span>
                      Agentic loop is running. Iterations will appear below as they complete.
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Agentic Loop Lineage Tree */}
              {runs && runs.length > 0 && (
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle className="text-base">Run Lineage</CardTitle>
                    <p className="text-xs text-slate-500">
                      Each node is an iteration of the agentic loop. Click a node to view its results.
                    </p>
                  </CardHeader>
                  <CardContent>
                    <RunLineageTree
                      runs={runs}
                      onRunClick={(runId) => navigate(`/runs/${runId}`)}
                    />
                  </CardContent>
                </Card>
              )}

              {/* Coverage Gaps */}
              {gaps && gaps.length > 0 && (
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle className="text-base">
                      Coverage Gaps ({gaps.length})
                    </CardTitle>
                    <p className="text-xs text-slate-500">
                      Untested scenarios identified by the AI across all iterations.
                    </p>
                  </CardHeader>
                  <CardContent>
                    <CoverageGapList gaps={gaps} />
                  </CardContent>
                </Card>
              )}

              <p className="text-sm text-slate-500 mb-6">
                {tests.length} test{tests.length !== 1 ? "s" : ""} generated
              </p>
              <div className="space-y-10">
                {Object.entries(
                  tests.reduce<Record<string, Test[]>>((acc, test) => {
                    const key = `${test.method} ${test.path}`;
                    if (!acc[key]) acc[key] = [];
                    acc[key].push(test);
                    return acc;
                  }, {})
                ).map(([endpoint, endpointTests]) => (
                  <div key={endpoint} className="space-y-4">
                    <h2 className="flex items-center gap-3 border-b pb-2">
                      <span className={`inline-block rounded px-2 py-1 text-xs font-bold uppercase tracking-wider ${METHOD_COLORS[endpoint.split(' ')[0]] ?? "bg-slate-100 text-slate-800"}`}>
                        {endpoint.split(' ')[0]}
                      </span>
                      <code className="text-base font-semibold text-slate-800">
                        {endpoint.split(' ').slice(1).join(' ')}
                      </code>
                      <span className="text-xs font-medium text-slate-400 ml-auto">
                        {endpointTests.length} tests
                      </span>
                    </h2>
                    <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                      {endpointTests.map((test) => (
                        <TestCard key={test.id} test={test} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">No tests generated</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-500">
                  The AI did not produce any valid tests. This may happen if the
                  endpoint schema is too minimal or the LLM response was
                  malformed.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  )
}
