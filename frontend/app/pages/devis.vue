<script setup lang="ts">
/**
 * Devis & plans de traitement: create quote from catalog or free line,
 * status flow draft → sent → accepted/rejected, printable plan.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const money = useMoney()
const toast = useToast()

interface PatientRow { id: number, nom: string, prenom: string, telephone: string }
interface CatalogItem { id: number, name: string, category: string, default_price: string, is_active: boolean }
interface DevisItem {
  id: number, catalog_item_id: number | null, label: string, tooth: number | null,
  quantity: number, unit_price: string, line_total: string,
}
interface Devis {
  id: number, patient_id: number, status: string, issue_date: string, due_date: string | null,
  notes: string, created_at: string, total?: string, items?: DevisItem[],
}
interface DevisRow extends Devis { patient_name?: string, patient?: PatientRow }
interface Clinic { clinic_name: string, doctor_name: string, address: string, phone: string, header_note: string, footer_note: string }

const STATUS_KEYS: Record<string, string> = {
  draft: "devis.etat_brouillon",
  sent: "devis.etat_envoye",
  accepted: "devis.etat_accepte",
  rejected: "devis.etat_refuse",
  expired: "devis.etat_expire",
  cancelled: "devis.etat_annule",
}

function statusBadge(status: string) {
  if (status === "accepted") return "badge badge-ok"
  if (status === "rejected" || status === "cancelled" || status === "expired") return "badge badge-error"
  if (status === "sent") return "badge badge-warn"
  return "badge"
}

const devis = ref<DevisRow[]>([])
const catalog = ref<CatalogItem[]>([])
const loading = ref(true)
const errorMsg = ref("")

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const [d, c] = await Promise.all([
      api.get<{ devis: DevisRow[] }>("/devis"),
      api.get<{ items: CatalogItem[] }>("/clinical/catalog", { include_inactive: "false" }),
    ])
    devis.value = d.devis
    catalog.value = c.items.filter(i => i.is_active)
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await load()

// ---- Create dialog ---------------------------------------------------------
const showNew = ref(false)
const saving = ref(false)
const formError = ref("")
const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const pickedPatient = ref<PatientRow | null>(null)
const form = ref({ issue_date: new Date().toISOString().slice(0, 10), due_date: "", notes: "" })
const items = ref<{ catalog_item_id: number | null, label: string, tooth: string, quantity: number, unit_price: string }[]>([])
let patientTimer: ReturnType<typeof setTimeout> | undefined

watch(patientQuery, (q) => {
  clearTimeout(patientTimer)
  if (!q.trim()) {
    patientResults.value = []
    return
  }
  patientTimer = setTimeout(async () => {
    try {
      const data = await api.get<{ patients: PatientRow[] }>("/patients", { q: q.trim(), per_page: 8 })
      patientResults.value = data.patients
    }
    catch {
      patientResults.value = []
    }
  }, 200)
})

function openNew() {
  pickedPatient.value = null
  patientQuery.value = ""
  items.value = [{ catalog_item_id: null, label: "", tooth: "", quantity: 1, unit_price: "" }]
  form.value = { issue_date: new Date().toISOString().slice(0, 10), due_date: "", notes: "" }
  formError.value = ""
  showNew.value = true
}

function pickCatalog(idx: number, ev: Event) {
  const id = Number((ev.target as HTMLSelectElement).value)
  const item = catalog.value.find(i => i.id === id)
  const line = items.value[idx]
  if (!line) return
  if (item) {
    line.catalog_item_id = item.id
    line.label = item.name
    line.unit_price = item.default_price
    if (line.quantity < 1) line.quantity = 1
  }
  else {
    line.catalog_item_id = null
    line.label = ""
    line.unit_price = ""
  }
}

function addLine() {
  items.value.push({ catalog_item_id: null, label: "", tooth: "", quantity: 1, unit_price: "" })
}

function removeLine(idx: number) {
  items.value.splice(idx, 1)
}

const formTotal = computed(() =>
  items.value.reduce((s, i) => s + (Number(i.unit_price) || 0) * (Number(i.quantity) || 0), 0),
)

function editableItemPayload() {
  return items.value.map(i => ({
    catalog_item_id: i.catalog_item_id,
    label: i.label,
    tooth: i.tooth === "" ? null : Number(i.tooth),
    quantity: Number(i.quantity) || 1,
    unit_price: Number(i.unit_price) || 0,
  }))
}

async function create() {
  if (!pickedPatient.value) {
    formError.value = "errors.patient_required"
    return
  }
  saving.value = true
  formError.value = ""
  try {
    await api.post("/devis", {
      patient_id: pickedPatient.value.id,
      items: editableItemPayload(),
      issue_date: form.value.issue_date,
      due_date: form.value.due_date || null,
      notes: form.value.notes,
    })
    toast.success("common.save")
    showNew.value = false
    await load()
  }
  catch (e: any) {
    formError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

// ---- Detail ----------------------------------------------------------------
const current = ref<Devis | null>(null)
const currentPatient = ref<PatientRow | null>(null)
const clinic = ref<Clinic | null>(null)
const detailError = ref("")
const editing = ref(false)
const editItems = ref<typeof items.value>([])
const editNotes = ref("")

const isLocked = computed(() => current.value !== null && current.value.status !== "draft")

async function openDevis(id: number) {
  detailError.value = ""
  loading.value = true
  try {
    const data = await api.get<{ devis: Devis, clinic: Clinic }>(`/devis/${id}`)
    current.value = data.devis
    clinic.value = data.clinic
    editing.value = false
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

function startEdit() {
  if (!current.value) return
  editItems.value = (current.value.items ?? []).map(i => ({
    catalog_item_id: i.catalog_item_id,
    label: i.label,
    tooth: i.tooth === null ? "" : String(i.tooth),
    quantity: i.quantity,
    unit_price: i.unit_price,
  }))
  editNotes.value = current.value.notes ?? ""
  editing.value = true
}

async function saveEdit() {
  if (!current.value) return
  saving.value = true
  detailError.value = ""
  try {
    await api.put(`/devis/${current.value.id}`, {
      items: editItems.value.map(i => ({
        catalog_item_id: i.catalog_item_id,
        label: i.label,
        tooth: i.tooth === "" ? null : Number(i.tooth),
        quantity: Number(i.quantity) || 1,
        unit_price: Number(i.unit_price) || 0,
      })),
      notes: editNotes.value,
      due_date: current.value.due_date,
    })
    toast.success("common.save")
    editing.value = false
    await openDevis(current.value.id)
  }
  catch (e: any) {
    detailError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

async function changeStatus(status: string) {
  if (!current.value) return
  detailError.value = ""
  try {
    const data = await api.post<{ devis: Devis }>(`/devis/${current.value.id}/status`, { status })
    current.value = data.devis
    toast.success("common.save")
  }
  catch (e: any) {
    detailError.value = e?.messageKey ?? "errors.generic"
  }
}

function printDevis() {
  window.print()
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("devis.title") }}</h1>
        <p class="page-subtitle">{{ t("devis.subtitle") }}</p>
      </div>
      <button class="btn btn-primary" @click="openNew">
        {{ t("devis.nouveau") }}
      </button>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <!-- Detail -->
    <div v-if="current" class="card print-area dv-card" style="max-width:760px;">
      <AppPrintLetter :settings="clinic" />
      <div class="dv-meta">
        <div>
          <p v-if="currentPatient" class="dv-patient">
            <strong>{{ currentPatient.nom }} {{ currentPatient.prenom }}</strong>
            <span class="small muted" style="margin-inline-start:8px;">{{ currentPatient.telephone }}</span>
          </p>
          <p class="small muted" style="margin:0;">
            {{ t("documents.date") }} : {{ dates.fmtDate(current.issue_date) }}
            <template v-if="current.due_date">
              <span style="margin-inline-start:12px;">{{ t("devis.validite") }} : {{ dates.fmtDate(current.due_date) }}</span>
            </template>
          </p>
        </div>
        <div class="no-print" style="text-align:end;">
          <span :class="statusBadge(current.status)" style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);">
            {{ t(STATUS_KEYS[current.status] ?? "devis.etat_brouillon") }}
          </span>
        </div>
      </div>

      <!-- Items: read / edit -->
      <div v-if="editing">
        <div v-for="(line, idx) in editItems" :key="idx" style="display:flex;gap:8px;align-items:end;margin-bottom:8px;flex-wrap:wrap;">
          <select class="select" style="width:200px;" :value="line.catalog_item_id ?? ''" @change="pickCatalog(idx, $event)">
            <option value="">{{ t("stock.traitement_catalogue") }}</option>
            <option v-for="c in catalog" :key="c.id" :value="c.id">{{ c.name }} — {{ money.fmt(c.default_price) }}</option>
          </select>
          <input v-model="line.label" class="input" style="flex:1;min-width:160px;" :placeholder="t('devis.ligne', { n: idx + 1 })">
          <input v-model="line.tooth" class="input" style="width:70px;" inputmode="numeric" :placeholder="t('treatments.dent')">
          <input v-model.number="line.quantity" type="number" min="1" max="20" class="input" style="width:64px;">
          <input v-model="line.unit_price" class="input" style="width:110px;" inputmode="decimal" :placeholder="t('devis.prix_unitaire')">
          <button class="btn btn-text btn-sm" @click="removeLine(idx)">✕</button>
        </div>
        <button class="btn btn-text btn-sm" style="margin-bottom:12px;" @click="addLine">
          {{ t("devis.ajouter_ligne") }}
        </button>
        <div class="field" style="margin-bottom:16px;">
          <label for="devis-notes">{{ t("devis.notes_lbl") }}</label>
          <textarea id="devis-notes" v-model="editNotes" class="textarea" rows="2" />
        </div>
      </div>
      <div v-else>
        <table class="table">
          <thead>
            <tr>
              <th>{{ t("devis.ligne", { n: "#" }) }}</th>
              <th>{{ t("treatments.dent") }}</th>
              <th>{{ t("devis.quantite") }}</th>
              <th class="num" style="text-align:end;">{{ t("devis.prix_unitaire") }}</th>
              <th class="num" style="text-align:end;">{{ t("devis.total") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in current.items" :key="item.id">
              <td>{{ item.label }}</td>
              <td>{{ item.tooth ?? "—" }}</td>
              <td>{{ item.quantity }}</td>
              <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(item.unit_price) }}</td>
              <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(item.line_total) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="4" style="text-align:end;font-weight:650;">{{ t("devis.total") }}</td>
              <td style="text-align:end;font-weight:650;font-variant-numeric:tabular-nums;">
                {{ money.fmt(String(current.total ?? "0")) }}
              </td>
            </tr>
          </tfoot>
        </table>
        <p v-if="current.due_date" class="small muted" style="margin-top:8px;">
          {{ t("devis.validite") }} : {{ dates.fmtDate(current.due_date) }}
        </p>
        <p v-if="current.notes" class="small muted" style="margin-top:12px;">{{ current.notes }}</p>
        <AppPrintFoot
          date=""
          :date-caption="t('documents.date')"
          :signs="[t('devis.print_sign_praticien'), t('devis.print_accord')]"
        />
      </div>

      <div v-if="detailError" class="alert alert-error" style="margin-top:12px;">{{ t(detailError) }}</div>
      <div class="dialog-actions no-print" style="margin-top:16px;">
        <button class="btn btn-secondary" @click="current = null">{{ t("common.back") }}</button>
        <!-- draft actions -->
        <template v-if="current.status === 'draft'">
          <button v-if="!editing" class="btn btn-secondary" @click="startEdit">{{ t("common.edit") }}</button>
          <button v-if="editing" class="btn btn-secondary" :disabled="saving" @click="saveEdit">{{ t("common.save") }}</button>
          <button v-if="editing" class="btn btn-text" @click="editing = false;">{{ t("common.cancel") }}</button>
          <button v-if="!editing" class="btn btn-primary" @click="changeStatus('sent')">{{ t("devis.envoyer") }}</button>
        </template>
        <!-- sent actions -->
        <template v-else-if="current.status === 'sent'">
          <button class="btn btn-primary" @click="changeStatus('accepted')">{{ t("devis.accepter") }}</button>
          <button class="btn btn-secondary" @click="changeStatus('rejected')">{{ t("devis.refuser") }}</button>
          <button class="btn btn-text" style="color:var(--color-danger);" @click="changeStatus('cancelled')">
            {{ t("devis.annuler") }}
          </button>
        </template>
        <button v-if="!editing" class="btn btn-secondary" @click="printDevis">{{ t("common.print") }}</button>
      </div>
      <p v-if="isLocked && !editing" class="small muted no-print" style="margin-top:8px;">{{ t("devis.non_editable") }}</p>
    </div>

    <!-- List -->
    <template v-else>
      <div v-if="loading" class="card" style="padding:16px;" aria-hidden="true">
        <div v-for="i in 5" :key="i" class="skeleton skeleton-line" :class="i % 2 ? 'w-60' : 'w-40'" />
      </div>
      <div v-else-if="!devis.length" class="card empty-state">
        <span class="empty-icon">▤</span>
        {{ t("devis.aucun") }}
        <div class="empty-hint">{{ t("devis.nouveau") }}</div>
      </div>
      <div v-else class="card" style="padding:0;">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t("appointment.patient") }}</th>
              <th>{{ t("appointment.date") }}</th>
              <th>{{ t("devis.lignes") }}</th>
              <th class="num" style="text-align:end;">{{ t("devis.total") }}</th>
              <th>{{ t("devis.etat") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in devis" :key="d.id" class="row-link" @click="openDevis(d.id)">
              <td><strong>{{ d.patient_name ?? ("Patient #" + d.patient_id) }}</strong></td>
              <td class="small muted" style="font-variant-numeric:tabular-nums;">{{ dates.fmtDate(d.issue_date) }}</td>
              <td class="small muted">{{ d.items?.length ?? 0 }}</td>
              <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(String(d.total ?? "0")) }}</td>
              <td>
                <span :class="statusBadge(d.status)" style="padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);display:inline-block;">
                  {{ t(STATUS_KEYS[d.status] ?? "devis.etat_brouillon") }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Create devis dialog -->
    <AppDialog :open="showNew" :title="t('devis.nouveau')" @close="showNew = false">
      <template v-if="!pickedPatient">
        <div style="position:relative;">
          <input
            v-model="patientQuery"
            class="input"
            :placeholder="t('common.search_placeholder')"
            :aria-label="t('common.search')"
            autofocus
          >
          <div v-if="patientResults.length" class="card" style="padding:0;margin-top:4px;position:absolute;z-index:30;width:100%;">
            <div
              v-for="p in patientResults"
              :key="p.id"
              style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--color-border);"
              @click="pickedPatient = p; patientResults = []; patientQuery = ''"
            >
              <strong>{{ p.nom }} {{ p.prenom }}</strong>
              <span class="small muted" style="margin-inline-start:8px;">{{ p.telephone }}</span>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <p class="small" style="margin-bottom:12px;">
          <strong>{{ pickedPatient.nom }} {{ pickedPatient.prenom }}</strong>
          <span class="muted" style="margin-inline-start:8px;">{{ pickedPatient.telephone }}</span>
          <button class="btn btn-text btn-sm" style="margin-inline-start:8px;" @click="pickedPatient = null">
            {{ t("common.back") }}
          </button>
        </p>

        <div class="field" style="margin-bottom:12px;">
          <label for="devis-date">{{ t("appointment.date") }}</label>
          <input id="devis-date" v-model="form.issue_date" type="date" class="input">
        </div>
        <div style="display:flex;gap:12px;margin-bottom:12px;">
          <div class="field" style="flex:1;">
            <label for="devis-due">{{ t("devis.validite") }} ({{ t("common.optional") }})</label>
            <input id="devis-due" v-model="form.due_date" type="date" class="input">
          </div>
        </div>

        <div class="nav-group-label" style="margin-bottom:8px;">{{ t("devis.lignes") }}</div>
        <div v-for="(line, idx) in items" :key="idx" style="display:flex;gap:8px;align-items:end;margin-bottom:8px;flex-wrap:wrap;">
          <select class="select" style="width:180px;" :value="line.catalog_item_id ?? ''" @change="pickCatalog(idx, $event)">
            <option value="">{{ t("stock.traitement_catalogue") }}</option>
            <option v-for="c in catalog" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <input v-model="line.label" class="input" style="flex:1;min-width:150px;" :placeholder="t('devis.ligne', { n: idx + 1 })">
          <input v-model="line.tooth" class="input" style="width:64px;" inputmode="numeric" :placeholder="t('treatments.dent')">
          <input v-model.number="line.quantity" type="number" min="1" max="20" class="input" style="width:60px;">
          <input v-model="line.unit_price" class="input" style="width:100px;" inputmode="decimal" :placeholder="t('devis.prix_unitaire')">
          <button class="btn btn-text btn-sm" @click="removeLine(idx)">✕</button>
        </div>
        <button class="btn btn-text btn-sm" @click="addLine">{{ t("devis.ajouter_ligne") }}</button>

        <p style="text-align:end;font-weight:650;margin-top:12px;">
          {{ t("devis.total") }} : {{ money.fmt(String(formTotal)) }}
        </p>
        <div class="field" style="margin-top:8px;">
          <label for="devis-notes-new">{{ t("devis.notes_lbl") }}</label>
          <textarea id="devis-notes-new" v-model="form.notes" class="textarea" rows="2" />
        </div>
      </template>

      <div v-if="formError" class="alert alert-error">{{ t(formError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showNew = false">{{ t("common.cancel") }}</button>
        <button v-if="pickedPatient" class="btn btn-primary" :disabled="saving" @click="create">
          {{ t("common.save") }}
        </button>
      </div>
    </AppDialog>
  </div>
</template>

<style scoped>
.dv-meta {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-top: 12px;
}

.dv-patient {
  margin: 0 0 4px;
}

@media print {
  .dv-card {
    border: none;
    box-shadow: none;
    border-radius: 0;
    padding: 0;
    background: #fff;
  }
}
</style>
