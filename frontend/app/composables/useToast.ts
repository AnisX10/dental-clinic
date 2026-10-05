/** App-wide toasts: success/error feedback with auto-dismiss. RTL-aware via CSS. */
export interface Toast {
  id: number
  kind: "success" | "error"
  messageKey: string
}

let _nextId = 1

export function useToast() {
  // useState must live inside the composable (setup context), not module scope.
  const toasts = useState<Toast[]>("clinic-toasts", () => [])

  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function push(kind: Toast["kind"], messageKey: string) {
    const id = _nextId++
    toasts.value = [...toasts.value.slice(-3), { id, kind, messageKey }]
    setTimeout(() => dismiss(id), 4000)
  }

  return {
    toasts,
    success: (key: string) => push("success", key),
    error: (key: string) => push("error", key),
    dismiss,
  }
}
