export const PRINT_HINT_KEY = "hkn:print-hint:v1"

export function usePrintHintOpen() {
  return useState("print:hint-open", () => false)
}

/**
 * Opens the browser print dialog. On first use (per browser profile) a one-time
 * reminder modal is shown instead: Chromium's "user margins"/"background
 * graphics" dialog settings override the document's CSS @page rules.
 */
export function askPrint() {
  if (import.meta.server) {
    window.print()
    return
  }
  try {
    if (localStorage.getItem(PRINT_HINT_KEY) === "1") {
      window.print()
      return
    }
  } catch {
    /* storage unavailable — still show the printable hint */
  }
  usePrintHintOpen().value = true
}

export function ackPrintHint() {
  try {
    localStorage.setItem(PRINT_HINT_KEY, "1")
  } catch {
    /* ignore */
  }
}
