import { useCallback, useMemo } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import type { Run } from "@/api/types"

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  pending: { bg: "#f8fafc", border: "#94a3b8", text: "#475569" },
  running: { bg: "#eff6ff", border: "#3b82f6", text: "#1d4ed8" },
  analyzing: { bg: "#fffbeb", border: "#f59e0b", text: "#b45309" },
  completed: { bg: "#f0fdf4", border: "#22c55e", text: "#15803d" },
  error: { bg: "#fef2f2", border: "#ef4444", text: "#b91c1c" },
}

function buildRunLabel(run: Run): string {
  const iteration = `Iteration ${run.loop_iteration}`
  if (run.summary) {
    return `${iteration}\n✅ ${run.summary.passed} / ❌ ${run.summary.failed}`
  }
  return `${iteration}\n${run.status}`
}

interface RunLineageTreeProps {
  runs: Run[]
  onRunClick?: (runId: string) => void
}

export default function RunLineageTree({ runs, onRunClick }: RunLineageTreeProps) {
  const { nodes, edges } = useMemo(() => {
    // Sort by iteration
    const sorted = [...runs].sort((a, b) => a.loop_iteration - b.loop_iteration)

    const nodes: Node[] = sorted.map((run, i) => {
      const colors = STATUS_COLORS[run.status] ?? STATUS_COLORS.pending
      return {
        id: run.id,
        position: { x: 0, y: i * 120 },
        data: { label: buildRunLabel(run) },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        style: {
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          color: colors.text,
          borderRadius: "12px",
          padding: "12px 20px",
          fontSize: "13px",
          fontWeight: 600,
          whiteSpace: "pre-line" as const,
          textAlign: "center" as const,
          minWidth: "180px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          cursor: "pointer",
        },
      }
    })

    const edges: Edge[] = sorted
      .filter((run) => run.parent_run_id)
      .map((run) => ({
        id: `${run.parent_run_id}-${run.id}`,
        source: run.parent_run_id!,
        target: run.id,
        animated: run.status === "running" || run.status === "analyzing",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#94a3b8", strokeWidth: 2 },
      }))

    return { nodes, edges }
  }, [runs])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRunClick?.(node.id)
    },
    [onRunClick],
  )

  if (runs.length === 0) return null

  return (
    <div style={{ height: Math.max(200, runs.length * 120 + 80), width: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#e2e8f0" gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
