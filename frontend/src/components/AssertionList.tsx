import type { AssertionResult } from "@/api/types"

function formatAssertion(a: AssertionResult): string {
  const { assertion } = a
  switch (assertion.type) {
    case "status_eq":
      return `Status = ${assertion.expected}`
    case "status_in":
      return `Status in [${(assertion.expected as number[])?.join(", ")}]`
    case "json_path":
      return assertion.op === "eq"
        ? `${assertion.target} = ${JSON.stringify(assertion.expected)}`
        : `${assertion.target} exists`
    case "body_contains":
      return `Body contains "${assertion.expected}"`
    case "body_not_contains":
      return `Body does not contain "${assertion.expected}"`
    case "header_eq":
      return `Header ${assertion.target} = "${assertion.expected}"`
    case "response_time_lt":
      return `Response time < ${assertion.expected}ms`
    default:
      return `${assertion.type}: ${JSON.stringify(assertion.expected)}`
  }
}

export default function AssertionList({
  results,
}: {
  results: AssertionResult[]
}) {
  if (results.length === 0) return null

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-slate-500 mb-2">Assertions</p>
      {results.map((a, i) => (
        <div
          key={i}
          className={`flex items-start gap-2 rounded-md px-3 py-2 text-xs ${
            a.passed
              ? "bg-emerald-50 text-emerald-800"
              : "bg-red-50 text-red-800"
          }`}
        >
          <span className="mt-0.5 flex-shrink-0">
            {a.passed ? "✅" : "❌"}
          </span>
          <div className="min-w-0">
            <span className="font-medium">{formatAssertion(a)}</span>
            {!a.passed && a.actual !== undefined && (
              <span className="block text-red-600 mt-0.5">
                Got: {JSON.stringify(a.actual)}
              </span>
            )}
            {a.error && (
              <span className="block text-red-500 mt-0.5 italic">
                {a.error}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
