/**
 * Thin fetch wrapper around the clinic API.
 * - JSON in/out, throws ApiError with message_key for the UI to translate.
 * - 401 clears the auth state (session cookie expired/revoked).
 */
export class ApiError extends Error {
  status: number
  code: string
  messageKey: string
  values: Record<string, string> | null

  constructor(
    status: number,
    code: string,
    messageKey: string,
    values: Record<string, string> | null,
  ) {
    super(`${status} ${code}`)
    this.status = status
    this.code = code
    this.messageKey = messageKey
    this.values = values
  }
}

interface ApiOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | undefined>
}

export function useApi() {
  async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
    const { method = "GET", body, query } = options
    const qs = query
      ? "?" + new URLSearchParams(
          Object.entries(query)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)]),
        ).toString()
      : ""
    let resp: Response
    try {
      resp = await fetch(`/api${path}`, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        credentials: "include",
      })
    }
    catch {
      throw new ApiError(0, "network", "errors.network", null)
    }
    if (resp.status === 204) return undefined as T
    let data: any = null
    try {
      data = await resp.json()
    }
    catch {
      // non-JSON response body
    }
    if (!resp.ok) {
      const err = data?.error ?? {}
      const code = typeof err.code === "string" ? err.code : "generic"
      const messageKey = typeof err.message_key === "string" ? err.message_key : "errors.generic"
      if (resp.status === 401) {
        const auth = useAuth()
        auth.user.value = null
        auth.loaded.value = true
      }
      throw new ApiError(resp.status, code, messageKey, err.values ?? null)
    }
    return data as T
  }

  return {
    get: <T>(path: string, query?: ApiOptions["query"]) => request<T>(path, { query }),
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
    put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
    del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
    upload: <T>(path: string, file: File) => {
      const form = new FormData()
      form.append("file", file)
      return fetch(`/api${path}`, { method: "POST", body: form, credentials: "include" })
        .then(async (resp) => {
          const data = resp.headers.get("content-type")?.includes("application/json")
            ? await resp.json().catch(() => null)
            : null
          if (!resp.ok) {
            const err = data?.error ?? {}
            throw new ApiError(
              resp.status,
              err.code ?? "generic",
              err.message_key ?? "errors.generic",
              err.values ?? null,
            )
          }
          return data as T
        })
        .catch((e) => {
          if (e instanceof ApiError) throw e
          throw new ApiError(0, "network", "errors.network", null)
        })
    },
  }
}
