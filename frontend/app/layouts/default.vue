<script setup lang="ts">
/**
 * DentalPin-inspired modern application shell.
 * - Collapsible sidebar with icon-rail mode (expanded 240px <-> collapsed 68px).
 * - Crisp offline SVG icons via AppIcon.
 * - Global Command Palette (Ctrl+K) for instant patient search.
 * - Clean top header with breadcrumb, search bar, language switcher, user badge.
 * - 100% RTL-safe with CSS logical properties.
 */
const route = useRoute()
const router = useRouter()
const { t, lang, setLang } = useI18n()
const auth = useAuth()

const isSidebarCollapsed = ref(false)
const sidebarOpen = ref(false)
const drawerCollapsed = computed(() => isSidebarCollapsed.value && !sidebarOpen.value)
const commandPaletteRef = ref<{ open: () => void } | null>(null)

onMounted(() => {
  const saved = localStorage.getItem("clinic:sidebar:collapsed")
  if (saved !== null) {
    isSidebarCollapsed.value = saved === "true"
  } else if (window.innerWidth < 1200) {
    isSidebarCollapsed.value = true
  }
})

function toggleCollapse() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  localStorage.setItem("clinic:sidebar:collapsed", String(isSidebarCollapsed.value))
}

watch(() => route.path, () => {
  sidebarOpen.value = false
})

const groups = computed(() => [
  {
    label: t("nav.accueil"),
    items: [{ to: "/", icon: "dashboard", label: t("nav.aujourdhui") }],
  },
  {
    label: t("nav.patients"),
    items: [{ to: "/patients", icon: "users", label: t("nav.tous_les_patients") }],
  },
  {
    label: t("nav.planning"),
    items: [{ to: "/rendez-vous", icon: "calendar", label: t("nav.rendez_vous") }],
  },
  {
    label: t("nav.clinique"),
    items: [
      { to: "/traitements", icon: "treatments", label: t("nav.traitements") },
      { to: "/odontogramme", icon: "tooth", label: t("nav.odontogramme") },
      { to: "/devis", icon: "devis", label: t("nav.devis") },
      { to: "/dsp", icon: "dsp", label: t("nav.dsp") },
      { to: "/sterilisation", icon: "sterilisation", label: t("nav.sterilisation") },
      { to: "/lab", icon: "lab", label: t("nav.lab") },
      { to: "/stock", icon: "stock", label: t("nav.stock") },
    ],
  },
  {
    label: t("nav.finances"),
    items: [
      { to: "/paiements", icon: "paiements", label: t("nav.paiements") },
      { to: "/documents", icon: "documents", label: t("nav.documents") },
    ],
  },
  {
    label: t("nav.parametres"),
    items: [{ to: "/parametres", icon: "parametres", label: t("nav.parametres") }],
  },
])

const currentBreadcrumb = computed(() => {
  const p = route.path
  if (p === "/") return t("nav.aujourdhui")
  if (p.startsWith("/patients/")) return t("nav.patients") + " > " + t("patients.dossier")
  if (p.startsWith("/patients")) return t("nav.patients")
  if (p.startsWith("/rendez-vous")) return t("nav.rendez_vous")
  if (p.startsWith("/traitements")) return t("nav.traitements")
  if (p.startsWith("/odontogramme")) return t("nav.odontogramme")
  if (p.startsWith("/devis")) return t("nav.devis")
  if (p.startsWith("/dsp")) return t("nav.dsp")
  if (p.startsWith("/sterilisation")) return t("nav.sterilisation")
  if (p.startsWith("/lab")) return t("nav.lab")
  if (p.startsWith("/stock")) return t("nav.stock")
  if (p.startsWith("/paiements")) return t("nav.paiements")
  if (p.startsWith("/documents")) return t("nav.documents")
  if (p.startsWith("/parametres")) return t("nav.parametres")
  return t("common.app_name")
})

