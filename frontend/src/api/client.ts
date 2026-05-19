import axios, { type AxiosInstance } from "axios"

const API_BASE = "http://localhost:8000/api/v1"

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token")
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        window.location.href = "/login"
      }
    }
    return Promise.reject(error)
  },
)
