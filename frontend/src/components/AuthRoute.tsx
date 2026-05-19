import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"

import { useAuthStore } from "@/hooks/useAuthStore"

interface Props {
  children: ReactNode
}

export function AuthRoute({ children }: Props) {
  const token = useAuthStore((s) => s.token)

  // If the user already has a token, they shouldn't be on the login/register page
  if (token) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
