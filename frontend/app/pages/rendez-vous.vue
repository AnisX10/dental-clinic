<script setup lang="ts">
/**
 * Rendez-vous: chronological list for a selected day with day navigation,
 * plus appointment creation (patient search + date + optional time + motif).
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()

interface Appt {
  id: number
  patient: { id: number, code: string, nom: string, prenom: string, telephone: string }
  date: string
  time: string | null
  time_note: string
  motif: string
  status: "a_venir" | "arrive" | "en_cours" | "termine"
  cancelled: boolean
  absent: boolean
}

const day = ref(dates.todayIso())
const appts = ref<Appt[]>([])
const loading = ref(true)
const errorMsg = ref("")
const successMsg = ref("")

function shiftDay(delta: number) {
  const d = new Date(`${day.value}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + delta)
  day.value = d.toISOString().slice(0, 10)
}

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ appointments: Appt[] }>(`/agenda/day/${day.value}`)
    appts.value = data.appointments
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
watch(day, load)
await load()

// ---- Create appointment ----------------------------------------------------
interface PatientRow { id: number, nom: string, prenom: string, telephone: string }
const showNew = ref(false)
const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const selectedPatient = ref<PatientRow | null>(null)
const form = ref({ date: dates.todayIso(), time: "", time_note: "", motif: "" })
const saving = ref(false)
const createError = ref("")
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

function pickPatient(p: PatientRow) {
  selectedPatient.value = p
  patientQuery.value = ""
  patientResults.value = []
}

function openNew() {
  form.value = { date: day.value, time: "", time_note: "", motif: "" }
  selectedPatient.value = null
  createError.value = ""
  showNew.value = true
}

async function create() {
  if (!selectedPatient.value) {
    createError.value = "errors.patient_required"
    return
  }
  saving.value = true
  createError.value = ""
  try {
    await api.post("/agenda/appointments", {
      patient_id: selectedPatient.value.id,
      date: form.value.date,
      time: form.value.time || null,
      time_note: form.value.time_note,
      motif: form.value.motif,
    })
    showNew.value = false
    successMsg.value = t("common.save")
    setTimeout(() => {
      successMsg.value = ""
    }, 2500)
    day.value = form.value.date
    await load()
  }
  catch (e: any) {
    createError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

function statusKey(a: Appt): string {
  if (a.cancelled) return "status.cancelled"
  if (a.absent) return "status.absent"
  return `status.${a.status}`
}
function statusClass(a: Appt): string {
  if (a.cancelled) return "badge badge-cancelled"
  if (a.absent) return "badge badge-absent"
  return `badge badge-${a.status}`
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("nav.rendez_vous") }}</h1>
        <p class="page-subtitle" style="text-transform:capitalize;">{{ dates.weekdayLong(day) }}</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour précédent" @click="shiftDay(-1)">‹</button>
        <input v-model="day" type="date" class="input" style="width:170px;height:36px;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour suivant" @click="shiftDay(1)">›</button>
        <button class="btn btn-primary" @click="openNew">{{ t("today.nouveau_rdv") }}</button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>
    <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

    <div class="card" style="padding:0;">
      <div v-if="loading" class="loading-line">{{ t("common.loading") }}</div>
      <div v-else-if="!appts.length" class="empty-state">{{ t("today.aucun_rdv") }}</div>
      <table v-else class="table">
        <tbody>
          <tr v-for="a in appts" :key="a.id">
            <td style="width:70px;font-variant-numeric:tabular-nums;">
              <template v-if="a.cancelled">—</template>
              <template v-else>{{ a.time ?? t("appointment.sans_heure") }}</template>
              <div v-if="a.time_note" class="small muted">{{ a.time_note }}</div>
            </td>
            <td>
              <NuxtLink :to="`/patients/${a.patient.id}`" style="font-weight:600;">
                {{ a.patient.nom }} {{ a.patient.prenom }}
              </NuxtLink>
              <div class="small muted" style="font-variant-numeric:tabular-nums;">{{ a.patient.telephone }}</div>
              <div v-if="a.motif" class="small muted">{{ a.motif }}</div>
            </td>
            <td style="width:110px;">
              <span :class="statusClass(a)">{{ t(statusKey(a)) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create appointment dialog -->
    <div v-if="showNew" class="overlay" @click.self="showNew = false">
      <div class="dialog" role="dialog" aria-modal="true">
        <h2>{{ t("today.nouveau_rdv") }}</h2>

        <div v-if="!selectedPatient" class="field" style="margin-bottom:12px;">
          <label for="rdv-search">{{ t("appointment.patient") }}</label>
          <input id="rdv-search" v-model="patientQuery" class="input" :placeholder="t('common.search_placeholder')">
          <div v-if="patientResults.length" class="card" style="padding:0;margin-top:4px;">
            <div
              v-for="p in patientResults"
              :key="p.id"
              class="row-link"
              style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--color-border);"
              @click="pickPatient(p)"
            >
              <strong>{{ p.nom }} {{ p.prenom }}</strong>
              <span class="small muted" style="margin-inline-start:8px;">{{ p.telephone }}</span>
            </div>
          </div>
        </div>
        <div
          v-else
          class="alert alert-success"
          style="display:flex;justify-content:space-between;align-items:center;"
        >
          <span>
            {{ selectedPatient.nom }} {{ selectedPatient.prenom }}
            <span class="small">{{ selectedPatient.telephone }}</span>
          </span>
          <button class="btn btn-text btn-sm" @click="selectedPatient = null">{{ t("common.back") }}</button>
        </div>

        <div style="display:flex;gap:12px;">
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="rdv-date">{{ t("appointment.date") }}</label>
            <input id="rdv-date" v-model="form.date" type="date" class="input">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="rdv-time">{{ t("appointment.time") }} ({{ t("common.optional") }})</label>
            <input id="rdv-time" v-model="form.time" type="time" class="input">
          </div>
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="rdv-tnote">{{ t("appointment.time") }} — texte ({{ t("common.optional") }})</label>
          <input id="rdv-tnote" v-model="form.time_note" class="input" placeholder="matin, vers 10h…">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="rdv-motif">{{ t("appointment.motif") }} ({{ t("common.optional") }})</label>
          <input id="rdv-motif" v-model="form.motif" class="input">
        </div>

        <div v-if="createError" class="alert alert-error">{{ t(createError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showNew = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="create">{{ t("common.save") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
