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
const form = ref({ nom: "", prenom: "", telephone: "" })
const saving = ref(false)
const fieldError = ref("")

async function createPatient() {
  saving.value = true
  fieldError.value = ""
  try {
    const created = await api.post<{ patient: { id: number } }>("/patients", form.value)
    showNew.value = false
    form.value = { nom: "", prenom: "", telephone: "" }
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
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("patients.title") }}</h1>
        <p v-if="data" class="page-subtitle">{{ data.pagination.total }}</p>
      </div>
      <div style="display:flex;gap:12px;align-items:center;flex:1;justify-content:flex-end;">
        <input
          v-model="q"
          class="input search-input"
          :placeholder="t('common.search_placeholder')"
          :aria-label="t('common.search')"
        >
        <button class="btn btn-primary" @click="showNew = true">
          {{ t("patients.nouveau_patient") }}
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div class="card" style="padding:0;">
      <div v-if="loading" style="padding:8px 16px 16px;" aria-hidden="true">
        <div v-for="i in 7" :key="i" class="skeleton skeleton-row" />
      </div>
      <div v-else-if="!data?.patients?.length" class="empty-state">
        <span class="empty-icon">☰</span>
        {{ t("patients.aucun") }}
        <div class="empty-hint">{{ t("patients.nouveau_patient") }}</div>
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t("patients.nom") }}</th>
            <th>{{ t("patients.prenom") }}</th>
            <th>{{ t("patients.telephone") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in data.patients"
            :key="p.id"
            class="row-link"
            @click="navigateTo(`/patients/${p.id}`)"
          >
            <td style="font-weight:600;">{{ p.nom }}</td>
            <td>{{ p.prenom }}</td>
            <td style="font-variant-numeric:tabular-nums;">{{ p.telephone }}</td>
          </tr>
        </tbody>
      </table>
      <div
        v-if="data && totalPages > 1"
        style="display:flex;gap:12px;justify-content:flex-end;padding:12px 16px;"
      >
        <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; load()">
          ‹
        </button>
        <span class="small muted" style="align-self:center;">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-secondary btn-sm" :disabled="page >= totalPages" @click="page++; load()">
          ›
        </button>
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
        <div class="field" style="margin-bottom:16px;">
          <label for="np-tel">{{ t("patients.telephone") }}</label>
          <input id="np-tel" v-model="form.telephone" class="input" inputmode="tel">
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
