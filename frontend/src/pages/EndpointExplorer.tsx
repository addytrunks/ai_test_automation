import { useMutation, useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { createTestSuite } from "@/api/generator"
import { apiClient } from "@/api/client"
import { getEndpoints } from "@/api/specs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/hooks/useAuthStore"
import type { Endpoint } from "@/api/types"

const METHOD_COLORS: Record<string, string> = {
  get: "bg-emerald-100 text-emerald-800",
  post: "bg-blue-100 text-blue-800",
  put: "bg-amber-100 text-amber-800",
  patch: "bg-orange-100 text-orange-800",
  delete: "bg-red-100 text-red-800",
  options: "bg-slate-100 text-slate-800",
  head: "bg-purple-100 text-purple-800",
}

// --- Guardrail helpers ---

function hasPathParams(ep: Endpoint): boolean {
  return /\{[^}]+\}/.test(ep.path)
}

function hasRequestBody(ep: Endpoint): boolean {
  return !!ep.request_body && ["post", "put", "patch"].includes(ep.method)
}

function hasInputs(ep: Endpoint): boolean {
  return hasRequestBody(ep) || (ep.parameters ?? []).length > 0
}

function hasAuth(ep: Endpoint): boolean {
  // Check explicit security field from OpenAPI
  if (ep.security && ep.security.length > 0) return true
  // Fallback: check if any parameter is named Authorization
  for (const p of ep.parameters ?? []) {
    if (typeof p === "object" && (p as Record<string, unknown>).name === "Authorization") return true
  }
  return false
}

interface ScenarioRule {
  value: string
  label: string
  description: string
  /** Returns null if valid, or a reason string if disabled */
  check: (endpoints: Endpoint[]) => string | null
}

const SCENARIO_RULES: ScenarioRule[] = [
  {
    value: "positive",
    label: "Positive",
    description: "Valid inputs, happy path",
    check: (eps) => {
      const allLackInputs = eps.every((ep) => !hasInputs(ep))
      return allLackInputs
        ? "No selected endpoint has documented parameters or request body"
        : null
    },
  },
  {
    value: "negative",
    label: "Negative",
    description: "Invalid inputs, error handling",
    check: () => null, // always valid
  },
  {
    value: "auth_bypass",
    label: "Auth Bypass",
    description: "Missing/invalid auth",
    check: (eps) => {
      const anyAuth = eps.some(hasAuth)
      return anyAuth ? null : "No selected endpoint has a security requirement"
    },
  },
  {
    value: "bola",
    label: "BOLA",
    description: "Broken object-level authorization",
    check: (eps) => {
      const anyWithParam = eps.some(hasPathParams)
      const anyAuth = eps.some(hasAuth)
      if (!anyWithParam) return "No selected endpoint has a path parameter like {id}"
      if (!anyAuth) return "No selected endpoint has a security requirement"
      return null
    },
  },
  {
    value: "boundary",
    label: "Boundary",
    description: "Edge values, limits",
    check: (eps) => {
      const any = eps.some(hasInputs)
      return any ? null : "No selected endpoint has parameters or a request body"
    },
  },
  {
    value: "injection",
    label: "Injection",
    description: "SQL/NoSQL/XSS payloads",
    check: (eps) => {
      const any = eps.some(hasInputs)
      return any ? null : "No selected endpoint has parameters or a request body to inject into"
    },
  },
  {
    value: "mass_assignment",
    label: "Mass Assignment",
    description: "Extra fields in body",
    check: (eps) => {
      const any = eps.some(hasRequestBody)
      return any ? null : "No selected endpoint accepts a request body (POST/PUT/PATCH)"
    },
  },
  {
    value: "rate_limiting",
    label: "Rate Limiting",
    description: "Brute-force / rate-limit on login",
    check: (eps) => {
      const anyLogin = eps.some(
        (ep) =>
          ep.method === "post" &&
          /login|auth|token|signin|sessions/i.test(ep.path),
      )
      return anyLogin
        ? null
        : "No selected endpoint is a login/auth POST endpoint"
    },
  },
]

