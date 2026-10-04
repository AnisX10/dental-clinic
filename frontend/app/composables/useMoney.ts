/** DZD money display: tabular figures, non-breaking space groupings, DA suffix. */
export function useMoney() {
  const { t } = useI18n()

  function fmt(value: string | number): string {
    const num = typeof value === "string" ? Number.parseFloat(value) : value
    if (!Number.isFinite(num)) return "—"
    const fixed = num.toFixed(2)
    const [int = "0", dec = "00"] = fixed.split(".")
    const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f")
    const trimmedDec = dec === "00" ? "" : `.${dec}`
    return `${grouped}${trimmedDec} ${t("common.currency_da")}`
  }

  return { fmt }
}
