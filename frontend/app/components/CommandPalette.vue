<script setup lang="ts">
/**
 * Global Command & Patient Quick-Search Palette (Ctrl+K).
 * Allows instant lookup of patients and quick navigation across the clinic.
 */
const { t } = useI18n()
const api = useApi()
const router = useRouter()

const isOpen = ref(false)
const searchQuery = ref("")
const results = ref<any[]>([])
const loading = ref(false)
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

function open() {
  isOpen.value = true
  searchQuery.value = ""
  results.value = []
  selectedIndex.value = 0
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  isOpen.value = false
}

// Global keyboard shortcut: Ctrl+K / Cmd+K
function onKeyDown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault()
    if (isOpen.value) {
      close()
    } else {
      open()
    }
  } else if (e.key === "Escape" && isOpen.value) {
    close()
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeyDown)
})

onUnmounted(() => {
  window.removeEventListener("keydown", onKeyDown)
})

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (q) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  const trimmed = q.trim()
  if (!trimmed) {
    results.value = []
    loading.value = false
    return
  }
  loading.value = true
  debounceTimer = setTimeout(async () => {
    try {
      const data = await api.get<{ patients: any[] }>("/patients", { q: trimmed })
      results.value = (data.patients ?? []).slice(0, 8)
      selectedIndex.value = 0
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 180)
})

function navigateToPatient(id: number) {
  close()
  router.push(`/patients/${id}`)
}

function onKeyNav(e: KeyboardEvent) {
  if (!results.value.length) return
  if (e.key === "ArrowDown") {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value + 1) % results.value.length
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value - 1 + results.value.length) % results.value.length
  } else if (e.key === "Enter") {
    e.preventDefault()
    const p = results.value[selectedIndex.value]
    if (p) navigateToPatient(p.id)
  }
}

defineExpose({ open, close })
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="cmd-overlay" @click.self="close">
      <div class="cmd-dialog" role="dialog" aria-modal="true">
        <div class="cmd-header">
          <AppIcon name="search" size="18" class="cmd-search-icon" />
          <input
            ref="inputRef"
            v-model="searchQuery"
            type="text"
            class="cmd-input"
            :placeholder="t('common.search_placeholder')"
            @keydown="onKeyNav"
          >
          <span class="cmd-badge">ESC</span>
        </div>

        <div v-if="loading" class="cmd-status">
          {{ t("common.loading") }}
        </div>

        <div v-else-if="searchQuery.trim() && !results.length" class="cmd-status muted">
          {{ t("patients.aucun") || "Aucun patient trouvé" }}
        </div>

        <ul v-else-if="results.length" class="cmd-list">
          <li
            v-for="(patient, idx) in results"
            :key="patient.id"
            class="cmd-item"
            :class="{ active: idx === selectedIndex }"
            @click="navigateToPatient(patient.id)"
            @mouseenter="selectedIndex = idx"
          >
            <div class="cmd-item-avatar">
              {{ (patient.prenom?.[0] || "") + (patient.nom?.[0] || "") }}
            </div>
            <div class="cmd-item-info">
              <span class="cmd-item-name">{{ patient.prenom }} {{ patient.nom }}</span>
              <span class="cmd-item-phone">{{ patient.telephone }} · {{ patient.code }}</span>
            </div>
            <AppIcon name="chevron-right" size="16" class="cmd-item-arrow" />
          </li>
        </ul>

        <div v-else class="cmd-hints">
          <span>{{ t("patients.rechercher_hint") || "Tapez le nom ou le numéro de téléphone" }}</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cmd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}

.cmd-dialog {
  width: 100%;
  max-width: 580px;
  background: var(--color-surface, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--color-border, #e2e8f0);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  animation: cmdSlideDown 0.15s ease-out;
}

@keyframes cmdSlideDown {
  from { opacity: 0; transform: translateY(-8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.cmd-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}

.cmd-search-icon {
  color: var(--color-text-muted, #64748b);
  flex-shrink: 0;
}

.cmd-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 15px;
  color: var(--color-text, #0f172a);
  outline: none;
  font-family: inherit;
}

.cmd-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 6px;
  border-radius: 4px;
  background: var(--color-bg, #f1f5f9);
  color: var(--color-text-muted, #64748b);
  border: 1px solid var(--color-border, #e2e8f0);
}

.cmd-status {
  padding: 24px;
  text-align: center;
  font-size: 13.5px;
}

.cmd-list {
  list-style: none;
  margin: 0;
  padding: 6px;
  max-height: 380px;
  overflow-y: auto;
}

.cmd-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.cmd-item.active {
  background: color-mix(in srgb, var(--color-primary, #0040dc) 8%, white);
}

.cmd-item-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-soft, #eef2ff);
  color: var(--color-primary, #0040dc);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 650;
  font-size: 12px;
  flex-shrink: 0;
}

.cmd-item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.cmd-item-name {
  font-weight: 550;
  font-size: 14px;
  color: var(--color-text, #0f172a);
}

.cmd-item-phone {
  font-size: 12px;
  color: var(--color-text-muted, #64748b);
}

.cmd-item-arrow {
  color: var(--color-text-muted, #94a3b8);
}

.cmd-hints {
  padding: 12px 18px;
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
  border-top: 1px solid var(--color-border-subtle, #f1f5f9);
}
</style>

