import { create } from "zustand"

import type { User } from "@/api/types"

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (token: string, user: User) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: typeof window !== "undefined" ? localStorage.getItem("access_token") : null,
  setAuth: (token, user) => {
    localStorage.setItem("access_token", token)
    set({ token, user })
  },
  setUser: (user) => set({ user }),
  logout: () => {
    localStorage.removeItem("access_token")
    set({ token: null, user: null })
  },
}))
