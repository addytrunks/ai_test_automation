import { Navigate, Route, Routes } from "react-router-dom"

import { AuthRoute } from "@/components/AuthRoute"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import Dashboard from "@/pages/Dashboard"
import EndpointExplorer from "@/pages/EndpointExplorer"
import Login from "@/pages/Login"
import ProjectDetail from "@/pages/ProjectDetail"
import Register from "@/pages/Register"
import TestSuiteDetail from "@/pages/TestSuiteDetail"

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<AuthRoute><Login /></AuthRoute>} />
      <Route path="/register" element={<AuthRoute><Register /></AuthRoute>} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId"
        element={
          <ProtectedRoute>
            <ProjectDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/specs/:specId/endpoints"
        element={
          <ProtectedRoute>
            <EndpointExplorer />
          </ProtectedRoute>
        }
      />
      <Route
        path="/test-suites/:suiteId"
        element={
          <ProtectedRoute>
            <TestSuiteDetail />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
