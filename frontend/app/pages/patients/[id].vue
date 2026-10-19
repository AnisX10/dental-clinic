<script setup lang="ts">
/**
 * Patient file (DESIGN.md §7.3): summary-first with tabs
 * Résumé / Médical / Traitements / Paiements / Documents.
 * Quick actions: Nouvelle note · Ajouter un traitement · Odontogramme.
 */
import type { ToothCondition } from "~/utils/toothShapes"

const route = useRoute()
const router = useRouter()
const patientId = Number(route.params.id)
const { t } = useI18n()
const api = useApi()
const money = useMoney()
const dates = useDates()
const auth = useAuth()
const toast = useToast()

// --- Odontogramme ---
const conditions = ref<ToothCondition[]>([])
const odontoTreatments = ref<Record<number, { name: string }[]>>({})
const selectedTooth = ref<number | null>(null)
const odontoBusy = ref(false)
const dentition = ref<"permanente" | "temporaire">("permanente")

interface ToothHistoryRow {
  id: number
  tooth: number
  surface: string
  condition: string
  action: string
  changed_at: string
  changed_by: string | null
}
const toothHistory = ref<ToothHistoryRow[]>([])

interface Patient {
  id: number, code: string, nom: string, prenom: string, telephone: string,
  telephone2: string, date_naissance: string, age_years: number | null,
  adresse: string, wilaya: string, notes: string,
  created_at: string,
  medical: Record<string, boolean | string> | null,
}
interface Note { id: number, motif: string, diagnostic: string, traitement: string, remarques: string, created_at: string }
interface Treatment { id: number, name: string, category: string, price: string, tooth: number | null, note: string, created_at: string }
interface Ledger {
  total: string, paye: string, reste: string,
  payments: { id: number, amount: string, note: string, created_at: string, created_by_name: string }[],
}
interface DocRow { id: number, doc_type: string, title: string, created_at: string }

interface AttachmentRow { id: number, original_name: string, mime_type: string, size_bytes: number, created_at: string }
interface LabOrderRow {
  id: number
  lab: { id: number, name: string }
  work_type: string
  teeth: string
  shade: string
  price: string
  status: string
  sent_date: string
  due_date: string | null
  received_date: string | null
}

const WORK_TYPES = ["couronne", "bridge", "prothese", "gouttiere", "autre"] as const

function workTypeLabel(workType: string): string {
  return WORK_TYPES.includes(workType as (typeof WORK_TYPES)[number]) ? t(`lab.work_${workType}`) : workType
}

const patient = ref<Patient | null>(null)
const loading = ref(true)
const errorMsg = ref("")
type TabKey = "resume" | "medical" | "odontogramme" | "traitements" | "paiements" | "documents"
const TAB_KEYS: TabKey[] = ["resume", "medical", "odontogramme", "traitements", "paiements", "documents"]
const queryTab = String(route.query.tab ?? "")
const tab = ref<TabKey>(TAB_KEYS.includes(queryTab as TabKey) ? (queryTab as TabKey) : "resume")

const notes = ref<Note[]>([])
const treatments = ref<Treatment[]>([])
const ledger = ref<Ledger | null>(null)
const docs = ref<DocRow[]>([])
const attachments = ref<AttachmentRow[]>([])
const uploading = ref(false)
const deletingAttachmentId = ref<number | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/webp,application/pdf"
const labOrders = ref<LabOrderRow[]>([])

const tabLoaded = ref<Record<string, boolean>>({})

