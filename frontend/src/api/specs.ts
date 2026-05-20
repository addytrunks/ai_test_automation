import { apiClient } from "./client"
import type {
  Endpoint,
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  Spec,
} from "./types"

export async function createProject(payload: ProjectCreatePayload): Promise<Project> {
  const { data } = await apiClient.post<Project>("/projects", payload)
  return data
}

export async function getProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>("/projects")
  return data
}

export async function getProject(projectId: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${projectId}`)
  return data
}

export async function updateProject(
  projectId: string,
  payload: ProjectUpdatePayload,
): Promise<Project> {
  const { data } = await apiClient.patch<Project>(`/projects/${projectId}`, payload)
  return data
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}`)
}

export async function uploadSpec(projectId: string, file: File): Promise<Spec> {
  const formData = new FormData()
  formData.append("file", file)
  const { data } = await apiClient.post<Spec>(`/projects/${projectId}/specs`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return data
}

export async function getSpecs(projectId: string): Promise<Spec[]> {
  const { data } = await apiClient.get<Spec[]>(`/projects/${projectId}/specs`)
  return data
}

export async function getEndpoints(specId: string): Promise<Endpoint[]> {
  const { data } = await apiClient.get<Endpoint[]>(`/specs/${specId}/endpoints`)
  return data
}
