/**
 * Global auth guard: every page requires a session except /login.
 */
export default defineNuxtRouteMiddleware(async (to) => {
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
