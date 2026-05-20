import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router-dom"

import { getEndpoints } from "@/api/specs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"

const METHOD_COLORS: Record<string, string> = {
  get: "bg-emerald-100 text-emerald-800",
  post: "bg-blue-100 text-blue-800",
  put: "bg-amber-100 text-amber-800",
  patch: "bg-orange-100 text-orange-800",
  delete: "bg-red-100 text-red-800",
  options: "bg-slate-100 text-slate-800",
  head: "bg-purple-100 text-purple-800",
}

export default function EndpointExplorer() {
  const { specId } = useParams<{ specId: string }>()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const { data: endpoints, isLoading } = useQuery({
    queryKey: ["endpoints", specId],
    queryFn: () => getEndpoints(specId!),
    enabled: !!specId,
  })

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
        <Card>
          <CardContent className="p-0">
            <table className="w-full" id="endpoints-table">
              <thead>
                <tr className="border-b text-left text-sm text-slate-500">
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
                    className="border-b last:border-b-0 hover:bg-slate-50 transition-colors"
                  >
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
          <span key={method} className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${cls}`}>
            {method}
          </span>
        ))}
      </div>
    </div>
  )
}
