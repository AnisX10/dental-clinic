<script setup lang="ts">
/**
 * App shell: persistent sidebar (ACCUEIL / PATIENTS / PLANNING / CLINIQUE /
 * FINANCES / PARAMÈTRES groups per DESIGN.md §5) + sticky page header.
 * RTL-safe via CSS logical properties.
 */
const route = useRoute()
const { t, lang, setLang } = useI18n()
const auth = useAuth()

/** Mobile drawer state (≤760px): hamburger toggles, scrim/nav click closes. */
const sidebarOpen = ref(false)
watch(() => route.path, () => {
  sidebarOpen.value = false
})

const groups = computed(() => [
  {
    label: t("nav.accueil"),
    items: [{ to: "/", icon: "◉", label: t("nav.aujourdhui") }],
  },
  {
    label: t("nav.patients"),
    items: [{ to: "/patients", icon: "☰", label: t("nav.tous_les_patients") }],
  },
  {
    label: t("nav.planning"),
    items: [{ to: "/rendez-vous", icon: "▦", label: t("nav.rendez_vous") }],
  },
  {
    label: t("nav.clinique"),
    items: [
      { to: "/traitements", icon: "✚", label: t("nav.traitements") },
      { to: "/odontogramme", icon: "◌", label: t("nav.odontogramme") },
      { to: "/devis", icon: "▤", label: t("nav.devis") },
      { to: "/dsp", icon: "◈", label: t("nav.dsp") },
      { to: "/sterilisation", icon: "☢", label: t("nav.sterilisation") },
      { to: "/lab", icon: "⚒", label: t("nav.lab") },
      { to: "/stock", icon: "◫", label: t("nav.stock") },
    ],
  },
  {
    label: t("nav.finances"),
    items: [
      { to: "/paiements", icon: "₽", label: t("nav.paiements") },
      { to: "/documents", icon: "▤", label: t("nav.documents") },
    ],
  },
  {
    label: t("nav.parametres"),
    items: [{ to: "/parametres", icon: "⚙", label: t("nav.parametres") }],
  },
])
</script>

<template>
  <div class="app-shell">
    <div v-if="sidebarOpen" class="sidebar-scrim" @click="sidebarOpen = false" />
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="brand" style="display:flex;align-items:center;gap:10px;padding:4px 12px;">
        <img
          src="~/assets/logo.svg"
          alt="HKN"
          style="height:38px;width:auto;"
        >
        <span class="brand-name" style="font-weight:650;font-size:15px;">{{ t("common.app_name") }}</span>
      </div>
      <nav class="sidebar-nav">
        <div v-for="group in groups" :key="group.label" class="nav-group">
          <div class="nav-group-label">{{ group.label }}</div>
          <NuxtLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :title="item.label"
            @click="sidebarOpen = false"
          >
            <span aria-hidden="true" style="width:20px;text-align:center;">{{ item.icon }}</span>
            <span class="nav-label-text">{{ item.label }}</span>
          </NuxtLink>
        </div>
      </nav>
    </aside>

    <div class="main-area">
      <header class="page-header">
        <div style="display:flex;align-items:center;gap:12px;min-width:0;">
          <button
            class="sidebar-toggle"
            :aria-label="t('common.menu')"
            :aria-expanded="sidebarOpen"
            @click="sidebarOpen = !sidebarOpen"
          >☰</button>
          <strong style="font-size:15px;">{{ t("common.app_name") }}</strong>
          <!-- header keeps text name; logo lives in sidebar -->
        </div>
        <div style="display:flex;align-items:center;gap:12px;">
          <div class="field" style="flex-direction:row;align-items:center;gap:8px;">
            <label class="small" for="lang-select">{{ t("settings.langue") }}</label>
            <select
              id="lang-select"
              class="select"
              style="height:34px;width:auto;"
              :value="lang"
              @change="setLang(($event.target as HTMLSelectElement).value as 'fr' | 'ar')"
            >
              <option value="fr">{{ t("settings.langue_fr") }}</option>
              <option value="ar">{{ t("settings.langue_ar") }}</option>
            </select>
          </div>
          <div v-if="auth.user.value" style="display:flex;align-items:center;gap:10px;">
            <span class="small">
              {{ auth.user.value.full_name }}
              <span class="muted">· {{ auth.user.value.is_owner ? "Responsable" : auth.user.value.role }}</span>
            </span>
            <button class="btn btn-secondary btn-sm" @click="auth.logout()">
              {{ t("auth.logout") }}
            </button>
          </div>
        </div>
      </header>
      <slot />
    </div>
  </div>
</template>