const userInitials = computed(() => {
  const name = auth.user.value?.full_name?.trim() || ""
  if (!name) return "DR"
  const parts = name.split(/\s+/).filter(Boolean)
  const first = parts[0]?.[0] || ""
  const second = parts[1]?.[0] || ""
  if (first && second) {
    return (first + second).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase() || "DR"
})
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-is-collapsed': drawerCollapsed }">
    <!-- Backdrop Scrim for Mobile Drawer -->
    <div
      v-if="sidebarOpen"
      class="sidebar-scrim"
      @click="sidebarOpen = false"
    />

    <!-- Sidebar (Collapsible & Responsive) -->
    <aside
      class="sidebar"
      :class="{
        open: sidebarOpen,
        collapsed: drawerCollapsed,
      }"
    >
      <!-- Brand Area -->
      <div class="sidebar-brand-wrapper">
        <NuxtLink to="/" class="sidebar-brand">
          <img
            src="~/assets/logo.svg"
            alt="HKN"
            class="brand-logo-img"
          >
          <div v-if="!drawerCollapsed" class="brand-text-block">
            <span class="brand-title">{{ t("common.app_name") }}</span>
            <span class="brand-tagline">Cabinet Dentaire</span>
          </div>
        </NuxtLink>

        <button
          class="sidebar-collapse-btn"
          :title="isSidebarCollapsed ? 'Agrandir le menu' : 'Réduire le menu'"
          @click="toggleCollapse"
        >
          <AppIcon
            :name="isSidebarCollapsed ? 'panel-left-open' : 'panel-left-close'"
            size="18"
          />
        </button>
      </div>

      <!-- Navigation Links -->
      <nav class="sidebar-nav">
        <div
          v-for="group in groups"
          :key="group.label"
          class="nav-group"
        >
          <div v-if="!drawerCollapsed" class="nav-group-label">
            {{ group.label }}
          </div>
          <div v-else class="nav-group-divider" />

          <NuxtLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ 'icon-only': drawerCollapsed }"
            :title="item.label"
            @click="sidebarOpen = false"
          >
            <div class="nav-item-icon-wrap">
              <AppIcon :name="item.icon" size="18" />
            </div>
            <span v-if="!drawerCollapsed" class="nav-label-text">
              {{ item.label }}
            </span>
          </NuxtLink>
        </div>
      </nav>

      <!-- Sidebar Footer -->
      <div class="sidebar-footer">
        <div v-if="!drawerCollapsed" class="sidebar-footer-info">
          <span class="footer-clinic-name">Dr Nom · Alger</span>
          <span class="footer-version">v1.2 · Local-first</span>
        </div>
      </div>
    </aside>

    <!-- Main Workspace Area -->
    <div class="main-area">
      <!-- Sticky Modern App Header -->
      <header class="page-header">
        <!-- Left: Mobile Toggle & Breadcrumb -->
        <div class="header-left">
          <button
            class="sidebar-toggle"
            :aria-label="t('common.menu')"
            :aria-expanded="sidebarOpen"
            @click="sidebarOpen = !sidebarOpen"
          >
            <AppIcon name="menu" size="20" />
          </button>

          <div class="header-breadcrumb">
            <span class="breadcrumb-root">{{ t("common.app_name") }}</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ currentBreadcrumb }}</span>
          </div>
        </div>

        <!-- Center: Quick Search Trigger Button (Ctrl+K) -->
        <div class="header-center">
          <button
            class="header-search-btn"
            type="button"
            @click="commandPaletteRef?.open()"
          >
            <AppIcon name="search" size="15" class="search-btn-icon" />
            <span class="search-btn-text">{{ t("common.search_placeholder") }}</span>
            <kbd class="search-btn-kbd">Ctrl K</kbd>
          </button>
        </div>

        <!-- Right: Actions & Profile -->
        <div class="header-right">
          <!-- Language Toggle Pill -->
          <div class="lang-switch-pill">
            <button
              class="lang-pill-btn"
              :class="{ active: lang === 'fr' }"
              type="button"
              @click="setLang('fr')"
            >
              FR
            </button>
            <button
              class="lang-pill-btn"
              :class="{ active: lang === 'ar' }"
              type="button"
              @click="setLang('ar')"
            >
              عربي
            </button>
          </div>

          <!-- User Profile & Logout -->
          <div v-if="auth.user.value" class="user-profile-badge">
            <div class="user-avatar" :title="auth.user.value.full_name">
              {{ userInitials }}
            </div>
            <div class="user-meta">
              <span class="user-name">{{ auth.user.value.full_name }}</span>
              <span class="user-role">
                {{ auth.user.value.is_owner ? t("auth.role_responsable") : (auth.user.value.role === 'dentiste' ? t("auth.role_dentiste") : t("auth.role_reception")) }}
              </span>
            </div>
            <button
              class="logout-icon-btn"
              :title="t('auth.logout')"
              @click="auth.logout()"
            >
              <AppIcon name="logout" size="16" />
            </button>
          </div>
        </div>
      </header>

      <!-- Main Page View -->
      <main class="page-body">
        <slot />
      </main>
    </div>

    <!-- Global Command Palette Modal -->
    <CommandPalette ref="commandPaletteRef" />

    <!-- One-time print-settings reminder (Chromium margins/background) -->
    <AppPrintHint />
  </div>
</template>

