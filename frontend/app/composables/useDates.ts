/** Date/time formatting helpers pinned to Africa/Algiers (locale-aware, no deps). */
const TZ = "Africa/Algiers"

export function useDates() {
  function fmtDate(iso: string | null | undefined): string {
    if (!iso) return "—"
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleDateString("fr-DZ", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: TZ })
  }

  function fmtDateTime(iso: string | null | undefined): string {
    if (!iso) return "—"
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return `${fmtDate(iso)} ${d.toLocaleTimeString("fr-DZ", { hour: "2-digit", minute: "2-digit", timeZone: TZ })}`
  }

  function fmtTime(iso: string | null | undefined): string {
    if (!iso) return "—"
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleTimeString("fr-DZ", { hour: "2-digit", minute: "2-digit", timeZone: TZ })
  }

  function todayIso(): string {
    const parts = new Intl.DateTimeFormat("en-CA", {
      year: "numeric", month: "2-digit", day: "2-digit", timeZone: TZ,
    }).format(new Date())
    return parts // en-CA gives YYYY-MM-DD
  }

  function weekdayLong(isoDate: string): string {
    const d = new Date(`${isoDate}T12:00:00Z`)
    return d.toLocaleDateString("fr-DZ", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
  }

  return { fmtDate, fmtDateTime, fmtTime, todayIso, weekdayLong }
}
