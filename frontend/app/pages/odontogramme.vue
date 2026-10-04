<script setup lang="ts">
/**
 * Odontogramme: FDI grid (two arches) with per-tooth state colors.
 * Pick a patient, click a tooth, choose its state.
 */
const { t } = useI18n()
const api = useApi()

interface PatientRow { id: number, nom: string, prenom: string, telephone: string }
type ToothState = "sain" | "a_traiter" | "traite" | "absent"

const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
const STATES: ToothState[] = ["sain", "a_traiter", "traite", "absent"]

const patient = ref<PatientRow | null>(null)
const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const states = ref<Record<string, string>>({})
const treatmentsByTooth = ref<Record<string, { name: string }[]>>({})
const loading = ref(false)
const errorMsg = ref("")
const successMsg = ref("")
let searchTimer: ReturnType<typeof setTimeout> | undefined

watch(patientQuery, (q) => {
  clearTimeout(searchTimer)
  if (!q.trim()) {
    patientResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const data = await api.get<{ patients: PatientRow[] }>("/patients", { q: q.trim(), per_page: 8 })
      patientResults.value = data.patients
    }
    catch {
      patientResults.value = []
    }
  }, 200)
})

async function pickPatient(p: PatientRow) {
  patient.value = p
  patientQuery.value = ""
  patientResults.value = []
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ states: Record<string, string>, treatments_by_tooth: Record<string, { name: string }[]> }>(
      `/clinical/patients/${p.id}/odontogram`,
    )
    states.value = data.states ?? {}
    treatmentsByTooth.value = data.treatments_by_tooth ?? {}
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

async function setTooth(tooth: number) {
  if (!patient.value) return
  const current = (states.value[String(tooth)] ?? "sain") as ToothState
  const next = STATES[(STATES.indexOf(current) + 1) % STATES.length]!
  errorMsg.value = ""
  try {
    await api.put(`/clinical/patients/${patient.value.id}/odontogram`, { tooth, state: next })
    states.value = { ...states.value, [String(tooth)]: next }
    successMsg.value = t("odontogram.saved")
    setTimeout(() => {
      successMsg.value = ""
    }, 1500)
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
}

function toothClass(tooth: number): string {
  const s = states.value[String(tooth)] ?? "sain"
  return `tooth tooth-${s}`
}

function toothTitle(tooth: number): string {
  const trs = treatmentsByTooth.value[String(tooth)]
  if (trs?.length) return trs.map(x => x.name).join(", ")
  return String(tooth)
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("odontogram.title") }}</h1>
        <p v-if="patient" class="page-subtitle">
          {{ patient.nom }} {{ patient.prenom }} · {{ patient.telephone }}
        </p>
      </div>
      <div v-if="!patient" style="width:360px;">
        <input
          v-model="patientQuery"
          class="input"
          :placeholder="t('common.search_placeholder')"
          :aria-label="t('common.search')"
        >
        <div v-if="patientResults.length" class="card" style="padding:0;margin-top:4px;">
          <div
            v-for="p in patientResults"
            :key="p.id"
            style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--color-border);"
            @click="pickPatient(p)"
          >
            <strong>{{ p.nom }} {{ p.prenom }}</strong>
            <span class="small muted" style="margin-inline-start:8px;">{{ p.telephone }}</span>
          </div>
        </div>
      </div>
      <button v-else class="btn btn-secondary btn-sm" @click="patient = null; states = {}">
        {{ t("common.back") }}
      </button>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>
    <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

    <div v-if="!patient" class="card empty-state">{{ t("patients.aucun") }}</div>

    <div v-else class="card">
      <div v-if="loading" class="loading-line">{{ t("common.loading") }}</div>
      <template v-else>
        <div class="odontogram">
          <div class="tooth-row">
            <button
              v-for="tooth in UPPER"
              :key="tooth"
              :class="toothClass(tooth)"
              :title="toothTitle(tooth)"
              @click="setTooth(tooth)"
            >
              <span class="tooth-num">{{ tooth }}</span>
              <span class="tooth-dot" />
            </button>
          </div>
          <div class="tooth-row">
            <button
              v-for="tooth in LOWER"
              :key="tooth"
              :class="toothClass(tooth)"
              :title="toothTitle(tooth)"
              @click="setTooth(tooth)"
            >
              <span class="tooth-num">{{ tooth }}</span>
              <span class="tooth-dot" />
            </button>
          </div>
        </div>
        <div class="legend" style="margin-top:24px;justify-content:center;">
          <span class="lg-sain">{{ t("odontogram.legend_sain") }}</span>
          <span class="lg-a_traiter">{{ t("odontogram.legend_a_traiter") }}</span>
          <span class="lg-traite">{{ t("odontogram.legend_traite") }}</span>
          <span class="lg-absent">{{ t("odontogram.legend_absent") }}</span>
        </div>
      </template>
    </div>
  </div>
</template>
