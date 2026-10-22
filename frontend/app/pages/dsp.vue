<script setup lang="ts">
/**
 * DSP & CNAS (AS 2 feuilles de soins): per-patient register with acts,
 * 3-month deadline tracking and printable sheet.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const money = useMoney()
const auth = useAuth()
const toast = useToast()

interface PatientRow { id: number, nom: string, prenom: string, telephone: string }
interface PatientFull extends PatientRow { code: string }
interface Registry {
  id: number, patient_id: number, caisse: string, insured_nin: string,
  affiliation_no: string, beneficiary_relation: string, first_act_date: string,
  notes: string, deadline_date: string, days_to_deadline: number, act_count: number,
  patient: PatientRow & { code: string },
}
interface Act {
  id: number, act_date: string, tooth: number | null, act_label: string,
  act_code: string, coefficient: string, fee: string,
}
interface Clinic { clinic_name: string, doctor_name: string, address: string, phone: string, header_note: string, footer_note: string }

const meta = ref<{ caisses: string[], beneficiary_relations: string[], deadline_days: number }>({
  caisses: ["CNAS", "CASNOS"],
  beneficiary_relations: ["assure", "conjoint", "enfant", "autre"],
  deadline_days: 90,
})
const caisseFilter = ref("")
const search = ref("")
const registries = ref<Registry[]>([])
const loading = ref(true)
const errorMsg = ref("")
let searchTimer: ReturnType<typeof setTimeout> | undefined

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ registries: Registry[] }>("/dsp", {
      caisse: caisseFilter.value || undefined,
      q: search.value.trim() || undefined,
    })
    registries.value = data.registries
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 250)
})

onMounted(async () => {
  try {
    meta.value = await api.get("/dsp/meta")
  }
  catch { /* defaults already set */ }
  await load()
})

function deadlineClass(r: Registry) {
  if (r.days_to_deadline < 0) return "badge badge-error"
  if (r.days_to_deadline <= 14) return "badge badge-warn"
  return "badge"
}

function deadlineLabel(r: Registry) {
  if (r.days_to_deadline < 0) return t("dsp.en_retard", { n: Math.abs(r.days_to_deadline) })
  if (r.days_to_deadline <= 14) return t("dsp.echeance_proche", { n: r.days_to_deadline })
  return t("dsp.jours_restants", { n: r.days_to_deadline })
}

// ---- Create dialog ---------------------------------------------------------
const showNew = ref(false)
const saving = ref(false)
const formError = ref("")
const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const pickedPatient = ref<PatientRow | null>(null)
const form = ref({ caisse: "CNAS", insured_nin: "", affiliation_no: "", beneficiary_relation: "assure", first_act_date: "", notes: "" })
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
  form.value = { caisse: "CNAS", insured_nin: "", affiliation_no: "", beneficiary_relation: "assure", first_act_date: "", notes: "" }
  formError.value = ""
  showNew.value = true
}

async function create() {
  if (!pickedPatient.value) {
    formError.value = "errors.patient_required"
    return
  }
  saving.value = true
  formError.value = ""
  try {
    await api.post("/dsp", { patient_id: pickedPatient.value.id, ...form.value })
    toast.success("common.save")
    showNew.value = false
    await load()
  }
  catch (e: any) {
    if (e?.messageKey === "errors.patient_not_found") {
      formError.value = e.messageKey
      pickedPatient.value = null
    }
    else {
      formError.value = e?.messageKey ?? "errors.generic"
    }
  }
  finally {
    saving.value = false
  }
}

// ---- Detail view -----------------------------------------------------------
const current = ref<Registry | null>(null)
const acts = ref<Act[]>([])
const deadlineDate = ref("")
const clinic = ref<Clinic | null>(null)
const detailError = ref("")

const totalFees = computed(() => acts.value.reduce((s, a) => s + Number(a.fee), 0))

