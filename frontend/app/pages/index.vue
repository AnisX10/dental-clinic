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
interface DormantPatient {
  id: number
  code: string
  nom: string
  prenom: string
  telephone: string
  days_since_visit: number
  last_visit: string
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
const dormant = ref<DormantPatient[]>([])
const hasAlerts = computed(() => labActive.value > 0 || labOverdue.value.length > 0 || lowItems.value.length > 0 || dormant.value.length > 0 || backupOverdue.value)

// Backup watchdog: warn when the last successful backup is ancient history.
const backupStatus = ref<{ last_success: { at: string, kind: string } | null } | null>(null)
const backupOverdue = computed(() => {
  const last = backupStatus.value?.last_success
  if (!last) return true
  const at = new Date(last.at).getTime()
  return Number.isNaN(at) || Date.now() - at > 26 * 3600 * 1000
})

function fmtQty(v: string): string {
  const n = Number.parseFloat(v)
  return Number.isFinite(n) ? String(n) : v
}

const stats = computed(() => {
  const appts = data.value?.appointments ?? []
  const total = appts.length
  const enCours = appts.filter(a => a.status === "en_cours" && !a.cancelled && !a.absent).length
  const enAttente = appts.filter(a => a.status === "arrive" && !a.cancelled && !a.absent).length
  const termines = appts.filter(a => a.status === "termine" && !a.cancelled && !a.absent).length
  return { total, enCours, enAttente, termines }
})

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
    const [today, labo, stock, dormantResp, bk] = await Promise.all([
      api.get<TodayData>("/agenda/today"),
      api
        .get<{ orders: LabOrderLite[], counts: Record<string, number> }>("/lab-orders", { limit: "200" })
        .catch(() => null),
      api.get<{ items: LowItem[], low_count: number }>("/stock", { low_stock: "true" }).catch(() => null),
      api.get<{ patients: DormantPatient[] }>("/patients/dormant", { days: "180", limit: "5" }).catch(() => null),
      api.get<{ last_success: { at: string, kind: string } | null }>("/backup/status").catch(() => null),
    ])
    backupStatus.value = bk
    data.value = today
    const c = labo?.counts
    labActive.value = c ? (c.envoye ?? 0) + (c.en_fabrication ?? 0) + (c.pret ?? 0) : 0
    labOverdue.value = (labo?.orders ?? []).filter(
      o => ["envoye", "en_fabrication", "pret"].includes(o.status) && !!o.due_date && o.due_date < today.date,
    )
    lowItems.value = stock?.items ?? []
    dormant.value = dormantResp?.patients ?? []
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
  <div class="today-page-container">
    <!-- Header Toolbar -->
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("today.title") }}</h1>
        <p class="page-subtitle" style="text-transform:capitalize;">
          {{ data ? dates.weekdayLong(data.date) : "" }}
        </p>
      </div>
      <NuxtLink to="/rendez-vous" class="btn btn-primary">
        <AppIcon name="plus" size="14" />
        <span>{{ t("today.nouveau_rdv") }}</span>
      </NuxtLink>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <!-- KPI Metric Cards Grid -->
    <div class="kpi-grid">
      <div class="kpi-card card">
        <div class="kpi-icon-wrap kpi-blue">
          <AppIcon name="calendar" size="20" />
        </div>
        <div class="kpi-info">
          <span class="kpi-label">Rendez-vous</span>
          <span class="kpi-val">{{ stats.total }}</span>
          <span class="kpi-sub">{{ stats.termines }} terminé(s)</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon-wrap kpi-amber">
          <AppIcon name="tooth" size="20" />
        </div>
        <div class="kpi-info">
          <span class="kpi-label">Au fauteuil</span>
          <span class="kpi-val">{{ stats.enCours }}</span>
          <span class="kpi-sub">En cours de soin</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon-wrap kpi-indigo">
          <AppIcon name="clock" size="20" />
        </div>
        <div class="kpi-info">
          <span class="kpi-label">Salle d'attente</span>
          <span class="kpi-val">{{ stats.enAttente }}</span>
          <span class="kpi-sub">Patient(s) arrivés</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon-wrap kpi-emerald">
          <AppIcon name="wallet" size="20" />
        </div>
        <div class="kpi-info">
          <span class="kpi-label">{{ t("today.recettes_du_jour") }}</span>
          <span class="kpi-val">{{ data ? money.fmt(data.summary.recettes_du_jour) : "0 DA" }}</span>
          <span class="kpi-sub">{{ data?.summary.nombre_paiements ?? 0 }} encaissement(s)</span>
        </div>
      </div>
    </div>

    <!-- Main Content Layout -->
    <div class="today-grid">
      <!-- Appointments Main Card -->
      <div class="card appointments-card" style="padding:0;">
        <div class="card-header-bar">
          <span class="card-header-title">Séances et rendez-vous du jour</span>
          <span class="badge badge-a_venir">{{ data?.appointments?.length ?? 0 }} patients</span>
        </div>

        <div v-if="loading" style="padding:16px;" aria-hidden="true">
          <div v-for="i in 5" :key="i" class="skeleton skeleton-row" />
        </div>

        <div v-else-if="!data?.appointments?.length" class="empty-state">
          <AppIcon name="calendar" size="32" class="muted" style="margin-bottom:8px;opacity:0.6;" />
          <div style="font-weight:600;margin-bottom:4px;">{{ t("today.aucun_rdv") }}</div>
          <div class="small muted">{{ t("today.nouveau_rdv") }}</div>
        </div>

        <table v-else class="table appt-table">
          <tbody>
            <tr v-for="a in data.appointments" :key="a.id" class="appt-row">
              <td class="appt-time-cell">
                <div class="time-chip">
                  <AppIcon name="clock" size="13" class="muted" />
                  <span>
                    <template v-if="a.cancelled">—</template>
                    <template v-else>{{ a.time ?? t("appointment.sans_heure") }}</template>
                  </span>
                </div>
              </td>
              <td>
                <div class="patient-cell-wrap">
                  <div class="patient-mini-avatar">
                    {{ ((a.patient.prenom?.[0] || '') + (a.patient.nom?.[0] || '')).toUpperCase() }}
                  </div>
                  <div class="patient-cell-info">
                    <NuxtLink :to="`/patients/${a.patient.id}`" class="patient-cell-name">
                      {{ a.patient.nom }} {{ a.patient.prenom }}
                    </NuxtLink>
                    <div class="small muted">{{ a.patient.telephone }} <span v-if="a.motif">· {{ a.motif }}</span></div>
                  </div>
                </div>
              </td>
              <td style="width:120px;">
                <span :class="statusClass(a)">{{ t(statusKey(a)) }}</span>
              </td>
              <td
                v-if="!a.cancelled && !a.absent && a.status !== 'termine'"
                class="appt-actions-cell"
              >
                <button
                  v-for="n in NEXT[a.status] ?? []"
                  :key="n.to"
                  class="btn btn-secondary btn-sm"
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
                  :title="t('action.cancel_rdv')"
                  @click="confirmCancel = a"
                >
                  ✕
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Right Alerts & Relance Column -->
      <div class="today-side-col">
        <div v-if="hasAlerts" class="card alerts-card">
          <div class="side-card-title">
            <AppIcon name="alert-triangle" size="16" class="alert-title-icon" />
            <span>{{ t("today.alertes") }}</span>
          </div>

          <NuxtLink
            v-if="labActive > 0 || labOverdue.length > 0"
            to="/lab"
            class="alert-item"
          >
            <div class="alert-icon-box">
              <AppIcon name="lab" size="15" />
            </div>
            <div class="alert-text-box">
              <span class="alert-main-text">{{ labActive }} {{ t("today.lab_en_cours") }}</span>
              <span v-if="labOverdue.length" class="alert-sub-warn">
                {{ labOverdue.length }} {{ t("today.lab_en_retard") }}
              </span>
            </div>
          </NuxtLink>

          <template v-if="lowItems.length">
            <NuxtLink
              to="/stock?bas=1"
              class="alert-item"
            >
              <div class="alert-icon-box warn">
                <AppIcon name="stock" size="15" />
              </div>
              <div class="alert-text-box">
                <span class="alert-main-text">{{ lowItems.length }} {{ t("today.stock_articles_bas") }}</span>
                <span class="alert-sub-warn">Niveaux critiques atteints</span>
              </div>
            </NuxtLink>
          </template>

          <NuxtLink v-if="backupOverdue" to="/parametres" class="alert-item">
            <div class="alert-icon-box danger">
              <AppIcon name="alert-circle" size="15" />
            </div>
            <div class="alert-text-box">
              <span class="alert-main-text danger-text">{{ t("today.backup_overdue") }}</span>
              <span class="alert-sub-warn">Vérifiez vos sauvegardes</span>
            </div>
          </NuxtLink>
        </div>

        <div v-if="dormant.length" class="card relance-card">
          <div class="side-card-title">
            <AppIcon name="clock" size="16" class="muted" />
            <span>{{ t("today.relance") }}</span>
          </div>
          <NuxtLink
            v-for="p in dormant"
            :key="p.id"
            :to="`/patients/${p.id}`"
            class="relance-item"
          >
            <div class="relance-patient-name">{{ p.nom }} {{ p.prenom }}</div>
            <div class="relance-meta">
              {{ p.days_since_visit }} {{ t("today.relance_jours") }} · {{ p.telephone }}
            </div>
          </NuxtLink>
        </div>
      </div>
    </div>

    <!-- Confirm Cancel Dialog -->
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

