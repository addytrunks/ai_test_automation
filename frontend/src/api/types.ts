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

export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  target_base_url: string | null
  created_at: string
}

export interface Spec {
  id: string
  project_id: string
  version: string
  parsed_at: string
  created_at: string
}

export interface Endpoint {
  id: string
  spec_id: string
  method: string
  path: string
  summary: string | null
  parameters: Record<string, unknown>[] | null
  request_body: Record<string, unknown> | null
  responses: Record<string, unknown> | null
}

export interface ProjectCreatePayload {
  name: string
  description?: string
  target_base_url?: string
}

export interface ProjectUpdatePayload {
  name?: string
  description?: string
  target_base_url?: string
}
