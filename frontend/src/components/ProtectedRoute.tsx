import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"

import { getMe } from "@/api/auth"
import { useAuthStore } from "@/hooks/useAuthStore"

interface Props {
  children: ReactNode
}

export function ProtectedRoute({ children }: Props) {
  const token = useAuthStore((s) => s.token)
  const setUser = useAuthStore((s) => s.setUser)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: !!token,
    retry: false,
  })

  if (!token) return <Navigate to="/login" replace />

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }

  if (isError || !data) return <Navigate to="/login" replace />

  // hydrate store
  if (!useAuthStore.getState().user) {
    setUser(data)
  }

  return <>{children}</>
}
