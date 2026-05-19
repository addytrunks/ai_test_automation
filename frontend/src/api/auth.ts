import axios from "axios"

import { apiClient } from "./client"
import type { LoginPayload, RegisterPayload, TokenResponse, User } from "./types"

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/register", payload)
  return data
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  // FastAPI's OAuth2PasswordRequestForm uses form-urlencoded
  const body = new URLSearchParams()
  body.set("username", payload.email)
  body.set("password", payload.password)
  const { data } = await axios.post<TokenResponse>(
    "http://localhost:8000/api/v1/auth/login",
    body,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  )
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me")
  return data
}
