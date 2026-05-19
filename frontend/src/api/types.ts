export interface User {
  id: string
  email: string
  name: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
}

export interface RegisterPayload {
  email: string
  password: string
  name?: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface ApiError {
  detail: string
}
