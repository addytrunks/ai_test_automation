import { useQuery } from "@tanstack/react-query"
import { useParams } from "react-router-dom"
import { JsonView, darkStyles } from "react-json-view-lite"
import "react-json-view-lite/dist/index.css"

import { getTestSuite, getTests } from "@/api/generator"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"
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
            className={`inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase ${METHOD_COLORS[test.method] ?? "bg-slate-100 text-slate-800"}`}
          >
            {test.method}
          </span>
          <code className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
            {test.path}
          </code>
          <span
            className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${SCENARIO_COLORS[test.scenario_type] ?? "bg-slate-100 text-slate-700"}`}
          >
            {test.scenario_type.replace("_", " ")}
          </span>
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
        {test.path_params && Object.keys(test.path_params).length > 0 && (
          <CollapsibleJson label="Path Params" data={test.path_params} />
        )}

        {/* Query params */}
        {test.query_params && Object.keys(test.query_params).length > 0 && (
          <CollapsibleJson label="Query Params" data={test.query_params} />
        )}

        {/* Headers */}
        {test.headers && Object.keys(test.headers).length > 0 && (
          <CollapsibleJson label="Headers" data={test.headers} />
        )}

        {/* Body */}
        {test.body && Object.keys(test.body).length > 0 && (
          <CollapsibleJson label="Request Body" data={test.body} />
        )}

        {/* Assertions */}
        {test.assertions && test.assertions.length > 0 && (
          <CollapsibleJson label="Assertions" data={test.assertions} />
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

export default function TestSuiteDetail() {
  const { suiteId } = useParams<{ suiteId: string }>()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

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

  const isGenerating =
    suite?.status === "pending" || suite?.status === "generating"

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
              <p className="text-sm text-slate-500 mb-4">
                {tests.length} test{tests.length !== 1 ? "s" : ""} generated
              </p>
              <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                {tests.map((test) => (
                  <TestCard key={test.id} test={test} />
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
