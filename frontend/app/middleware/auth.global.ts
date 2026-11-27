/**
 * Global guards. Without a valid licence the app stays usable READ-ONLY (the
 * clinic must always reach its own records and backups): pages stay open, a
 * banner explains the situation, and any save is refused by the API and sends
 * the user to /licence (see useApi). /licence is always reachable; session auth
 * applies to everything except /login and /licence.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const license = useLicense()
  if (!license.status.value) await license.fetchStatus()
  if (!license.locked.value && to.path === "/licence") {
    return navigateTo("/", { replace: true })
  }
  if (to.path === "/licence") return

  const auth = useAuth()
  if (to.path === "/login") {
    if (!auth.loaded.value) await auth.fetchMe()
    if (auth.user.value) return navigateTo("/")
    return
  }
  if (!auth.loaded.value) await auth.fetchMe()
  if (!auth.user.value) {
    return navigateTo("/login", { replace: true })
  }
})