<style scoped>
.today-page-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* KPI Cards Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}

.kpi-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-blue { background: #eef2ff; color: #0040dc; }
.kpi-amber { background: #fef3c7; color: #b45309; }
.kpi-indigo { background: #e0e7ff; color: #4338ca; }
.kpi-emerald { background: #ecfdf5; color: #047857; }

.kpi-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kpi-label {
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #64748b);
}

.kpi-val {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 11.5px;
  color: var(--color-text-subtle, #94a3b8);
}

/* Appointments Card */
.card-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border-subtle, #f1f5f9);
}

.card-header-title {
  font-weight: 650;
  font-size: 14px;
  color: var(--color-text, #0f172a);
}

.appt-time-cell {
  width: 90px;
}

.time-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
  font-variant-numeric: tabular-nums;
  background: var(--color-canvas, #f8fafc);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--color-border-subtle, #edf2f7);
}

.patient-cell-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.patient-mini-avatar {
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
}

.patient-cell-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text, #0f172a);
  text-decoration: none;
  transition: color 0.12s ease;
}

.patient-cell-name:hover {
  color: var(--color-primary, #0040dc);
}

.appt-actions-cell {
  width: 1%;
  white-space: nowrap;
  display: flex;
  gap: 6px;
  padding-inline-end: 16px;
}

/* Side Column Cards */
.today-side-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
  font-size: 14px;
  margin-bottom: 12px;
  color: var(--color-text, #0f172a);
}

.alert-title-icon {
  color: var(--color-warning, #f59e0b);
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.12s ease;
  margin-bottom: 4px;
}

.alert-item:hover {
  background: var(--color-canvas, #f8fafc);
}

.alert-icon-box {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #eef2ff;
  color: #0040dc;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.alert-icon-box.warn { background: #fef3c7; color: #b45309; }
.alert-icon-box.danger { background: #fef2f2; color: #dc2626; }

.alert-text-box {
  display: flex;
  flex-direction: column;
}

.alert-main-text {
  font-size: 13px;
  font-weight: 550;
  color: var(--color-text, #0f172a);
}

.alert-sub-warn {
  font-size: 11.5px;
  color: var(--color-text-muted, #64748b);
}

.danger-text {
  color: var(--color-danger, #ef4444);
}

.relance-item {
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.12s ease;
}

.relance-item:hover {
  background: var(--color-canvas, #f8fafc);
}

.relance-patient-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text, #0f172a);
}

.relance-meta {
  font-size: 11.5px;
  color: var(--color-text-muted, #64748b);
}
</style>
