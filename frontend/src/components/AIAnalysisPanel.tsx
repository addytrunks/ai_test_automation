import { useQuery } from "@tanstack/react-query"

import { getAnalysis } from "@/api/runner"
import type { AIAnalysis } from "@/api/types"

export default function AIAnalysisPanel({
  resultId,
  isRunAnalyzing,
}: {
  resultId: string
  isRunAnalyzing: boolean
}) {
  const { data: analysis, isLoading } = useQuery<AIAnalysis>({
    queryKey: ["analysis", resultId],
    queryFn: () => getAnalysis(resultId),
    // Poll every 3s while run is still analyzing
    refetchInterval: isRunAnalyzing ? 3000 : false,
    // The backend returns 404 while analysis is pending — suppress error
    retry: false,
  })

  if (isLoading || (!analysis && isRunAnalyzing)) {
    return (
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-amber-500" />
          </span>
          <span className="text-sm font-medium text-amber-800">
            AI is analyzing this failure…
          </span>
        </div>
      </div>
    )
  }

  if (!analysis) return null

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
        AI Failure Analysis
      </h4>

      <div>
        <p className="text-xs font-medium text-slate-500 mb-1">What happened</p>
        <p className="text-sm text-slate-800">{analysis.explanation}</p>
      </div>

      <div>
        <p className="text-xs font-medium text-slate-500 mb-1">Likely cause</p>
        <p className="text-sm text-red-700 font-medium">{analysis.likely_cause}</p>
      </div>

      <div>
        <p className="text-xs font-medium text-slate-500 mb-1">Suggested fix</p>
        <p className="text-sm text-emerald-700">{analysis.suggested_fix}</p>
      </div>
    </div>
  )
}