<style scoped>
/* App Shell Grid & Base */
.app-shell {
  display: flex;
  min-height: 100vh;
  background-color: var(--color-canvas, #f8fafc);
}

/* Sidebar Styling */
.sidebar {
  width: var(--sidebar-w, 240px);
  flex-shrink: 0;
  background: var(--color-surface, #ffffff);
  border-inline-end: 1px solid var(--color-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  transition: width 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 50;
}

.sidebar.collapsed {
  width: 68px;
}

/* Brand area */
.sidebar-brand-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 14px 16px;
  border-bottom: 1px solid var(--color-border-subtle, #f1f5f9);
  min-height: 64px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  min-width: 0;
}

.brand-logo-img {
  height: 34px;
  width: auto;
  flex-shrink: 0;
}

.brand-text-block {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--color-text, #0f172a);
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-tagline {
  font-size: 11px;
  color: var(--color-text-muted, #64748b);
  white-space: nowrap;
}

.sidebar-collapse-btn {
  background: transparent;
  border: none;
  padding: 6px;
  border-radius: 6px;
  color: var(--color-text-muted, #64748b);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s ease;
}

.sidebar-collapse-btn:hover {
  background: var(--color-bg, #f1f5f9);
  color: var(--color-text, #0f172a);
}

.sidebar.collapsed .sidebar-collapse-btn {
  margin: 0 auto;
}

/* Navigation items */
.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-group-label {
  font-size: 10.5px;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-subtle, #94a3b8);
  padding: 4px 10px 6px;
}

.nav-group-divider {
  height: 1px;
  background: var(--color-border-subtle, #f1f5f9);
  margin: 6px 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--color-text-muted, #475569);
  text-decoration: none;
  min-height: 38px;
  transition: all 0.15s ease;
  position: relative;
}

.nav-item:hover {
  background: var(--color-canvas, #f8fafc);
  color: var(--color-text, #0f172a);
}

.nav-item.router-link-active {
  background: var(--color-primary-soft, #eef2ff);
  color: var(--color-primary, #0040dc);
  font-weight: 600;
}

.nav-item.icon-only {
  justify-content: center;
  padding: 8px;
}

.nav-item-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  flex-shrink: 0;
}

.nav-label-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Sidebar Footer */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border-subtle, #f1f5f9);
}

.sidebar-footer-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.footer-clinic-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
}

.footer-version {
  font-size: 11px;
  color: var(--color-text-subtle, #94a3b8);
}

/* Main Area & Header */
.main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.page-header {
  background: var(--color-surface, #ffffff);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 40;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.sidebar-toggle {
  display: none;
  background: transparent;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  padding: 6px;
  color: var(--color-text, #0f172a);
  cursor: pointer;
}

.header-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.breadcrumb-root {
  color: var(--color-text-muted, #64748b);
  font-weight: 500;
}

.breadcrumb-separator {
  color: var(--color-border, #cbd5e1);
}

.breadcrumb-current {
  color: var(--color-text, #0f172a);
  font-weight: 600;
}

/* Header Center Search */
.header-center {
  flex: 1;
  max-width: 360px;
}

.header-search-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--color-canvas, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--color-text-muted, #64748b);
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.header-search-btn:hover {
  background: var(--color-surface, #ffffff);
  border-color: var(--color-primary, #0040dc);
  box-shadow: 0 1px 3px rgba(0, 64, 220, 0.08);
}

.search-btn-icon {
  color: var(--color-text-subtle, #94a3b8);
}

.search-btn-text {
  flex: 1;
  text-align: start;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-btn-kbd {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--color-surface, #ffffff);
  border: 1px solid var(--color-border, #e2e8f0);
  color: var(--color-text-muted, #64748b);
}

/* Header Right */
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

/* Language Switch Pill */
.lang-switch-pill {
  display: flex;
  background: var(--color-canvas, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 20px;
  padding: 2px;
}

.lang-pill-btn {
  background: transparent;
  border: none;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--color-text-muted, #64748b);
  cursor: pointer;
  transition: all 0.12s ease;
  font-family: inherit;
}

.lang-pill-btn.active {
  background: var(--color-surface, #ffffff);
  color: var(--color-primary, #0040dc);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* User Profile Badge */
.user-profile-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 4px 4px;
  border-radius: 24px;
  background: var(--color-canvas, #f8fafc);
  border: 1px solid var(--color-border-subtle, #f1f5f9);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary, #0040dc);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 650;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
  line-height: 1.2;
}

.user-role {
  font-size: 10.5px;
  color: var(--color-text-muted, #64748b);
  line-height: 1.2;
}

.logout-icon-btn {
  background: transparent;
  border: none;
  padding: 6px;
  border-radius: 6px;
  color: var(--color-text-muted, #64748b);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s ease;
}

.logout-icon-btn:hover {
  background: var(--color-surface, #ffffff);
  color: var(--color-danger, #b34a4a);
}

/* Page Body */
.page-body {
  flex: 1;
}

/* Responsive Breakpoints */
@media (max-width: 1024px) {
  .header-center {
    display: none;
  }
}

@media (max-width: 768px) {
  .sidebar-toggle {
    display: flex;
  }

  .sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    inset-inline-start: 0;
    transform: translateX(-100%);
    transition: transform 0.2s ease-in-out;
  }

  [dir="rtl"] .sidebar {
    transform: translateX(100%);
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .sidebar-scrim {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.4);
    backdrop-filter: blur(2px);
    z-index: 45;
  }

  .sidebar-collapse-btn {
    display: none;
  }

  .user-meta {
    display: none;
  }
}
</style>
