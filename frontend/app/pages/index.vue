<script setup lang="ts">
/**
 * Aujourd'hui (DESIGN.md §7.1): chronological appointment list + small
 * financial summary. No calendar grid.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const money = useMoney()

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
interface TodayData {
  date: string
  appointments: Appt[]
  summary: { recettes_du_jour: string, nombre_paiements: number }
}

const data = ref<TodayData | null>(null)
const loading = ref(true)
const errorMsg = ref("")
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

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    data.value = await api.get<TodayData>("/agenda/today")
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await load()

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
    errorMsg.value = e?.messageKey ?? "errors.generic"
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
    errorMsg.value = e?.messageKey ?? "errors.generic"
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
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("today.title") }}</h1>
        <p class="page-subtitle" style="text-transform:capitalize;">
          {{ data ? dates.weekdayLong(data.date) : "" }}
        </p>
      </div>
      <NuxtLink to="/rendez-vous" class="btn btn-primary">{{ t("today.nouveau_rdv") }}</NuxtLink>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div style="display:grid;grid-template-columns:2fr 1fr;gap:24px;align-items:start;">
      <div class="card" style="padding:0;">
        <div v-if="loading" class="loading-line">{{ t("common.loading") }}</div>
        <div v-else-if="!data?.appointments?.length" class="empty-state">
          {{ t("today.aucun_rdv") }}
        </div>
        <table v-else class="table">
          <tbody>
            <tr v-for="a in data.appointments" :key="a.id">
              <td style="width:70px;font-variant-numeric:tabular-nums;">
                <template v-if="a.cancelled">—</template>
                <template v-else>{{ a.time ?? t("appointment.sans_heure") }}</template>
              </td>
              <td>
                <NuxtLink :to="`/patients/${a.patient.id}`" style="font-weight:600;">
                  {{ a.patient.nom }} {{ a.patient.prenom }}
                </NuxtLink>
                <div class="small muted">{{ a.patient.telephone }}</div>
                <div v-if="a.motif" class="small muted">{{ a.motif }}</div>
              </td>
              <td style="width:110px;">
                <span :class="statusClass(a)">{{ t(statusKey(a)) }}</span>
              </td>
              <td
                v-if="!a.cancelled && !a.absent && a.status !== 'termine'"
                style="width:1%;white-space:nowrap;"
              >
                <button
                  v-for="n in NEXT[a.status] ?? []"
                  :key="n.to"
                  class="btn btn-text btn-sm"
                  :disabled="busyId === a.id"
                  @click="setStatus(a, n.to)"
                >
                  {{ t(n.key) }}
                </button>
              </td>
              <td
                v-if="!a.cancelled && !a.absent"
                style="width:1%;white-space:nowrap;"
              >
                <button
                  v-if="a.status === 'a_venir'"
                  class="btn btn-text btn-sm"
                  :disabled="busyId === a.id"
                  @click="confirmCancel = a"
                >
                  {{ t("action.cancel_rdv") }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h2 class="section-title" style="margin-bottom:12px;">{{ t("today.recettes_du_jour") }}</h2>
        <div class="money-row">
          <span class="money-label">{{ t("today.recettes_du_jour") }}</span>
          <span class="money-value">{{ data ? money.fmt(data.summary.recettes_du_jour) : "" }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("today.nombre_paiements") }}</span>
          <span class="money-value">{{ data?.summary.nombre_paiements ?? 0 }}</span>
        </div>
      </div>
    </div>

    <div v-if="confirmCancel" class="overlay" @click.self="confirmCancel = null">
      <div class="dialog" role="dialog" aria-modal="true">
        <h2>{{ t("action.confirmer_cancel") }}</h2>
        <p>
          {{ confirmCancel.patient.nom }} {{ confirmCancel.patient.prenom }} —
          {{ confirmCancel.date }} {{ confirmCancel.time ?? "" }}
        </p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="confirmCancel = null">{{ t("common.cancel") }}</button>
          <button class="btn btn-danger" :disabled="busyId !== null" @click="doCancel">
            {{ t("action.cancel_rdv") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
