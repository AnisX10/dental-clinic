<script setup lang="ts">
/**
 * Patient file (DESIGN.md §7.3): summary-first with tabs
 * Résumé / Médical / Traitements / Paiements / Documents.
 * Quick actions: Nouvelle note · Ajouter un traitement · Odontogramme.
 */
const route = useRoute()
const patientId = Number(route.params.id)
const { t } = useI18n()
const api = useApi()
const money = useMoney()
const dates = useDates()
const auth = useAuth()
const toast = useToast()

interface Patient {
  id: number, code: string, nom: string, prenom: string, telephone: string,
  telephone2: string, adresse: string, wilaya: string, notes: string,
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
const tab = ref<"resume" | "medical" | "traitements" | "paiements" | "documents">("resume")

const notes = ref<Note[]>([])
const treatments = ref<Treatment[]>([])
const ledger = ref<Ledger | null>(null)
const docs = ref<DocRow[]>([])
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
      tabLoaded.value.documents = true
    }
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
}
if (patient.value) await loadTab("resume")

function flash(messageKey: string) {
  toast.success(messageKey)
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
const editForm = ref({ nom: "", prenom: "", telephone: "", telephone2: "", adresse: "", wilaya: "", notes: "" })
const editSaving = ref(false)
const editError = ref("")

function openEdit() {
  const p = patient.value!
  editForm.value = {
    nom: p.nom, prenom: p.prenom, telephone: p.telephone, telephone2: p.telephone2,
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

const tabs = [
  { key: "resume", label: "patient_tabs.resume" },
  { key: "medical", label: "patient_tabs.medical" },
  { key: "traitements", label: "patient_tabs.traitements" },
  { key: "paiements", label: "patient_tabs.paiements" },
  { key: "documents", label: "patient_tabs.documents" },
] as const

function switchTab(key: typeof tab.value) {
  tab.value = key
  loadTab(key)
}

const hasReste = computed(() => ledger.value && Number(ledger.value.reste) > 0)
</script>

<template>
  <div>
    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div v-if="loading" style="max-width:840px;" aria-hidden="true">
      <div class="skeleton skeleton-line w-40" />
      <div class="skeleton skeleton-line w-60" />
      <div class="skeleton skeleton-line w-80" />
    </div>

    <template v-else-if="patient">
      <div class="toolbar">
        <div>
          <h1 class="page-title">{{ patient.nom }} {{ patient.prenom }}</h1>
          <p class="page-subtitle" style="font-variant-numeric:tabular-nums;">
            {{ patient.telephone }}
            <span v-if="patient.telephone2"> · {{ patient.telephone2 }}</span>
            <span v-if="patient.wilaya"> · {{ patient.wilaya }}</span>
          </p>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-secondary btn-sm" @click="openEdit">{{ t("common.edit") }}</button>
        </div>
      </div>

      <div class="toolbar" style="margin-bottom:16px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-primary" @click="showNote = true">{{ t("resume.nouvelle_note") }}</button>
          <button class="btn btn-secondary" @click="openTreatment">{{ t("resume.ajouter_traitement") }}</button>
          <NuxtLink to="/odontogramme" class="btn btn-secondary">{{ t("resume.odontogramme") }}</NuxtLink>
        </div>
        <button v-if="hasReste" class="btn btn-primary" @click="openPayment">
          {{ t("payments.encaisser") }}
        </button>
      </div>

      <div class="tabs">
        <button
          v-for="tb in tabs"
          :key="tb.key"
          class="tab"
          :class="{ active: tab === tb.key }"
          @click="switchTab(tb.key)"
        >
          {{ t(tb.label) }}
        </button>
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
  </div>
</template>
