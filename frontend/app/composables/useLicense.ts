/** License state from /api/license/status (offline validation, see backend). */
export interface LicenseStatus {
  active: boolean
  reason: string
  clinic: string | null
  dentist: string | null
  issued_at: string | null
  installation_id: string
}

export function useLicense() {
  const status = useState<LicenseStatus | null>("license.status", () => null)
  const loading = useState<boolean>("license.loading", () => false)

  async function fetchStatus(force = false) {
    if (status.value && !force) return status.value
    loading.value = true
    const api = useApi()
    try {
      status.value = await api.get<LicenseStatus>("/license/status")
    }
    catch {
      // Unknown state: do not brick on a transient failure; retried next boot.
      status.value = null
    }
    finally {
      loading.value = false
    }
    return status.value
  }

  async function installContent(content: string) {
    const api = useApi()
    const data = await api.post<LicenseStatus>("/license/install", { content })
    status.value = data
    return data
  }

  const locked = computed(() => status.value !== null && !status.value.active)

  return { status, loading, locked, fetchStatus, installContent }
}
