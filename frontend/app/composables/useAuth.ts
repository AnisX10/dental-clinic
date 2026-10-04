/** Current-user session state backed by /api/auth/me (httpOnly cookie session). */
export interface ClinicUser {
  id: number
  username: string
  full_name: string
  role: string
  is_owner: boolean
}

export function useAuth() {
  const user = useState<ClinicUser | null>("auth.user", () => null)
  const loaded = useState<boolean>("auth.loaded", () => false)

  async function fetchMe(force = false) {
    if (loaded.value && !force) return user.value
    const api = useApi()
    try {
      const data = await api.get<{ user: ClinicUser }>("/auth/me")
      user.value = data.user
    }
    catch {
      user.value = null
    }
    finally {
      loaded.value = true
    }
    return user.value
  }

  async function login(username: string, password: string) {
    const api = useApi()
    const data = await api.post<{ user: ClinicUser }>("/auth/login", { username, password })
    user.value = data.user
    loaded.value = true
    return data.user
  }

  async function logout() {
    const api = useApi()
    try {
      await api.post("/auth/logout")
    }
    finally {
      user.value = null
      loaded.value = true
    }
    await navigateTo("/login")
  }

  return { user, loaded, fetchMe, login, logout }
}
