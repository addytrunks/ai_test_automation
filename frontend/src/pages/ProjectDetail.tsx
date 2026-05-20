import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"

import { getProject, getSpecs, uploadSpec } from "@/api/specs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/hooks/useAuthStore"

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [file, setFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  })

  const { data: specs, isLoading: specsLoading } = useQuery({
    queryKey: ["specs", projectId],
    queryFn: () => getSpecs(projectId!),
    enabled: !!projectId,
  })

  const uploadMutation = useMutation({
    mutationFn: (f: File) => uploadSpec(projectId!, f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["specs", projectId] })
      setFile(null)
      setUploadError(null)
      // Reset the file input
      const input = document.getElementById("spec-file-input") as HTMLInputElement | null
      if (input) input.value = ""
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Upload failed"
      setUploadError(msg)
    },
  })

  if (projectLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-8">
        <p className="text-sm text-slate-500">Loading project…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-slate-400 hover:text-slate-600 transition-colors">
            ← Back
          </Link>
          <h1 className="text-2xl font-semibold">{project?.name}</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-600">{user?.email}</span>
          <Button
            variant="outline"
            onClick={() => {
              logout()
              window.location.href = "/login"
            }}
          >
            Log out
          </Button>
        </div>
      </header>

      {/* Project info */}
      {project?.description && (
        <p className="text-sm text-slate-600 mb-6">{project.description}</p>
      )}
      {project?.target_base_url && (
        <p className="text-xs text-slate-400 mb-6">
          Base URL: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{project.target_base_url}</code>
        </p>
      )}

      {/* Upload spec */}
      <Card className="mb-8 max-w-lg">
        <CardHeader>
          <CardTitle>Upload OpenAPI Spec</CardTitle>
          <CardDescription>Upload a JSON or YAML OpenAPI 3.x specification file.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="spec-file-input">Spec File</Label>
              <Input
                id="spec-file-input"
                type="file"
                accept=".json,.yaml,.yml"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null)
                  setUploadError(null)
                }}
              />
            </div>
            {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
            <Button
              id="upload-spec-btn"
              onClick={() => file && uploadMutation.mutate(file)}
              disabled={!file || uploadMutation.isPending}
            >
              {uploadMutation.isPending ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Specs list */}
      <h2 className="text-lg font-semibold mb-4">Specs</h2>
      {specsLoading ? (
        <p className="text-sm text-slate-500">Loading specs…</p>
      ) : specs && specs.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {specs.map((spec) => (
            <Card key={spec.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  Version {spec.version}
                </CardTitle>
                <CardDescription>
                  Parsed {new Date(spec.parsed_at).toLocaleString()}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Link
                  id={`spec-endpoints-${spec.id}`}
                  to={`/specs/${spec.id}/endpoints`}
                >
                  <Button variant="outline" size="sm" className="w-full">
                    View Endpoints
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No specs uploaded</CardTitle>
            <CardDescription>
              Upload an OpenAPI spec above to extract and view endpoints.
            </CardDescription>
          </CardHeader>
        </Card>
      )}
    </div>
  )
}