async function openRegistry(id: number) {
  detailError.value = ""
  loading.value = true
  try {
    const data = await api.get<{
      registry: Registry, acts: Act[], deadline_date: string, days_to_deadline: number, clinic: Clinic
    }>(`/dsp/${id}`)
    current.value = { ...data.registry, days_to_deadline: data.days_to_deadline, deadline_date: data.deadline_date }
    acts.value = data.acts
    deadlineDate.value = data.deadline_date
    clinic.value = data.clinic
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

function printSheet() {
  askPrint()
}

// ---- Acts: add / edit / delete --------------------------------------------
const showActForm = ref(false)
const editActId = ref<number | null>(null)
const actForm = ref({ act_date: "", tooth: "", act_label: "", act_code: "", coefficient: "", fee: "" })
const actSaving = ref(false)
const actError = ref("")

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function openAddAct() {
  editActId.value = null
  actForm.value = { act_date: todayISO(), tooth: "", act_label: "", act_code: "", coefficient: "", fee: "" }
  actError.value = ""
  showActForm.value = true
}

function openEditAct(a: Act) {
  editActId.value = a.id
  actForm.value = {
    act_date: a.act_date,
    tooth: a.tooth === null ? "" : String(a.tooth),
    act_label: a.act_label,
    act_code: a.act_code,
    coefficient: a.coefficient,
    fee: a.fee,
  }
  actError.value = ""
  showActForm.value = true
}

async function saveAct() {
  if (!current.value) return
  actSaving.value = true
  actError.value = ""
  const payload: Record<string, unknown> = {
    act_date: actForm.value.act_date,
    act_label: actForm.value.act_label,
    act_code: actForm.value.act_code,
    coefficient: Number(actForm.value.coefficient) || 0,
    fee: Number(actForm.value.fee) || 0,
    tooth: actForm.value.tooth === "" ? null : Number(actForm.value.tooth),
  }
  try {
    if (editActId.value === null) {
      await api.post(`/dsp/${current.value.id}/acts`, payload)
    }
    else {
      await api.put(`/dsp/${current.value.id}/acts/${editActId.value}`, payload)
    }
    showActForm.value = false
    toast.success("common.save")
    await openRegistry(current.value.id)
  }
  catch (e: any) {
    actError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    actSaving.value = false
  }
}

async function deleteAct(a: Act) {
  if (!current.value) return
  detailError.value = ""
  try {
    await api.del(`/dsp/${current.value.id}/acts/${a.id}`)
    toast.success("common.save")
    await openRegistry(current.value.id)
  }
  catch (e: any) {
    detailError.value = e?.messageKey ?? "errors.generic"
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("dsp.title") }}</h1>
        <p class="page-subtitle">{{ t("dsp.subtitle") }}</p>
      </div>
      <button class="btn btn-primary" @click="openNew">
        {{ t("dsp.nouveau") }}
      </button>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <!-- Detail: printable sheet -->
    <div v-if="current" class="card print-area dsp-card" style="max-width:760px;">
      <AppPrintLetter :settings="clinic" />
      <div class="dsp-meta">
        <div>
          <p class="dsp-patient">
            <strong>{{ current.patient.nom }} {{ current.patient.prenom }}</strong>
            <span class="small muted" style="margin-inline-start:8px;">
              {{ t("dsp.nin") }}: {{ current.insured_nin || "—" }}
            </span>
            <span class="small muted" style="margin-inline-start:8px;">
              {{ t("dsp.affiliation") }}: {{ current.affiliation_no || "—" }}
            </span>
          </p>
          <p class="small" style="margin:0;">
            {{ t("dsp.premiere_consultation") }} : {{ dates.fmtDate(current.first_act_date) }}
            <span class="muted" style="margin-inline-start:8px;">{{ t("dsp.echeance") }} : {{ dates.fmtDate(deadlineDate) }}</span>
          </p>
        </div>
        <div style="text-align:end;">
          <div class="badge" style="margin-bottom:6px;">{{ current.caisse }}</div>
          <div class="no-print" :class="deadlineClass(current)" style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);">
            {{ deadlineLabel(current) }}
          </div>
        </div>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>{{ t("dsp.acte_date") }}</th>
            <th>{{ t("dsp.acte_dent") }}</th>
            <th>{{ t("dsp.acte_libelle") }}</th>
            <th>{{ t("dsp.acte_code") }}</th>
            <th>{{ t("dsp.acte_coefficient") }}</th>
            <th class="num" style="text-align:end;">{{ t("dsp.acte_honoraires") }}</th>
            <th class="no-print" style="width:1%;" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in acts" :key="a.id">
            <td class="small" style="font-variant-numeric:tabular-nums;">{{ dates.fmtDate(a.act_date) }}</td>
            <td>{{ a.tooth ?? "—" }}</td>
            <td>{{ a.act_label }}</td>
            <td class="small muted">{{ a.act_code }}</td>
            <td class="small" style="font-variant-numeric:tabular-nums;">{{ a.coefficient }}</td>
            <td style="text-align:end;font-variant-numeric:tabular-nums;">{{ money.fmt(a.fee) }}</td>
            <td class="no-print" style="width:1%;white-space:nowrap;">
              <button class="btn btn-text btn-sm" @click="openEditAct(a)">{{ t("common.edit") }}</button>
              <button class="btn btn-text btn-sm" style="color:var(--color-danger);" @click="deleteAct(a)">
                {{ t("common.delete") }}
              </button>
            </td>
          </tr>
          <tr v-if="!acts.length">
            <td colspan="7" class="small muted" style="text-align:center;padding:16px;">
              {{ t("dsp.aucun") }}
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="5" style="text-align:end;font-weight:650;">{{ t("dsp.totals") }}</td>
            <td style="text-align:end;font-weight:650;font-variant-numeric:tabular-nums;">
              {{ money.fmt(String(totalFees)) }}
            </td>
            <td style="width:1%;" />
          </tr>
        </tfoot>
      </table>

      <p v-if="current.notes" class="small muted" style="margin-top:12px;">{{ current.notes }}</p>

      <AppPrintFoot
        date=""
        :date-caption="t('documents.date')"
        :signs="[t('dsp.print_sign_praticien')]"
      />

      <div class="dialog-actions no-print" style="margin-top:16px;">
        <button class="btn btn-secondary" @click="current = null">{{ t("common.back") }}</button>
        <button class="btn btn-primary" @click="openAddAct">{{ t("dsp.ajouter_acte") }}</button>
        <button class="btn btn-primary" @click="printSheet">{{ t("dsp.imprimer") }}</button>
      </div>
    </div>

    <!-- List -->
    <template v-else>
      <div class="toolbar" style="margin-bottom:12px;gap:12px;">
        <select v-model="caisseFilter" class="select" style="width:auto;height:38px;" @change="load">
          <option value="">{{ t("dsp.caisse") }} — {{ t("common.none") }}</option>
          <option v-for="c in meta.caisses" :key="c" :value="c">{{ c }}</option>
        </select>
        <input
          v-model="search"
          class="input"
          style="max-width:320px;"
          :placeholder="t('dsp.recherche')"
          :aria-label="t('common.search')"
        >
      </div>

      <div v-if="loading" class="card" style="padding:16px;" aria-hidden="true">
        <div v-for="i in 5" :key="i" class="skeleton skeleton-line" :class="i % 2 ? 'w-60' : 'w-40'" />
      </div>
      <div v-else-if="!registries.length" class="card empty-state">
        <span class="empty-icon">◈</span>
        {{ t("dsp.aucun") }}
        <div class="empty-hint">{{ t("dsp.nouveau") }}</div>
      </div>
      <div v-else class="card" style="padding:0;">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t("dsp.patient") }}</th>
              <th>{{ t("dsp.caisse") }}</th>
              <th>{{ t("dsp.premiere_consultation") }}</th>
              <th>{{ t("dsp.echeance") }}</th>
              <th>{{ t("dsp.actes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in registries" :key="r.id" class="row-link" @click="openRegistry(r.id)">
              <td>
                <strong>{{ r.patient.nom }} {{ r.patient.prenom }}</strong>
                <div class="small muted">{{ r.patient.telephone }}</div>
              </td>
              <td><span class="badge">{{ r.caisse }}</span></td>
              <td class="small muted" style="font-variant-numeric:tabular-nums;">{{ dates.fmtDate(r.first_act_date) }}</td>
              <td>
                <span :class="deadlineClass(r)" style="padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);display:inline-block;">
                  {{ deadlineLabel(r) }}
                </span>
              </td>
              <td class="small muted">{{ r.act_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Create registry dialog -->
    <AppDialog :open="showNew" :title="t('dsp.nouveau')" @close="showNew = false">
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
          <label for="dsp-caisse">{{ t("dsp.caisse") }}</label>
          <select id="dsp-caisse" v-model="form.caisse" class="select">
            <option v-for="c in meta.caisses" :key="c" :value="c">{{ c }}</option>
          </select>
          <p class="small muted" style="margin-top:4px;">{{ t("dsp.caisse_hint") }}</p>
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="dsp-nin">{{ t("dsp.nin") }} ({{ t("common.optional") }})</label>
          <input id="dsp-nin" v-model="form.insured_nin" class="input" maxlength="18">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="dsp-affil">{{ t("dsp.affiliation") }} ({{ t("common.optional") }})</label>
          <input id="dsp-affil" v-model="form.affiliation_no" class="input" maxlength="40">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="dsp-relation">{{ t("dsp.lien") }}</label>
          <select id="dsp-relation" v-model="form.beneficiary_relation" class="select">
            <option value="assure">{{ t("dsp.lien_assure") }}</option>
            <option value="conjoint">{{ t("dsp.lien_conjoint") }}</option>
            <option value="enfant">{{ t("dsp.lien_enfant") }}</option>
            <option value="autre">{{ t("dsp.lien_autre") }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="dsp-first">{{ t("dsp.premiere_consultation") }}</label>
          <input id="dsp-first" v-model="form.first_act_date" type="date" class="input">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="dsp-notes">{{ t("dsp.notes_lbl") }}</label>
          <textarea id="dsp-notes" v-model="form.notes" class="textarea" rows="2" />
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

    <!-- Add/edit act dialog -->
    <AppDialog :open="showActForm" :title="editActId === null ? t('dsp.ajouter_acte') : t('common.edit')" @close="showActForm = false">
      <div class="field" style="margin-bottom:12px;">
        <label for="act-date">{{ t("dsp.acte_date") }}</label>
        <input id="act-date" v-model="actForm.act_date" type="date" class="input">
      </div>
      <div style="display:flex;gap:12px;margin-bottom:12px;">
        <div class="field" style="flex:1;">
          <label for="act-dent">{{ t("dsp.acte_dent") }}</label>
          <input id="act-dent" v-model="actForm.tooth" class="input" inputmode="numeric" :placeholder="t('common.optional')">
        </div>
        <div class="field" style="flex:1;">
          <label for="act-code">{{ t("dsp.acte_code") }}</label>
          <input id="act-code" v-model="actForm.act_code" class="input" :placeholder="t('common.optional')">
        </div>
      </div>
      <div class="field" style="margin-bottom:12px;">
        <label for="act-label">{{ t("dsp.acte_libelle") }}</label>
        <input id="act-label" v-model="actForm.act_label" class="input">
      </div>
      <div style="display:flex;gap:12px;margin-bottom:16px;">
        <div class="field" style="flex:1;">
          <label for="act-coef">{{ t("dsp.acte_coefficient") }}</label>
          <input id="act-coef" v-model="actForm.coefficient" class="input" inputmode="decimal">
        </div>
        <div class="field" style="flex:1;">
          <label for="act-fee">{{ t("dsp.acte_honoraires") }} ({{ t("common.currency_da") }})</label>
          <input id="act-fee" v-model="actForm.fee" class="input" inputmode="decimal">
        </div>
      </div>
      <div v-if="actError" class="alert alert-error">{{ t(actError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showActForm = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="actSaving" @click="saveAct">{{ t("common.save") }}</button>
      </div>
    </AppDialog>
  </div>
</template>

<style scoped>
.dsp-meta {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-top: 12px;
}

.dsp-patient {
  margin: 0 0 4px;
}

@media print {
  .dsp-card {
    border: none;
    box-shadow: none;
    border-radius: 0;
    padding: 0;
    background: #fff;
  }
}
</style>
