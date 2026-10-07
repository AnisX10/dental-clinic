<script setup lang="ts">
/**
 * Odontogramme launcher: the chart itself lives in the patient file
 * (Onglet Odontogramme). Pick a patient here to open their chart.
 */
const { t } = useI18n()
const api = useApi()
const router = useRouter()

interface PatientRow { id: number, code: string, nom: string, prenom: string, telephone: string }

const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const searching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | undefined

watch(patientQuery, (q) => {
  clearTimeout(searchTimer)
  if (!q.trim()) {
    patientResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      const data = await api.get<{ patients: PatientRow[] }>("/patients", { q: q.trim(), per_page: 8 })
      patientResults.value = data.patients
    }
    catch {
      patientResults.value = []
    }
    finally {
      searching.value = false
    }
  }, 200)
})

function openChart(p: PatientRow) {
  router.push(`/patients/${p.id}?tab=odontogramme`)
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("odontogram.title") }}</h1>
        <p class="page-subtitle">{{ t("odontogram.choose_hint") }}</p>
      </div>
    </div>

    <div class="card" style="max-width:560px;">
      <input
        v-model="patientQuery"
        class="input"
        :placeholder="t('common.search_placeholder')"
        :aria-label="t('common.search')"
      >
      <div v-if="patientResults.length" style="margin-top:8px;">
        <button
          v-for="p in patientResults"
          :key="p.id"
          type="button"
          class="patient-hit"
          @click="openChart(p)"
        >
          <strong>{{ p.nom }} {{ p.prenom }}</strong>
          <span class="small muted">{{ p.telephone }}</span>
        </button>
      </div>
      <div v-else-if="patientQuery.trim() && !searching" class="small muted" style="margin-top:8px;">
        {{ t("patients.aucun") }}
      </div>
    </div>
  </div>
</template>
