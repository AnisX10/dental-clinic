<script setup lang="ts">
/**
 * Tous les patients (DESIGN.md §7.2): one dominant search field, a simple
 * Nom/Prénom/Téléphone table, and a 3-field fast-create dialog (§7.4).
 */
const { t } = useI18n()
const api = useApi()
const toast = useToast()

interface PatientRow {
  id: number
  code: string
  nom: string
  prenom: string
  telephone: string
}
interface ListData {
  patients: PatientRow[]
  pagination: { total: number, page: number, per_page: number }
}

const q = ref("")
const page = ref(1)
const data = ref<ListData | null>(null)
const loading = ref(true)
const errorMsg = ref("")
let debounce: ReturnType<typeof setTimeout> | undefined

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    data.value = await api.get<ListData>("/patients", { q: q.value, page: page.value })
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

watch(q, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    page.value = 1
    load()
  }, 200)
})

await load()

// ---- New patient dialog ----------------------------------------------------
const showNew = ref(false)
const form = ref({ nom: "", prenom: "", telephone: "", date_naissance: "" })
const saving = ref(false)
const fieldError = ref("")

async function createPatient() {
  saving.value = true
  fieldError.value = ""
  try {
    const created = await api.post<{ patient: { id: number } }>("/patients", form.value)
    showNew.value = false
    form.value = { nom: "", prenom: "", telephone: "", date_naissance: "" }
    toast.success("patients.created")
    await navigateTo(`/patients/${created.patient.id}`)
  }
  catch (e: any) {
    fieldError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

const totalPages = computed(() =>
  data.value ? Math.max(1, Math.ceil(data.value.pagination.total / data.value.pagination.per_page)) : 1,
)
</script>

<template>
  <div class="patients-page-container">
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("patients.title") }}</h1>
        <p v-if="data" class="page-subtitle">{{ data.pagination.total }} patients enregistrés</p>
      </div>
      <div class="toolbar-search-group">
        <div class="search-input-wrapper">
          <AppIcon name="search" size="16" class="search-input-icon" />
          <input
            v-model="q"
            class="input search-input-field"
            :placeholder="t('common.search_placeholder')"
            :aria-label="t('common.search')"
          >
          <button v-if="q" class="search-clear-btn" type="button" @click="q = ''">✕</button>
        </div>
        <button class="btn btn-primary" @click="showNew = true">
          <AppIcon name="plus" size="14" />
          <span>{{ t("patients.nouveau_patient") }}</span>
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div class="card" style="padding:0;overflow:hidden;">
      <div v-if="loading" style="padding:16px;" aria-hidden="true">
        <div v-for="i in 7" :key="i" class="skeleton skeleton-row" />
      </div>

      <div v-else-if="!data?.patients?.length" class="empty-state">
        <AppIcon name="users" size="36" class="muted" style="margin-bottom:8px;opacity:0.6;" />
        <div style="font-weight:600;margin-bottom:4px;">{{ t("patients.aucun") }}</div>
        <div class="small muted">{{ t("patients.nouveau_patient") }}</div>
      </div>

      <table v-else class="table patients-table">
        <thead>
          <tr>
            <th style="width:50px;"></th>
            <th>{{ t("patients.nom") }}</th>
            <th>{{ t("patients.prenom") }}</th>
            <th>Identifiant</th>
            <th>{{ t("patients.telephone") }}</th>
            <th style="width:40px;"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in data.patients"
            :key="p.id"
            class="row-link patient-table-row"
            @click="navigateTo(`/patients/${p.id}`)"
          >
            <td style="width:50px;padding-inline-end:0;">
              <div class="patient-table-avatar">
                {{ ((p.prenom?.[0] || '') + (p.nom?.[0] || '')).toUpperCase() }}
              </div>
            </td>
            <td style="font-weight:650;color:var(--color-text,#0f172a);">{{ p.nom }}</td>
            <td style="font-weight:550;">{{ p.prenom }}</td>
            <td>
              <span class="patient-code-tag">#{{ p.code }}</span>
            </td>
            <td style="font-variant-numeric:tabular-nums;color:var(--color-text-muted,#64748b);">
              {{ p.telephone }}
            </td>
            <td style="text-align:end;color:var(--color-text-subtle,#94a3b8);">
              <AppIcon name="chevron-right" size="16" class="row-arrow" />
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div
        v-if="data && totalPages > 1"
        class="pagination-bar"
      >
        <span class="small muted">Page {{ page }} sur {{ totalPages }} ({{ data.pagination.total }} au total)</span>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; load()">
            <AppIcon name="chevron-left" size="14" />
          </button>
          <button class="btn btn-secondary btn-sm" :disabled="page >= totalPages" @click="page++; load()">
            <AppIcon name="chevron-right" size="14" />
          </button>
        </div>
      </div>
    </div>

    <AppDialog :open="showNew" :title="t('patients.nouveau_patient')" @close="showNew = false">
        <div class="field" style="margin-bottom:12px;">
          <label for="np-nom">{{ t("patients.nom") }}</label>
          <input id="np-nom" v-model="form.nom" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="np-prenom">{{ t("patients.prenom") }}</label>
          <input id="np-prenom" v-model="form.prenom" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="np-tel">{{ t("patients.telephone") }}</label>
          <input id="np-tel" v-model="form.telephone" class="input" inputmode="tel">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="np-bday">{{ t("patients.date_naissance") }}</label>
          <input id="np-bday" v-model="form.date_naissance" class="input" type="date">
        </div>
        <div v-if="fieldError" class="alert alert-error">{{ t(fieldError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showNew = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="createPatient">
            {{ t("common.save") }}
          </button>
        </div>
    </AppDialog>
  </div>
</template>

<style scoped>
.patients-page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar-search-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  justify-content: flex-end;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  max-width: 380px;
  width: 100%;
}

.search-input-icon {
  position: absolute;
  inset-inline-start: 12px;
  color: var(--color-text-subtle, #94a3b8);
  pointer-events: none;
}

.search-input-field {
  padding-inline-start: 36px;
  padding-inline-end: 32px;
  background: var(--color-surface, #ffffff);
}

.search-clear-btn {
  position: absolute;
  inset-inline-end: 10px;
  background: transparent;
  border: none;
  color: var(--color-text-subtle, #94a3b8);
  cursor: pointer;
  padding: 4px;
}

.patients-table th {
  padding-top: 12px;
  padding-bottom: 12px;
}

.patient-table-row {
  cursor: pointer;
}

.patient-table-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-soft, #eef2ff);
  color: var(--color-primary, #0040dc);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11.5px;
  font-weight: 700;
  border: 1px solid color-mix(in srgb, var(--color-primary, #0040dc) 15%, transparent);
}

.patient-code-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted, #64748b);
  background: var(--color-canvas, #f8fafc);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--color-border-subtle, #edf2f7);
}

.row-arrow {
  opacity: 0.4;
  transition: all 0.12s ease;
}

.patient-table-row:hover .row-arrow {
  opacity: 1;
  transform: translateX(2px);
  color: var(--color-primary, #0040dc);
}

[dir="rtl"] .patient-table-row:hover .row-arrow {
  transform: translateX(-2px);
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  background: var(--color-surface-muted, #f1f5f9);
  border-top: 1px solid var(--color-border-subtle, #edf2f7);
}
</style>