export default function EndpointExplorer() {
  const { specId } = useParams<{ specId: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [selectedScenarios, setSelectedScenarios] = useState<Set<string>>(
    new Set(["positive", "negative"]),
  )
  const [suiteName, setSuiteName] = useState("")
  const [generateError, setGenerateError] = useState<string | null>(null)

  const { data: endpoints, isLoading } = useQuery({
    queryKey: ["endpoints", specId],
    queryFn: () => getEndpoints(specId!),
    enabled: !!specId,
  })

  // Look up project_id by finding which project owns this spec
  const { data: projectIdFromSpec } = useQuery({
    queryKey: ["projectId-from-spec", specId],
    queryFn: async () => {
      // Get all projects and find which one owns this spec
      const { data: projects } = await apiClient.get<
        { id: string; name: string }[]
      >("/projects")
      for (const project of projects) {
        const { data: specs } = await apiClient.get<{ id: string }[]>(
          `/projects/${project.id}/specs`,
        )
        if (specs.some((s) => s.id === specId)) {
          return project.id
        }
      }
      return null
    },
    enabled: !!specId,
    staleTime: Infinity,
  })

  // Compute which scenarios are valid based on selected endpoints
  const selectedEndpoints = useMemo(() => {
    if (!endpoints) return []
    return endpoints.filter((ep) => selectedIds.has(ep.id))
  }, [endpoints, selectedIds])

  const scenarioStates = useMemo(() => {
    return SCENARIO_RULES.map((rule) => ({
      ...rule,
      disabledReason: selectedEndpoints.length > 0 ? rule.check(selectedEndpoints) : null,
    }))
  }, [selectedEndpoints])

  const toggleEndpoint = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (!endpoints) return
    if (selectedIds.size === endpoints.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(endpoints.map((ep) => ep.id)))
    }
  }

  const toggleScenario = (value: string) => {
    setSelectedScenarios((prev) => {
      const next = new Set(prev)
      if (next.has(value)) next.delete(value)
      else next.add(value)
      return next
    })
  }

  // Auto-deselect scenarios that become disabled when endpoints change
  useMemo(() => {
    const invalidSelected = scenarioStates
      .filter((s) => s.disabledReason && selectedScenarios.has(s.value))
      .map((s) => s.value)
    if (invalidSelected.length > 0) {
      setSelectedScenarios((prev) => {
        const next = new Set(prev)
        for (const v of invalidSelected) next.delete(v)
        return next
      })
    }
  }, [scenarioStates])

  const generateMutation = useMutation({
    mutationFn: () => {
      if (!projectIdFromSpec || !specId) {
        throw new Error("Project not found")
      }
      return createTestSuite(projectIdFromSpec, {
        name: suiteName || `Test Suite — ${new Date().toLocaleString()}`,
        spec_id: specId,
        endpoint_ids: Array.from(selectedIds),
        scenarios: Array.from(selectedScenarios),
      })
    },
    onSuccess: (suite) => {
      navigate(`/test-suites/${suite.id}`)
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail ?? "Generation failed"
      setGenerateError(msg)
    },
  })

  const canGenerate =
    selectedIds.size > 0 &&
    selectedScenarios.size > 0 &&
    !!projectIdFromSpec &&
    !generateMutation.isPending

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
          <h1 className="text-2xl font-semibold">Endpoints</h1>
          {endpoints && (
            <span className="text-sm text-slate-400 mt-1">
              ({endpoints.length} endpoint{endpoints.length !== 1 ? "s" : ""})
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

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading endpoints…</p>
      ) : endpoints && endpoints.length > 0 ? (
        <>
          {/* Endpoints table with checkboxes */}
          <Card className="mb-6">
            <CardContent className="p-0">
              <table className="w-full" id="endpoints-table">
                <thead>
                  <tr className="border-b text-left text-sm text-slate-500">
                    <th className="px-4 py-3 w-12">
                      <input
                        type="checkbox"
                        id="select-all-endpoints"
                        checked={selectedIds.size === endpoints.length}
                        onChange={toggleAll}
                        className="rounded border-slate-300 accent-slate-900"
                      />
                    </th>
                    <th className="px-4 py-3 w-24">Method</th>
                    <th className="px-4 py-3">Path</th>
                    <th className="px-4 py-3">Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.map((ep) => (
                    <tr
                      key={ep.id}
                      id={`endpoint-${ep.id}`}
                      className={`border-b last:border-b-0 transition-colors cursor-pointer ${selectedIds.has(ep.id)
                          ? "bg-blue-50/60"
                          : "hover:bg-slate-50"
                        }`}
                      onClick={() => toggleEndpoint(ep.id)}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(ep.id)}
                          onChange={() => toggleEndpoint(ep.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="rounded border-slate-300 accent-slate-900"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase ${METHOD_COLORS[ep.method] ?? "bg-slate-100 text-slate-800"}`}
                        >
                          {ep.method}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-sm">{ep.path}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {ep.summary ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Generation panel */}
          {selectedIds.size > 0 && (
            <Card className="mb-6 max-w-2xl">
              <CardHeader>
                <CardTitle className="text-base">Generate Test Suite</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Suite name */}
                <div className="space-y-1">
                  <Label htmlFor="suite-name">Suite Name (optional)</Label>
                  <Input
                    id="suite-name"
                    placeholder="e.g. Smoke Tests, Security Audit"
                    value={suiteName}
                    onChange={(e) => setSuiteName(e.target.value)}
                  />
                </div>

                {/* Scenario selection with guardrails */}
                <div className="space-y-2">
                  <Label>Scenario Types</Label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {scenarioStates.map((scenario) => {
                      const isDisabled = !!scenario.disabledReason
                      return (
                        <label
                          key={scenario.value}
                          title={scenario.disabledReason ?? undefined}
                          className={`flex items-start gap-2 rounded-lg border p-3 transition-colors ${isDisabled
                              ? "border-slate-100 bg-slate-50/50 cursor-not-allowed opacity-50"
                              : selectedScenarios.has(scenario.value)
                                ? "border-slate-900 bg-slate-50 cursor-pointer"
                                : "border-slate-200 hover:border-slate-300 cursor-pointer"
                            }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedScenarios.has(scenario.value)}
                            disabled={isDisabled}
                            onChange={() => toggleScenario(scenario.value)}
                            className="mt-0.5 rounded border-slate-300 accent-slate-900"
                          />
                          <div>
                            <div className="text-sm font-medium">
                              {scenario.label}
                            </div>
                            <div className="text-xs text-slate-500">
                              {isDisabled ? scenario.disabledReason : scenario.description}
                            </div>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </div>

                {/* Summary + Generate */}
                <div className="flex items-center justify-between pt-2 border-t">
                  <p className="text-sm text-slate-600">
                    {selectedIds.size} endpoint{selectedIds.size !== 1 ? "s" : ""}{" "}
                    × {selectedScenarios.size} scenario
                    {selectedScenarios.size !== 1 ? "s" : ""}
                  </p>
                  <Button
                    id="generate-tests-btn"
                    onClick={() => generateMutation.mutate()}
                    disabled={!canGenerate}
                  >
                    {generateMutation.isPending
                      ? "Creating…"
                      : "Generate Tests"}
                  </Button>
                </div>
                {generateError && (
                  <p className="text-sm text-red-600">{generateError}</p>
                )}
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No endpoints found</CardTitle>
          </CardHeader>
        </Card>
      )}

      {/* Legend */}
      <div className="mt-6 flex flex-wrap gap-2">
        {Object.entries(METHOD_COLORS).map(([method, cls]) => (
          <span
            key={method}
            className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${cls}`}
          >
            {method}
          </span>
        ))}
      </div>
    </div>
  )
}
