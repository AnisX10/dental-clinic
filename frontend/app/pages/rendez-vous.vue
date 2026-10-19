<script setup lang="ts">
/**
 * Rendez-vous: chronological list for a selected day with day navigation,
 * plus appointment creation (patient search + date + optional time + motif).
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const toast = useToast()

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
    toast.success("common.save")
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

const busyId = ref<number | null>(null)
const confirmCancel = ref<Appt | null>(null)

const NEXT: Record<string, { key: string, to: string }[]> = {
  a_venir: [
    { key: "action.arrive", to: "arrive" },
    { key: "action.en_cours", to: "en_cours" },
    { key: "action.termine", to: "termine" },
  ],
  arrive: [
    { key: "action.en_cours", to: "en_cours" },
    { key: "action.termine", to: "termine" },
    { key: "action.absent", to: "__absent" },
  ],
  en_cours: [
    { key: "action.termine", to: "termine" },
    { key: "action.absent", to: "__absent" },
  ],
  termine: [],
}

async function setStatus(appt: Appt, to: string) {
  busyId.value = appt.id
  try {
    if (to === "__absent") {
      await api.post(`/agenda/appointments/${appt.id}/absent`)
    }
    else {
      await api.post(`/agenda/appointments/${appt.id}/status`, { status: to })
    }
    await load()
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    busyId.value = null
  }
}

async function doCancel() {
  if (!confirmCancel.value) return
  busyId.value = confirmCancel.value.id
  try {
    await api.post(`/agenda/appointments/${confirmCancel.value.id}/cancel`)
    confirmCancel.value = null
    await load()
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    busyId.value = null
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
  <div class="rendezvous-page-container">
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("nav.rendez_vous") }}</h1>
        <p class="page-subtitle" style="text-transform:capitalize;">{{ dates.weekdayLong(day) }}</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour précédent" @click="shiftDay(-1)">
          <AppIcon name="chevron-left" size="14" />
        </button>
        <input v-model="day" type="date" class="input" style="width:170px;height:36px;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour suivant" @click="shiftDay(1)">
          <AppIcon name="chevron-right" size="14" />
        </button>
        <button class="btn btn-primary" @click="openNew">
          <AppIcon name="plus" size="14" />
          <span>{{ t("today.nouveau_rdv") }}</span>
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div class="card" style="padding:0;overflow:hidden;">
      <div v-if="loading" style="padding:16px;" aria-hidden="true">
        <div v-for="i in 5" :key="i" class="skeleton skeleton-row" />
      </div>
      <div v-else-if="!appts.length" class="empty-state">
        <AppIcon name="calendar" size="36" class="muted" style="margin-bottom:8px;opacity:0.6;" />
        <div style="font-weight:600;margin-bottom:4px;">{{ t("today.aucun_rdv") }}</div>
        <div class="small muted">{{ t("today.nouveau_rdv") }}</div>
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th style="width:110px;">{{ t("appointment.time") }}</th>
            <th>{{ t("appointment.patient") }}</th>
            <th style="width:130px;">{{ t("common.status") || "Statut" }}</th>
            <th style="text-align:end;width:240px;">{{ t("common.actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in appts" :key="a.id" class="row-link">
            <td style="font-variant-numeric:tabular-nums;" @click="navigateTo(`/patients/${a.patient.id}`)">
              <div class="time-badge">
                <AppIcon name="clock" size="12" class="muted" />
                <span v-if="a.cancelled">—</span>
                <span v-else>{{ a.time ?? t("appointment.sans_heure") }}</span>
              </div>
              <div v-if="a.time_note" class="small muted" style="margin-top:2px;">{{ a.time_note }}</div>
            </td>
            <td @click="navigateTo(`/patients/${a.patient.id}`)">
              <div style="display:flex;align-items:center;gap:10px;">
                <div class="patient-table-avatar">
                  {{ ((a.patient.prenom?.[0] || '') + (a.patient.nom?.[0] || '')).toUpperCase() }}
                </div>
                <div>
                  <div style="font-weight:650;color:var(--color-text,#0f172a);">
                    {{ a.patient.nom }} {{ a.patient.prenom }}
                  </div>
                  <div class="small muted" style="font-variant-numeric:tabular-nums;">
                    {{ a.patient.telephone }}
                    <span v-if="a.motif"> · {{ a.motif }}</span>
                  </div>
                </div>
              </div>
            </td>
            <td @click="navigateTo(`/patients/${a.patient.id}`)">
              <span :class="statusClass(a)">{{ t(statusKey(a)) }}</span>
            </td>
            <td style="text-align:end;" @click.stop>
              <div style="display:inline-flex;gap:4px;align-items:center;justify-content:flex-end;">
                <button
                  v-for="n in NEXT[a.status] ?? []"
                  :key="n.to"
                  class="btn btn-secondary btn-sm"
                  :disabled="busyId === a.id"
                  @click.stop="setStatus(a, n.to)"
                >
                  {{ t(n.key) }}
                </button>
                <button
                  v-if="!a.cancelled && a.status === 'a_venir'"
                  class="btn btn-text btn-sm"
                  style="color:var(--color-danger,#ef4444);padding:4px 8px;"
                  :disabled="busyId === a.id"
                  :title="t('action.cancel_rdv')"
                  @click.stop="confirmCancel = a"
                >
                  ✕
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create appointment dialog -->
    <AppDialog :open="showNew" :title="t('today.nouveau_rdv')" @close="showNew = false">

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
    </AppDialog>

    <!-- Confirm cancellation dialog -->
    <AppDialog
      :open="!!confirmCancel"
      :title="t('action.cancel_rdv')"
      @close="confirmCancel = null"
    >
      <p style="margin-bottom:16px;">
        {{ t("action.confirm_cancel") }}
      </p>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="confirmCancel = null">
          {{ t("common.cancel") }}
        </button>
        <button class="btn btn-danger" :disabled="busyId !== null" @click="doCancel">
          {{ t("action.cancel_rdv") }}
        </button>
      </div>
    </AppDialog>
  </div>
</template>

<style scoped>
.rendezvous-page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.time-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 650;
  color: var(--color-text, #0f172a);
  background: var(--color-canvas, #f8fafc);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--color-border-subtle, #edf2f7);
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
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--color-primary, #0040dc) 15%, transparent);
}
</style>
