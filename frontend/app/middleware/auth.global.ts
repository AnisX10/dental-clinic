/**
 * Global guards: license lockout first (the licence screen is always reachable,
 * so the clinic can install their .lic file), then session auth for everything
 * except /login and /licence.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const license = useLicense()
  if (!license.status.value) await license.fetchStatus()
  if (license.locked.value && to.path !== "/licence") {
    return navigateTo("/licence", { replace: true })
  }
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
