import type { CoverageGap, Endpoint } from "@/api/types"

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-800 border-red-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-slate-100 text-slate-700 border-slate-200",
}

const SEVERITY_ICON: Record<string, string> = {
  high: "🔴",
  medium: "🟡",
  low: "⚪",
}

interface CoverageGapListProps {
  gaps: CoverageGap[]
  endpoints?: Endpoint[]
}

export default function CoverageGapList({ gaps, endpoints }: CoverageGapListProps) {
  if (gaps.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center">
        <p className="text-sm text-slate-500">No coverage gaps identified</p>
        <p className="text-xs text-slate-400 mt-1">
          The AI found no untested scenarios for the endpoints in scope.
        </p>
      </div>
    )
  }

  const endpointMap = new Map<string, Endpoint>()
  endpoints?.forEach((ep) => endpointMap.set(ep.id, ep))

  return (
    <div className="space-y-2">
      {gaps.map((gap) => {
        const ep = endpointMap.get(gap.endpoint_id)
        return (
          <div
            key={gap.id}
            className={`rounded-lg border p-3 ${SEVERITY_STYLES[gap.severity] ?? SEVERITY_STYLES.low}`}
          >
            <div className="flex items-start gap-2">
              <span className="text-sm flex-shrink-0 mt-0.5">
                {SEVERITY_ICON[gap.severity] ?? "⚪"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-snug">
                  {gap.scenario_description}
                </p>
                {ep && (
                  <p className="text-xs opacity-75 mt-1 font-mono">
                    {ep.method.toUpperCase()} {ep.path}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    {gap.severity}
                  </span>
                  {gap.spawned_test_id && (
                    <span className="text-xs opacity-75">
                      → test generated
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
