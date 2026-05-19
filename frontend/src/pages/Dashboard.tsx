import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/hooks/useAuthStore"

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <header className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">API Test Platform</h1>
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

      <Card>
        <CardHeader>
          <CardTitle>Welcome, {user?.name ?? user?.email}</CardTitle>
          <CardDescription>
            Projects, specs, and test suites will live here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            This dashboard is currently a placeholder. Authentication is fully wired up — you reached
            this page because your JWT was valid.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
