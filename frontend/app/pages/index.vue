<script setup lang="ts">
/**
 * Aujourd'hui (DESIGN.md §7.1): chronological appointment list + small
 * financial summary. No calendar grid.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const money = useMoney()
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
interface TodayData {
  date: string
  appointments: Appt[]
  summary: { recettes_du_jour: string, nombre_paiements: number }
}
interface LabOrderLite {
  id: number
  status: string
  due_date: string | null
  patient: { id: number, nom: string, prenom: string }
  lab: { name: string }
}
interface LowItem {
  id: number
  name: string
  unit: string
  stock_quantity: string
  min_quantity: string
}

const data = ref<TodayData | null>(null)
const loading = ref(true)
const errorMsg = ref("")
const busyId = ref<number | null>(null)
const confirmCancel = ref<Appt | null>(null)

// Alertes (labo + stock) — modules optionnels : silencieux si indisponibles.
const labActive = ref(0)
const labOverdue = ref<LabOrderLite[]>([])
const lowItems = ref<LowItem[]>([])
const hasAlerts = computed(() => labActive.value > 0 || labOverdue.value.length > 0 || lowItems.value.length > 0)

function fmtQty(v: string): string {
  const n = Number.parseFloat(v)
  return Number.isFinite(n) ? String(n) : v
}

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
    const [today, labo, stock] = await Promise.all([
      api.get<TodayData>("/agenda/today"),
      api
        .get<{ orders: LabOrderLite[], counts: Record<string, number> }>("/lab-orders", { limit: "200" })
        .catch(() => null),
      api.get<{ items: LowItem[], low_count: number }>("/stock", { low_stock: "true" }).catch(() => null),
    ])
    data.value = today
    const c = labo?.counts
    labActive.value = c ? (c.envoye ?? 0) + (c.en_fabrication ?? 0) + (c.pret ?? 0) : 0
    labOverdue.value = (labo?.orders ?? []).filter(
      o => ["envoye", "en_fabrication", "pret"].includes(o.status) && !!o.due_date && o.due_date < today.date,
    )
    lowItems.value = stock?.items ?? []
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

    <div class="today-grid">
      <div class="card" style="padding:0;">
        <div v-if="loading" style="padding:8px 16px 16px;" aria-hidden="true">
          <div v-for="i in 5" :key="i" class="skeleton skeleton-row" />
        </div>
        <div v-else-if="!data?.appointments?.length" class="empty-state">
          <span class="empty-icon">◉</span>
          {{ t("today.aucun_rdv") }}
          <div class="empty-hint">{{ t("today.nouveau_rdv") }}</div>
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

      <div style="display:flex;flex-direction:column;gap:24px;">
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

        <div v-if="hasAlerts" class="card">
          <h2 class="section-title" style="margin-bottom:8px;">{{ t("today.alertes") }}</h2>
          <NuxtLink
            v-if="labActive > 0 || labOverdue.length > 0"
            to="/lab"
            class="alert-row"
          >
            <span class="alert-count">{{ labActive }}</span>
            <span>{{ t("today.lab_en_cours") }}</span>
            <span v-if="labOverdue.length" class="badge badge-low">
              {{ labOverdue.length }} {{ t("today.lab_en_retard") }}
            </span>
          </NuxtLink>
          <template v-if="lowItems.length">
            <div class="alert-row" style="cursor:default;">
              <span class="alert-count danger">{{ lowItems.length }}</span>
              <span>{{ t("today.stock_articles_bas") }}</span>
            </div>
            <NuxtLink
              v-for="it in lowItems"
              :key="it.id"
              to="/stock?bas=1"
              class="alert-row sub"
            >
              <span>{{ it.name }}</span>
              <span class="alert-qty">{{ fmtQty(it.stock_quantity) }} / {{ fmtQty(it.min_quantity) }} {{ it.unit }}</span>
            </NuxtLink>
          </template>
        </div>
      </div>
    </div>

    <AppDialog :open="confirmCancel !== null" :title="t('action.confirmer_cancel')" @close="confirmCancel = null">
      <template v-if="confirmCancel">
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
      </template>
    </AppDialog>
  </div>
</template>