async function loadPatient() {
  loading.value = true
  try {
    const data = await api.get<{ patient: Patient }>(`/patients/${patientId}`)
    patient.value = data.patient
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await loadPatient()

async function loadTab(name: string) {
  try {
    errorMsg.value = ""
    if (name === "resume") {
      const [n, tr, lg, lo] = await Promise.all([
        api.get<{ notes: Note[] }>(`/clinical/patients/${patientId}/notes`),
        api.get<{ treatments: Treatment[] }>(`/clinical/patients/${patientId}/treatments`),
        api.get<Ledger>(`/payments/patients/${patientId}/ledger`),
        api.get<{ orders: LabOrderRow[] }>(`/patients/${patientId}/lab-orders`),
      ])
      notes.value = n.notes
      treatments.value = tr.treatments
      ledger.value = lg
      labOrders.value = lo.orders
      tabLoaded.value.resume = true
    }
    if (name === "odontogramme" && !tabLoaded.value.odontogramme) {
      await Promise.all([loadOdontogram(), loadToothHistory()])
      tabLoaded.value.odontogramme = true
    }
    if (name === "traitements" && !tabLoaded.value.traitements) {
      const tr = await api.get<{ treatments: Treatment[] }>(`/clinical/patients/${patientId}/treatments`)
      treatments.value = tr.treatments
      tabLoaded.value.traitements = true
    }
    if (name === "paiements" && !tabLoaded.value.paiements) {
      ledger.value = await api.get<Ledger>(`/payments/patients/${patientId}/ledger`)
      tabLoaded.value.paiements = true
    }
    if (name === "documents" && !tabLoaded.value.documents) {
      const d = await api.get<{ documents: DocRow[] }>(`/documents/patients/${patientId}`)
      docs.value = d.documents
      const att = await api.get<{ attachments: AttachmentRow[] }>(`/patients/${patientId}/attachments`)
      attachments.value = att.attachments
      tabLoaded.value.documents = true
    }
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
}
if (patient.value) await loadTab(tab.value)

async function loadAttachments() {
  const att = await api.get<{ attachments: AttachmentRow[] }>(`/patients/${patientId}/attachments`)
  attachments.value = att.attachments
}

function onAttachmentPicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  void uploadAttachment(file)
}

function onClickFileLabel() {
  fileInputRef.value?.click()
}

async function uploadAttachment(file: File) {
  if (uploading.value) return
  uploading.value = true
  errorMsg.value = ""
  try {
    await api.upload<{ attachment: AttachmentRow }>(`/patients/${patientId}/attachments`, file)
    toast.success("documents.att_upload")
    await loadAttachments()
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    uploading.value = false
  }
}

async function deleteAttachment(a: AttachmentRow) {
  if (deletingAttachmentId.value !== null) return
  deletingAttachmentId.value = a.id
  errorMsg.value = ""
  try {
    await api.del(`/patients/${patientId}/attachments/${a.id}`)
    toast.success("documents.att_deleted")
    attachments.value = attachments.value.filter(x => x.id !== a.id)
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    deletingAttachmentId.value = null
  }
}

function fmtFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function flash(messageKey: string) {
  toast.success(messageKey)
}

async function loadOdontogram() {
  const og = await api.get<{ conditions: ToothCondition[], treatments_by_tooth: Record<string, { name: string }[]> }>(
    `/clinical/patients/${patientId}/odontogram`,
  )
  conditions.value = og.conditions
  const map: Record<number, { name: string }[]> = {}
  for (const [key, list] of Object.entries(og.treatments_by_tooth ?? {})) map[Number(key)] = list
  odontoTreatments.value = map
}

async function loadToothHistory() {
  try {
    const r = await api.get<{ history: ToothHistoryRow[] }>(
      `/clinical/patients/${patientId}/odontogram/history`,
    )
    toothHistory.value = r.history
  }
  catch {
    toothHistory.value = []
  }
}

async function applyCondition(payload: { tooth: number, condition: string, surface: string }) {
  odontoBusy.value = true
  try {
    await api.put(`/clinical/patients/${patientId}/odontogram`, payload)
    await loadOdontogram()
    await loadToothHistory()
    flash("odontogram.saved")
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    odontoBusy.value = false
  }
}

function toothTreatments(tooth: number): { name: string }[] {
  return odontoTreatments.value[tooth] ?? []
}

async function onSelectTooth(tooth: number) {
  selectedTooth.value = tooth
  await nextTick()
  document.querySelector(".cond-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" })
}

// ---- New clinical note -----------------------------------------------------
const showNote = ref(false)
const noteForm = ref({ motif: "", diagnostic: "", traitement: "", remarques: "" })
const noteSaving = ref(false)
const noteError = ref("")

async function saveNote() {
  noteSaving.value = true
  noteError.value = ""
  try {
    await api.post("/clinical/notes", { patient_id: patientId, ...noteForm.value })
    showNote.value = false
    noteForm.value = { motif: "", diagnostic: "", traitement: "", remarques: "" }
    tabLoaded.value.resume = false
    tabLoaded.value.traitements = false
    await loadTab(tab.value)
    flash("notes.saved")
  }
  catch (e: any) {
    noteError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    noteSaving.value = false
  }
}

// ---- Add treatment ---------------------------------------------------------
interface CatalogItem { id: number, name: string, category: string, default_price: string, is_active: boolean }
const showTreatment = ref(false)
const catalog = ref<CatalogItem[]>([])
const treatmentForm = ref({ catalog_item_id: "", tooth: "", price: "", note: "" })
const treatmentSaving = ref(false)
const treatmentError = ref("")

async function openTreatment() {
  showTreatment.value = true
  if (!catalog.value.length) {
    try {
      const c = await api.get<{ items: CatalogItem[] }>("/clinical/catalog")
      catalog.value = c.items.filter(i => i.is_active)
    }
    catch {
      catalog.value = []
    }
  }
}

const selectedCatalogItem = computed(() =>
  catalog.value.find(i => String(i.id) === treatmentForm.value.catalog_item_id) ?? null,
)

/** Picking a treatment pre-fills the price with the catalog default (still editable). */
watch(selectedCatalogItem, (item) => {
  if (item) treatmentForm.value.price = item.default_price
})

async function saveTreatment() {
  treatmentSaving.value = true
  treatmentError.value = ""
  const item = selectedCatalogItem.value
  try {
    await api.post("/clinical/treatments", {
      patient_id: patientId,
      catalog_item_id: item?.id ?? null,
      name: item?.name ?? "",
      category: item?.category ?? "",
      price: treatmentForm.value.price === "" ? "" : treatmentForm.value.price,
      tooth: treatmentForm.value.tooth === "" ? null : Number(treatmentForm.value.tooth),
      note: treatmentForm.value.note,
    })
    showTreatment.value = false
    treatmentForm.value = { catalog_item_id: "", tooth: "", price: "", note: "" }
    tabLoaded.value.resume = false
    tabLoaded.value.traitements = false
    await loadTab(tab.value)
    await loadPatient()
    flash("treatments.added")
  }
  catch (e: any) {
    treatmentError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    treatmentSaving.value = false
  }
}

// ---- Payment ---------------------------------------------------------------
const showPayment = ref(false)
const paymentForm = ref({ amount: "", note: "" })
const paymentSaving = ref(false)
const paymentError = ref("")

async function openPayment() {
  paymentForm.value = { amount: "", note: "" }
  paymentError.value = ""
  showPayment.value = true
  if (!tabLoaded.value.paiements) await loadTab("paiements")
}

async function savePayment() {
  paymentSaving.value = true
  paymentError.value = ""
  try {
    await api.post("/payments", { patient_id: patientId, amount: paymentForm.value.amount, note: paymentForm.value.note })
    showPayment.value = false
    tabLoaded.value.paiements = false
    await loadTab(tab.value === "paiements" ? "paiements" : tab.value)
    flash("payments.saved")
  }
  catch (e: any) {
    paymentError.value = e?.messageKey ?? "errors.generic"
    if (e?.values?.reste) paymentForm.value.amount = e.values.reste
  }
  finally {
    paymentSaving.value = false
  }
}

// ---- Medical form ----------------------------------------------------------
const MED_FIELDS = [
  "diabete", "hypertension", "maladie_cardiaque", "grossesse", "anticoagulants",
  "asthme", "epilepsie", "allergies",
] as const
const medicalForm = ref<Record<string, boolean | string>>({})
const medicalSaving = ref(false)
const medicalDirty = ref(false)

watch(patient, (p) => {
  if (p && !medicalDirty.value) {
    medicalForm.value = { ...(p.medical ?? {}) }
    for (const f of MED_FIELDS) if (medicalForm.value[f] === undefined) medicalForm.value[f] = false
    if (medicalForm.value.autre === undefined) medicalForm.value.autre = ""
  }
}, { immediate: true })

async function saveMedical() {
  medicalSaving.value = true
  try {
    const payload: Record<string, unknown> = {}
    for (const f of MED_FIELDS) payload[f] = Boolean(medicalForm.value[f])
    payload.autre = String(medicalForm.value.autre ?? "")
    await api.put(`/patients/${patientId}/medical`, payload)
    medicalDirty.value = false
    await loadPatient()
    flash("medical.saved")
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    medicalSaving.value = false
  }
}

// ---- Edit patient ----------------------------------------------------------
const showEdit = ref(false)
const editForm = ref({ nom: "", prenom: "", telephone: "", telephone2: "", date_naissance: "", adresse: "", wilaya: "", notes: "" })
const editSaving = ref(false)
const editError = ref("")

function openEdit() {
  const p = patient.value!
  editForm.value = {
    nom: p.nom, prenom: p.prenom, telephone: p.telephone, telephone2: p.telephone2,
    date_naissance: p.date_naissance ?? "",
    adresse: p.adresse, wilaya: p.wilaya, notes: p.notes,
  }
  editError.value = ""
  showEdit.value = true
}

async function saveEdit() {
  editSaving.value = true
  editError.value = ""
  try {
    await api.put(`/patients/${patientId}`, editForm.value)
    showEdit.value = false
    await loadPatient()
    flash("patients.updated")
  }
  catch (e: any) {
    editError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    editSaving.value = false
  }
}

const medicalAlerts = computed(() => {
  if (!patient.value?.medical) return []
  const alerts: string[] = []
  const med = patient.value.medical
  const keys = ["allergies", "anticoagulants", "maladie_cardiaque", "diabete", "grossesse", "asthme", "epilepsie", "hypertension"]
  for (const k of keys) {
    if (med[k]) alerts.push(t(`medical.${k}`))
  }
  return alerts
})

function openTreatmentForTooth(tooth: number) {
  treatmentForm.value.tooth = String(tooth)
  openTreatment()
}

const tabs = [
  { key: "resume", label: "patient_tabs.resume", icon: "dashboard" },
  { key: "medical", label: "patient_tabs.medical", icon: "shield-check" },
  { key: "odontogramme", label: "patient_tabs.odontogramme", icon: "tooth" },
  { key: "traitements", label: "patient_tabs.traitements", icon: "treatments" },
  { key: "paiements", label: "patient_tabs.paiements", icon: "wallet" },
  { key: "documents", label: "patient_tabs.documents", icon: "documents" },
] as const

function switchTab(key: typeof tab.value) {
  tab.value = key
  const q: Record<string, unknown> = { ...route.query }
  if (key === "resume") delete q.tab
  else q.tab = key
  router.replace({ query: q })
  loadTab(key)
}

const hasReste = computed(() => ledger.value && Number(ledger.value.reste) > 0)

// ---- Quick appointment booking from patient page --------------------------
const showRdv = ref(false)
const rdvForm = ref({ date: dates.todayIso(), time: "", time_note: "", motif: "" })
const rdvSaving = ref(false)
const rdvError = ref("")

function openRdvModal() {
  rdvForm.value = { date: dates.todayIso(), time: "", time_note: "", motif: "" }
  rdvError.value = ""
  showRdv.value = true
}

async function saveRdv() {
  rdvSaving.value = true
  rdvError.value = ""
  try {
    await api.post("/agenda/appointments", {
      patient_id: patientId,
      date: rdvForm.value.date,
      time: rdvForm.value.time || null,
      time_note: rdvForm.value.time_note,
      motif: rdvForm.value.motif,
    })
    showRdv.value = false
    toast.success("common.save")
  }
  catch (e: any) {
    rdvError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    rdvSaving.value = false
  }
}
</script>

<template>
  <div class="patient-page-container">
    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div v-if="loading" style="max-width:840px;" aria-hidden="true">
      <div class="skeleton skeleton-line w-40" />
      <div class="skeleton skeleton-line w-60" />
      <div class="skeleton skeleton-line w-80" />
    </div>

    <template v-else-if="patient">
      <!-- Modern Patient Hero Card (DentalPin Inspired) -->
      <div class="patient-hero-card card">
        <div class="patient-hero-top">
          <NuxtLink to="/patients" class="hero-back-link">
            <AppIcon name="chevron-left" size="16" />
            <span>{{ t("common.back") }}</span>
          </NuxtLink>
          <span class="patient-code-badge">Dossier #{{ patient.code }}</span>
        </div>

        <div class="patient-hero-body">
          <div class="patient-avatar-box">
            {{ ((patient.prenom?.[0] || '') + (patient.nom?.[0] || '')).toUpperCase() }}
          </div>

          <div class="patient-identity-box">
            <div class="patient-name-row">
              <h1 class="patient-full-name">{{ patient.nom }} {{ patient.prenom }}</h1>
              <button class="btn btn-secondary btn-sm" @click="openEdit" :title="t('common.edit')">
                <AppIcon name="edit" size="14" />
                <span>{{ t("common.edit") }}</span>
              </button>
            </div>

            <div class="patient-chips-row">
              <a :href="'tel:' + patient.telephone" class="patient-chip patient-chip-link" :title="patient.telephone">
                <AppIcon name="phone" size="13" />
                <span>{{ patient.telephone }}</span>
              </a>
              <span v-if="patient.telephone2" class="patient-chip">
                <AppIcon name="phone" size="13" />
                <span>{{ patient.telephone2 }}</span>
              </span>
              <span v-if="patient.age_years !== null" class="patient-chip">
                <AppIcon name="calendar" size="13" />
                <span>{{ patient.age_years }} {{ t("patients.ans") }}</span>
                <span v-if="patient.date_naissance" class="muted">({{ dates.fmtDate(patient.date_naissance) }})</span>
              </span>
              <span v-if="patient.wilaya" class="patient-chip">
                <AppIcon name="home" size="13" />
                <span>{{ patient.wilaya }}</span>
              </span>
            </div>

            <!-- Medical Alerts Warning Banner -->
            <div v-if="medicalAlerts.length" class="patient-medical-alert-chip">
              <AppIcon name="alert-triangle" size="14" class="alert-icon" />
              <span class="alert-label">Alerte médicale :</span>
              <span class="alert-content">{{ medicalAlerts.join(" · ") }}</span>
            </div>
          </div>

          <!-- Financial Balance Strip -->
          <div v-if="ledger" class="patient-ledger-pill">
            <div class="ledger-stat">
              <span class="stat-label">{{ t("resume.total") }}</span>
              <span class="stat-val">{{ money.fmt(ledger.total) }}</span>
            </div>
            <div class="ledger-stat-divider" />
            <div class="ledger-stat">
              <span class="stat-label">{{ t("resume.paye") }}</span>
              <span class="stat-val stat-success">{{ money.fmt(ledger.paye) }}</span>
            </div>
            <div class="ledger-stat-divider" />
            <div class="ledger-stat">
              <span class="stat-label">{{ t("resume.reste") }}</span>
              <span class="stat-val" :class="{ 'stat-danger': Number(ledger.reste) > 0 }">
                {{ money.fmt(ledger.reste) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Quick Action Bar -->
        <div class="patient-actions-bar">
          <div class="action-buttons-group">
            <button class="btn btn-primary btn-sm" @click="showNote = true">
              <AppIcon name="plus" size="14" />
              <span>{{ t("resume.nouvelle_note") }}</span>
            </button>
            <button class="btn btn-secondary btn-sm" @click="openTreatment">
              <AppIcon name="treatments" size="14" />
              <span>{{ t("resume.ajouter_traitement") }}</span>
            </button>
            <button class="btn btn-secondary btn-sm" @click="switchTab('odontogramme')">
              <AppIcon name="tooth" size="14" />
              <span>{{ t("resume.odontogramme") }}</span>
            </button>
            <button class="btn btn-secondary btn-sm" @click="openRdvModal">
              <AppIcon name="calendar" size="14" />
              <span>{{ t("today.nouveau_rdv") }}</span>
            </button>
          </div>

          <button v-if="hasReste" class="btn btn-primary btn-sm btn-encaissement" @click="openPayment">
            <AppIcon name="wallet" size="14" />
            <span>{{ t("payments.encaisser") }}</span>
          </button>
        </div>
      </div>

      <!-- Modern Segmented Tabs -->
      <div class="segmented-tabs-wrapper">
        <div class="segmented-tabs">
          <button
            v-for="tb in tabs"
            :key="tb.key"
            class="segmented-tab-btn"
            :class="{ active: tab === tb.key }"
            @click="switchTab(tb.key)"
          >
            <AppIcon :name="tb.icon" size="15" />
            <span>{{ t(tb.label) }}</span>
          </button>
        </div>
      </div>

      <!-- Résumé -->
      <template v-if="tab === 'resume'">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;">
          <div class="card">
            <h2 class="section-title" style="margin-bottom:12px;">{{ t("resume.historique") }}</h2>
            <div v-if="!notes.length && !treatments.length" class="empty-state">
              {{ t("resume.aucune_activite") }}
            </div>
            <table v-else class="table">
              <tbody>
                <tr v-for="n in notes" :key="`n${n.id}`">
                  <td>
                    <div class="small muted">{{ dates.fmtDate(n.created_at) }} · {{ t("notes.nouvelle_note") }}</div>
                    <div>{{ n.motif || n.diagnostic || "—" }}</div>
                  </td>
                </tr>
                <tr v-for="tr in treatments" :key="`t${tr.id}`">
                  <td>
                    <div class="small muted">{{ dates.fmtDate(tr.created_at) }} · {{ t("treatments.title") }}</div>
                    <div>
                      {{ tr.name }}
                      <span v-if="tr.tooth" class="muted">· {{ t("treatments.dent") }} {{ tr.tooth }}</span>
                    </div>
                    <div class="small" style="font-variant-numeric:tabular-nums;">{{ money.fmt(tr.price) }}</div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="card">
            <h2 class="section-title" style="margin-bottom:12px;">{{ t("patient_tabs.paiements") }}</h2>
            <template v-if="ledger">
              <div class="money-row">
                <span class="money-label">{{ t("resume.total") }}</span>
                <span class="money-value">{{ money.fmt(ledger.total) }}</span>
              </div>
              <div class="money-row">
                <span class="money-label">{{ t("resume.paye") }}</span>
                <span class="money-value" style="color:var(--color-success);">{{ money.fmt(ledger.paye) }}</span>
              </div>
              <div class="money-row">
                <span class="money-label">{{ t("resume.reste") }}</span>
                <span class="money-value" :class="{ 'money-reste': Number(ledger.reste) > 0 }">
                  {{ money.fmt(ledger.reste) }}
                </span>
              </div>
            </template>
          </div>

          <div class="card" style="grid-column:1 / -1;">
            <h2 class="section-title" style="margin-bottom:12px;">{{ t("nav.lab") }}</h2>
            <div v-if="!labOrders.length" class="empty-state" style="padding:16px 0;">
              {{ t("lab.aucun_ordre") }}
            </div>
            <div v-else class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>{{ t("lab.type_travail") }}</th>
                    <th>{{ t("lab.labo") }}</th>
                    <th>{{ t("lab.dents") }}</th>
                    <th>{{ t("lab.teinte") }}</th>
                    <th class="num">{{ t("lab.prix") }}</th>
                    <th>{{ t("lab.date_envoi") }}</th>
                    <th>{{ t("lab.date_souhaitee") }}</th>
                    <th>{{ t("lab.recu_le") }}</th>
                    <th>{{ t("status.envoye") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="o in labOrders" :key="o.id">
                    <td style="font-weight:600;">{{ workTypeLabel(o.work_type) }}</td>
                    <td>{{ o.lab.name }}</td>
                    <td class="small">{{ o.teeth || "—" }}</td>
                    <td class="small">{{ o.shade || "—" }}</td>
                    <td class="num">{{ money.fmt(o.price) }}</td>
                    <td class="small muted">{{ dates.fmtDate(o.sent_date) }}</td>
                    <td class="small muted">{{ dates.fmtDate(o.due_date) }}</td>
                    <td class="small muted">{{ dates.fmtDate(o.received_date) }}</td>
                    <td><span class="badge" :class="`badge-${o.status}`">{{ t(`status.${o.status}`) }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>

      <!-- Médical -->
      <template v-if="tab === 'medical'">
        <div class="card" style="max-width:560px;">
          <h2 class="section-title" style="margin-bottom:16px;">{{ t("medical.title") }}</h2>
          <div v-for="f in MED_FIELDS" :key="f" class="money-row">
            <span class="money-label">{{ t(`medical.${f}`) }}</span>
            <input
              v-model="medicalForm[f] as boolean"
              type="checkbox"
              style="width:18px;height:18px;"
              @change="medicalDirty = true"
            >
          </div>
          <div class="field" style="margin-top:12px;">
            <label for="med-autre">{{ t("medical.autre") }}</label>
            <textarea id="med-autre" v-model="medicalForm.autre as string" class="textarea" @input="medicalDirty = true" />
          </div>
          <div style="margin-top:16px;display:flex;justify-content:flex-end;">
            <button class="btn btn-primary" :disabled="medicalSaving || !medicalDirty" @click="saveMedical">
              {{ t("common.save") }}
            </button>
          </div>
        </div>
      </template>

      <!-- Traitements -->
      <template v-if="tab === 'traitements'">
        <div class="card" style="padding:0;">
          <div v-if="!treatments.length" class="empty-state">{{ t("treatments.aucun") }}</div>
          <table v-else class="table">
            <thead>
              <tr>
                <th>{{ t("treatments.title") }}</th>
                <th>{{ t("treatments.dent") }}</th>
                <th style="text-align:end;">{{ t("treatments.prix") }}</th>
                <th>{{ t("appointment.date") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tr in treatments" :key="tr.id">
                <td>
                  {{ tr.name }}
                  <div v-if="tr.note" class="small muted">{{ tr.note }}</div>
                </td>
                <td>{{ tr.tooth ?? "—" }}</td>
                <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(tr.price) }}</td>
                <td class="small muted">{{ dates.fmtDate(tr.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <!-- Odontogramme -->
      <template v-if="tab === 'odontogramme'">
        <div class="odonto-split-layout">
          <div class="card odonto-chart-card" style="overflow-x:auto;">
            <div class="odonto-head">
              <div class="odonto-title-group">
                <AppIcon name="tooth" size="20" class="odonto-title-icon" />
                <h2 class="section-title">{{ t("odontogram.title") }}</h2>
              </div>
              <div class="seg">
                <button
                  type="button"
                  class="seg-btn"
                  :class="{ active: dentition === 'permanente' }"
                  @click="dentition = 'permanente'"
                >
                  {{ t("odontogram.permanentes") }}
                </button>
                <button
                  type="button"
                  class="seg-btn"
                  :class="{ active: dentition === 'temporaire' }"
                  @click="dentition = 'temporaire'"
                >
                  {{ t("odontogram.temporaires") }}
                </button>
              </div>
            </div>
            <OdontogramToothChart
              :conditions="conditions"
              :treatments="odontoTreatments"
              :selected="selectedTooth"
              :dentition="dentition"
              @select="onSelectTooth"
            />
          </div>
          <div class="odonto-side-pane">
            <div v-if="selectedTooth" class="odonto-tooth-inspector">
              <OdontogramConditionPanel
                :tooth="selectedTooth"
                :conditions="conditions"
                :treatments="toothTreatments(selectedTooth)"
                :busy="odontoBusy"
                @apply="applyCondition"
                @close="selectedTooth = null"
              />
              <div class="card" style="margin-top:12px;padding:12px;">
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  style="width:100%;"
                  @click="openTreatmentForTooth(selectedTooth)"
                >
                  <AppIcon name="plus" size="14" />
                  <span>{{ t("treatments.ajout") }} #{{ selectedTooth }}</span>
                </button>
              </div>
            </div>
            <div v-else class="card empty-state odonto-empty-pane">
              <AppIcon name="tooth" size="32" class="muted" style="margin-bottom:8px;opacity:0.6;" />
              <div style="font-weight:600;margin-bottom:4px;">{{ t("odontogram.hint") }}</div>
              <div class="small muted">
                {{ t("odontogram.traitements_lies") }} {{ Object.values(odontoTreatments).reduce((n, l) => n + l.length, 0) }}
              </div>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top:16px;padding:0;">
          <h2 class="section-title" style="padding:16px 16px 0;">{{ t("odontogram.historique") }}</h2>
          <div v-if="!toothHistory.length" class="empty-state">{{ t("odontogram.historique_vide") }}</div>
          <table v-else class="table">
            <tbody>
              <tr v-for="h in toothHistory.slice(0, 30)" :key="h.id">
                <td style="width:70px;font-weight:600;">{{ h.tooth }}</td>
                <td>{{ t(h.condition === "sain" ? "odontogram.sain" : `odontogram.cond_${h.condition}`) }}<span v-if="h.surface" class="small muted"> · {{ h.surface }}</span></td>
                <td style="width:90px;">
                  <span :class="h.action === 'clear' ? 'badge badge-cancelled' : 'badge badge-en_cours'">
                    {{ t(h.action === "clear" ? "odontogram.hist_clear" : "odontogram.hist_set") }}
                  </span>
                </td>
                <td class="small muted">{{ dates.fmtDateTime(h.changed_at) }}</td>
                <td class="small muted">{{ h.changed_by ?? "" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <!-- Paiements -->
      <template v-if="tab === 'paiements'">
        <div style="display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:start;">
          <div class="card" v-if="ledger">
            <div class="money-row">
              <span class="money-label">{{ t("resume.total") }}</span>
              <span class="money-value">{{ money.fmt(ledger.total) }}</span>
            </div>
            <div class="money-row">
              <span class="money-label">{{ t("resume.paye") }}</span>
              <span class="money-value" style="color:var(--color-success);">{{ money.fmt(ledger.paye) }}</span>
            </div>
            <div class="money-row">
              <span class="money-label">{{ t("resume.reste") }}</span>
              <span class="money-value" :class="{ 'money-reste': Number(ledger.reste) > 0 }">
                {{ money.fmt(ledger.reste) }}
              </span>
            </div>
            <div style="margin-top:16px;text-align:end;">
              <button class="btn btn-primary" :disabled="!hasReste" @click="openPayment">
                {{ t("payments.encaisser") }}
              </button>
            </div>
          </div>
          <div class="card" style="padding:0;">
            <div v-if="!ledger?.payments?.length" class="empty-state">{{ t("payments.aucun") }}</div>
            <table v-else class="table">
              <thead>
                <tr>
                  <th>{{ t("appointment.date") }}</th>
                  <th style="text-align:end;">{{ t("payments.montant") }}</th>
                  <th>{{ t("common.notes") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in ledger.payments" :key="p.id">
                  <td class="small muted">{{ dates.fmtDateTime(p.created_at) }}</td>
                  <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(p.amount) }}</td>
                  <td class="small">{{ p.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- Documents -->
      <template v-if="tab === 'documents'">
        <div class="card" style="padding:0;">
          <div v-if="!docs.length" class="empty-state">{{ t("documents.aucun") }}</div>
          <table v-else class="table">
            <tbody>
              <tr v-for="d in docs" :key="d.id" class="row-link" @click="navigateTo(`/documents?open=${d.id}&patient=${patientId}`)">
                <td>{{ t(`documents.${d.doc_type}`) }}</td>
                <td>{{ d.title }}</td>
                <td class="small muted">{{ dates.fmtDate(d.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card" style="margin-top:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
            <h2 class="section-title">{{ t("documents.pieces_jointes") }}</h2>
            <div style="display:flex;gap:8px;align-items:center;">
              <input
                id="att-file"
                ref="fileInputRef"
                type="file"
                class="visually-hidden"
                :accept="ACCEPTED_FILE_TYPES"
                @change="onAttachmentPicked"
              >
              <label
                for="att-file"
                class="btn btn-secondary"
                tabindex="0"
                @keydown.enter.prevent="onClickFileLabel"
                @keydown.space.prevent="onClickFileLabel"
              >{{ uploading ? t("documents.saving_att") : t("documents.ajouter_piece") }}</label>
            </div>
          </div>
          <p class="small muted" style="margin:0 0 12px;">{{ t("documents.att_hint") }}</p>
          <div v-if="!attachments.length" class="empty-state">{{ t("documents.att_aucune") }}</div>
          <table v-else class="table">
            <thead>
              <tr>
                <th>{{ t("documents.nom_piece") }}</th>
                <th class="num">{{ t("documents.att_taille") }}</th>
                <th>{{ t("documents.date") }}</th>
                <th style="width:1%;" />
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in attachments" :key="a.id">
                <td>{{ a.original_name }}</td>
                <td class="num small" style="font-variant-numeric:tabular-nums;">{{ fmtFileSize(a.size_bytes) }}</td>
                <td class="small muted">{{ dates.fmtDateTime(a.created_at) }}</td>
                <td>
                  <div style="display:flex;gap:6px;justify-content:flex-end;">
                    <a
                      :href="`/api/patients/${patientId}/attachments/${a.id}/file`"
                      target="_blank"
                      rel="noopener"
                      class="btn btn-text btn-sm"
                    >{{ t("documents.att_telecharger") }}</a>
                    <button
                      class="btn btn-text btn-sm"
                      style="color:var(--color-danger);"
                      :disabled="deletingAttachmentId !== null"
                      @click="deleteAttachment(a)"
                    >{{ t("common.delete") }}</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>

    <!-- Note dialog -->
    <AppDialog :open="showNote" :title="t('notes.nouvelle_note')" @close="showNote = false">
        <div class="field" style="margin-bottom:12px;">
          <label for="note-motif">{{ t("notes.motif") }}</label>
          <input id="note-motif" v-model="noteForm.motif" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="note-diag">{{ t("notes.diagnostic") }}</label>
          <input id="note-diag" v-model="noteForm.diagnostic" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="note-trt">{{ t("notes.traitement") }}</label>
          <input id="note-trt" v-model="noteForm.traitement" class="input">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="note-rem">{{ t("notes.remarques") }}</label>
          <textarea id="note-rem" v-model="noteForm.remarques" class="textarea" />
        </div>
        <div v-if="noteError" class="alert alert-error">{{ t(noteError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showNote = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="noteSaving" @click="saveNote">{{ t("common.save") }}</button>
        </div>
    </AppDialog>

    <!-- Treatment dialog -->
    <AppDialog :open="showTreatment" :title="t('treatments.ajout')" @close="showTreatment = false">
        <div class="field" style="margin-bottom:12px;">
          <label for="trt-item">{{ t("treatments.title") }}</label>
          <select id="trt-item" v-model="treatmentForm.catalog_item_id" class="select">
            <option value="">—</option>
            <option v-for="i in catalog" :key="i.id" :value="String(i.id)">
              {{ i.name }} ({{ money.fmt(i.default_price) }})
            </option>
          </select>
        </div>
        <div style="display:flex;gap:12px;">
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="trt-tooth">{{ t("treatments.dent") }} ({{ t("common.optional") }})</label>
            <input id="trt-tooth" v-model="treatmentForm.tooth" class="input" inputmode="numeric">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="trt-price">{{ t("treatments.prix") }}</label>
            <input
              id="trt-price"
              v-model="treatmentForm.price"
              class="input"
              inputmode="decimal"
              :placeholder="selectedCatalogItem ? selectedCatalogItem.default_price : ''"
            >
          </div>
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="trt-note">{{ t("common.notes") }}</label>
          <input id="trt-note" v-model="treatmentForm.note" class="input">
        </div>
        <div v-if="treatmentError" class="alert alert-error">{{ t(treatmentError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showTreatment = false">{{ t("common.cancel") }}</button>
          <button
            class="btn btn-primary"
            :disabled="treatmentSaving || !treatmentForm.catalog_item_id"
            @click="saveTreatment"
          >
            {{ t("common.add") }}
          </button>
        </div>
    </AppDialog>

    <!-- Payment dialog -->
    <AppDialog :open="showPayment" :title="t('payments.encaisser')" @close="showPayment = false">
        <p v-if="ledger" class="small muted" style="margin-bottom:12px;">
          {{ t("payments.reste_max") }} : {{ money.fmt(ledger.reste) }}
        </p>
        <div class="field" style="margin-bottom:12px;">
          <label for="pay-amount">{{ t("payments.montant") }}</label>
          <input id="pay-amount" v-model="paymentForm.amount" class="input" inputmode="decimal">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="pay-note">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
          <input id="pay-note" v-model="paymentForm.note" class="input">
        </div>
        <div v-if="paymentError" class="alert alert-error">{{ t(paymentError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showPayment = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="paymentSaving" @click="savePayment">
            {{ t("common.save") }}
          </button>
        </div>
    </AppDialog>

    <!-- Edit patient dialog -->
    <AppDialog :open="showEdit" :title="t('patients.edit_title')" @close="showEdit = false">
        <div style="display:flex;gap:12px;">
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-nom">{{ t("patients.nom") }}</label>
            <input id="ed-nom" v-model="editForm.nom" class="input">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-prenom">{{ t("patients.prenom") }}</label>
            <input id="ed-prenom" v-model="editForm.prenom" class="input">
          </div>
        </div>
        <div style="display:flex;gap:12px;">
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-tel">{{ t("patients.telephone") }}</label>
            <input id="ed-tel" v-model="editForm.telephone" class="input" inputmode="tel">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-tel2">{{ t("patients.telephone2") }}</label>
            <input id="ed-tel2" v-model="editForm.telephone2" class="input" inputmode="tel">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-bday">{{ t("patients.date_naissance") }}</label>
            <input id="ed-bday" v-model="editForm.date_naissance" class="input" type="date">
          </div>
        </div>
        <div style="display:flex;gap:12px;">
          <div class="field" style="margin-bottom:12px;flex:2;">
            <label for="ed-adresse">{{ t("patients.adresse") }}</label>
            <input id="ed-adresse" v-model="editForm.adresse" class="input">
          </div>
          <div class="field" style="margin-bottom:12px;flex:1;">
            <label for="ed-wilaya">{{ t("patients.wilaya") }}</label>
            <input id="ed-wilaya" v-model="editForm.wilaya" class="input">
          </div>
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="ed-notes">{{ t("patients.notes") }}</label>
          <textarea id="ed-notes" v-model="editForm.notes" class="textarea" />
        </div>
        <div v-if="editError" class="alert alert-error">{{ t(editError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showEdit = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="editSaving" @click="saveEdit">{{ t("common.save") }}</button>
        </div>
    </AppDialog>

    <!-- Appointment dialog -->
    <AppDialog :open="showRdv" :title="t('today.nouveau_rdv')" @close="showRdv = false">
      <div style="display:flex;gap:12px;">
        <div class="field" style="margin-bottom:12px;flex:1;">
          <label for="p-rdv-date">{{ t("appointment.date") }}</label>
          <input id="p-rdv-date" v-model="rdvForm.date" type="date" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;flex:1;">
          <label for="p-rdv-time">{{ t("appointment.time") }} ({{ t("common.optional") }})</label>
          <input id="p-rdv-time" v-model="rdvForm.time" type="time" class="input">
        </div>
      </div>
      <div class="field" style="margin-bottom:12px;">
        <label for="p-rdv-tnote">{{ t("appointment.time") }} — texte ({{ t("common.optional") }})</label>
        <input id="p-rdv-tnote" v-model="rdvForm.time_note" class="input" placeholder="matin, vers 10h…">
      </div>
      <div class="field" style="margin-bottom:16px;">
        <label for="p-rdv-motif">{{ t("appointment.motif") }} ({{ t("common.optional") }})</label>
        <input id="p-rdv-motif" v-model="rdvForm.motif" class="input">
      </div>
      <div v-if="rdvError" class="alert alert-error">{{ t(rdvError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showRdv = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="rdvSaving" @click="saveRdv">{{ t("common.save") }}</button>
      </div>
    </AppDialog>
  </div>
</template>

<style scoped>
.patient-page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Patient Hero Card */
.patient-hero-card {
  padding: 18px 24px;
  background: var(--color-surface, #ffffff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.patient-hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hero-back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted, #64748b);
  transition: color 0.12s ease;
}

.hero-back-link:hover {
  color: var(--color-primary, #0040dc);
}

.patient-code-badge {
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--color-surface-muted, #f1f5f9);
  color: var(--color-text-muted, #64748b);
  border: 1px solid var(--color-border, #e2e8f0);
}

.patient-hero-body {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.patient-avatar-box {
  width: 58px;
  height: 58px;
  border-radius: 16px;
  background: var(--color-primary-soft, #eef2ff);
  color: var(--color-primary, #0040dc);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--color-primary, #0040dc) 20%, transparent);
}

.patient-identity-box {
  flex: 1;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.patient-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.patient-full-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #0f172a);
  letter-spacing: -0.01em;
  margin: 0;
}

.patient-chips-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.patient-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--color-text-muted, #64748b);
  background: var(--color-canvas, #f8fafc);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--color-border-subtle, #edf2f7);
}

.patient-chip-link {
  text-decoration: none;
  color: var(--color-text, #0f172a);
  font-weight: 550;
  transition: all 0.12s ease;
}

.patient-chip-link:hover {
  border-color: var(--color-primary, #0040dc);
  color: var(--color-primary, #0040dc);
}

.patient-medical-alert-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 600;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  padding: 4px 10px;
  border-radius: 6px;
  width: fit-content;
}

.alert-icon {
  flex-shrink: 0;
}

/* Ledger Balance Strip */
.patient-ledger-pill {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--color-canvas, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 10px;
  padding: 10px 16px;
}

.ledger-stat {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-muted, #64748b);
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.stat-val {
  font-size: 15px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-text, #0f172a);
}

.stat-success {
  color: var(--color-success, #10b981);
}

.stat-danger {
  color: var(--color-danger, #ef4444);
}

.ledger-stat-divider {
  width: 1px;
  height: 28px;
  background: var(--color-border, #e2e8f0);
}

/* Patient Actions Bar */
.patient-actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--color-border-subtle, #f1f5f9);
  padding-top: 14px;
  flex-wrap: wrap;
}

.action-buttons-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-encaissement {
  background: var(--color-primary, #0040dc);
}

/* Segmented Tabs */
.segmented-tabs-wrapper {
  overflow-x: auto;
  padding-bottom: 2px;
}

.segmented-tabs {
  display: inline-flex;
  background: var(--color-surface, #ffffff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 10px;
  padding: 4px;
  gap: 4px;
}

.segmented-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 550;
  color: var(--color-text-muted, #64748b);
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
  white-space: nowrap;
}

.segmented-tab-btn:hover {
  color: var(--color-text, #0f172a);
  background: var(--color-canvas, #f8fafc);
}

.segmented-tab-btn.active {
  background: var(--color-primary-soft, #eef2ff);
  color: var(--color-primary, #0040dc);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 64, 220, 0.08);
}

/* Odontogram Split Layout */
.odonto-split-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  align-items: start;
}

.odonto-chart-card {
  padding: 16px;
}

.odonto-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}

.odonto-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.odonto-title-icon {
  color: var(--color-primary, #0040dc);
}

.odonto-side-pane {
  position: sticky;
  top: 76px;
}

.odonto-empty-pane {
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

@media (max-width: 1024px) {
  .odonto-split-layout {
    grid-template-columns: 1fr;
  }
  .odonto-side-pane {
    position: static;
  }
}
</style>
