<script setup lang="ts">
/**
 * Documents (DESIGN.md §12): a small print desk.
 * Flow: pick a patient → list their documents → preview/print, or create
 * ordonnance / certificat / attestation for the selected patient.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const toast = useToast()

interface DocRow { id: number, patient_id: number, doc_type: string, title: string, created_at: string }
interface DocFull extends DocRow { content: any }
interface PatientRow { id: number, nom: string, prenom: string, telephone: string }
interface PatientFull { id: number, nom: string, prenom: string, telephone: string, code: string, age_years?: number | null, date_naissance?: string }
interface ClinicSettings {
  clinic_name: string, doctor_name: string, address: string, phone: string,
  header_note: string, footer_note: string,
}

const patient = ref<PatientFull | null>(null)
const patientQuery = ref("")
const patientResults = ref<PatientRow[]>([])
const docs = ref<DocRow[]>([])
const loading = ref(false)
const errorMsg = ref("")
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
  patientQuery.value = ""
  patientResults.value = []
  loading.value = true
  errorMsg.value = ""
  try {
    const [full, list] = await Promise.all([
      api.get<{ patient: PatientFull }>(`/patients/${p.id}`),
      api.get<{ documents: DocRow[] }>(`/documents/patients/${p.id}`),
    ])
    patient.value = full.patient
    docs.value = list.documents
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

async function reloadDocs() {
  if (!patient.value) return
  const list = await api.get<{ documents: DocRow[] }>(`/documents/patients/${patient.value.id}`)
  docs.value = list.documents
}

// ---- Create dialog ---------------------------------------------------------
const showNew = ref(false)
const form = ref({ doc_type: "ordonnance", lines: ["", "", ""], note: "", text: "", duration_days: 0 })
const saving = ref(false)
const formError = ref("")

function openNew() {
  if (!patient.value) {
    errorMsg.value = "errors.patient_required"
    return
  }
  form.value = { doc_type: "ordonnance", lines: ["", "", ""], note: "", text: "", duration_days: 0 }
  formError.value = ""
  showNew.value = true
}

async function create() {
  if (!patient.value) return
  saving.value = true
  formError.value = ""
  const docType = form.value.doc_type
  let content: Record<string, unknown>
  if (docType === "ordonnance") {
    content = { lines: form.value.lines.filter(l => l.trim()), note: form.value.note }
  }
  else if (docType === "certificat") {
    content = { text: form.value.text, duration_days: Number(form.value.duration_days) || 0 }
  }
  else {
    content = { text: form.value.text }
  }
  try {
    const created = await api.post<{ document: DocFull }>("/documents", {
      patient_id: patient.value.id,
      doc_type: docType,
      title: t(`documents.${docType}`),
      content,
    })
    showNew.value = false
    toast.success("documents.created")
    await reloadDocs()
    await openDoc(created.document.id)
  }
  catch (e: any) {
    formError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

// ---- Preview / print -------------------------------------------------------
const current = ref<DocFull | null>(null)
const settings = ref<ClinicSettings | null>(null)
const editing = ref(false)
const editForm = ref({ lines: [] as string[], note: "", age: "", sexe: "" as "" | "M" | "F", text: "", duration_days: 0 })
const savingEdit = ref(false)

async function openDoc(id: number) {
  errorMsg.value = ""
  editing.value = false
  try {
    const data = await api.get<{ document: DocFull, clinic: ClinicSettings }>(`/documents/${id}`)
    current.value = data.document
    settings.value = data.clinic
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
}

function ageYears(birth?: string): number | null {
  if (!birth) return null
  const b = new Date(birth)
  if (Number.isNaN(b.getTime())) return null
  const now = new Date()
  let age = now.getFullYear() - b.getFullYear()
  const m = now.getMonth() - b.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--
  return age >= 0 ? age : null
}

function startEdit() {
  if (!current.value) return
  const c = current.value.content || {}
  const autoAge = ageYears(patient.value?.date_naissance)
  editForm.value = {
    lines: [...(c.lines ?? [""])],
    note: c.note ?? "",
    age: c.age || (autoAge !== null ? String(autoAge) : ""),
    sexe: (c.sexe === "M" || c.sexe === "F") ? c.sexe : "",
    text: c.text ?? "",
    duration_days: c.duration_days ?? 0,
  }
  editing.value = true
}

async function saveEdit() {
  if (!current.value) return
  savingEdit.value = true
  errorMsg.value = ""
  try {
    const content: Record<string, unknown> = { ...(current.value.content || {}) }
    if (current.value.doc_type === "ordonnance") {
      content.lines = editForm.value.lines.filter(l => l.trim())
      content.note = editForm.value.note
      content.age = editForm.value.age
      content.sexe = editForm.value.sexe
    }
    else {
      content.text = editForm.value.text
      if (current.value.doc_type === "certificat") content.duration_days = Number(editForm.value.duration_days) || 0
    }
    const data = await api.put<{ document: DocFull }>(`/documents/${current.value.id}`, { content })
    current.value = data.document
    editing.value = false
    toast.success("documents.saved")
    await reloadDocs()
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    savingEdit.value = false
  }
}

function printDoc() {
  window.print()
}

const route = useRoute()

onMounted(async () => {
  const openId = route.query.open
  const patientId = route.query.patient
  if (typeof patientId === "string" && patientId) {
    try {
      const full = await api.get<{ patient: PatientFull }>(`/patients/${Number(patientId)}`)
      patient.value = full.patient
      await reloadDocs()
    }
    catch {
      /* ignore: user picks a patient manually */
    }
  }
  if (typeof openId === "string" && openId) await openDoc(Number(openId))
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("documents.title") }}</h1>
        <p v-if="patient" class="page-subtitle">
          {{ patient.nom }} {{ patient.prenom }} · {{ patient.telephone }} · {{ patient.code }}
        </p>
      </div>
      <div style="display:flex;gap:12px;align-items:center;">
        <div v-if="!patient" style="width:360px;position:relative;">
          <input
            v-model="patientQuery"
            class="input"
            :placeholder="t('common.search_placeholder')"
            :aria-label="t('common.search')"
          >
          <div v-if="patientResults.length" class="card" style="padding:0;margin-top:4px;position:absolute;z-index:30;width:100%;">
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
        <button v-else class="btn btn-secondary btn-sm" @click="patient = null; docs = []; current = null">
          {{ t("common.back") }}
        </button>
        <button v-if="patient" class="btn btn-primary" @click="openNew">
          {{ t("documents.nouveau") }}
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div v-if="!patient" class="card empty-state">
      <span class="empty-icon">▤</span>
      {{ t("common.search_placeholder") }}
    </div>

    <template v-else>
      <!-- Preview / print: HKN Dental Care ordonnance/template -->
      <div v-if="current" class="card print-area" style="max-width:720px;">
        <template v-if="current.doc_type === 'ordonnance'">
          <!-- Ordonnance uses the dedicated HKN sheet -->
          <div class="ord-sheet">
            <div class="ord-header">
              <div class="ord-brand">
                <img src="/ordonnance-mark.svg" alt="" class="ord-logo" aria-hidden="true">
                <div class="ord-brandtext">
                  <span class="ord-brand-hkn">HKN</span>
                  <span class="ord-brand-sub">Dental Care</span>
                </div>
              </div>
              <div class="ord-doctor">
                <div class="ord-doctor-name">{{ settings?.doctor_name }}</div>
                <div class="ord-doctor-sub">{{ settings?.header_note }}</div>
              </div>
            </div>
            <div class="ord-clinic-info">
              <div v-if="settings?.address">📍 {{ settings?.address }}</div>
              <div v-if="settings?.phone">📞 {{ settings?.phone }}</div>
              <div>{{ settings?.clinic_name }}</div>
            </div>
            <hr class="ord-rule">

            <div class="ord-patient">
              <template v-if="editing">
                <div class="field" style="margin-bottom:6px;">
                  <label for="ord-name">{{ t("documents.nom_prenom") }}</label>
                  <input id="ord-name" class="input" :value="patient?.nom + ' ' + patient?.prenom" disabled>
                </div>
              </template>
              <p v-else class="ord-line-label">{{ t("documents.nom_prenom") }} : <strong>{{ patient?.nom }} {{ patient?.prenom }}</strong></p>
              <template v-if="editing">
                <div class="field" style="margin-bottom:6px;">
                  <label for="ord-age">{{ t("documents.age") }}</label>
                  <input id="ord-age" v-model="editForm.age" class="input" style="max-width:120px;">
                </div>
                <div class="field" style="margin-bottom:6px;">
                  <label>{{ t("documents.sexe") }}</label>
                  <div style="display:flex;gap:8px;align-items:center;">
                    <button
                      type="button"
                      class="ord-sexbtn"
                      :class="{ 'ord-sexbtn-on': editForm.sexe === 'M' }"
                      @click="editForm.sexe = editForm.sexe === 'M' ? '' : 'M'"
                    >M</button>
                    <button
                      type="button"
                      class="ord-sexbtn"
                      :class="{ 'ord-sexbtn-on': editForm.sexe === 'F' }"
                      @click="editForm.sexe = editForm.sexe === 'F' ? '' : 'F'"
                    >F</button>
                  </div>
                </div>

                <div v-for="(_, idx) in editForm.lines" :key="idx" class="field" style="margin-bottom:6px;">
                  <label :for="`ord-line-${idx}`">{{ t("documents.ligne") }} {{ idx + 1 }}</label>
                  <input :id="`ord-line-${idx}`" v-model="editForm.lines[idx]" class="input">
                </div>
                <button class="btn btn-text btn-sm" @click="editForm.lines.push('')">{{ t("documents.ajouter_ligne") }}</button>
              </template>
              <template v-else>
                <p class="ord-line-label">{{ t("documents.age") }} : {{ current.content?.age || "—" }}</p>
                <p class="ord-line-label">
                  {{ t("documents.sexe") }} :
                  <span class="ord-sexbox" :class="{ 'ord-sexbox-on': current.content?.sexe === 'M' }">M</span>
                  <span class="ord-sexbox" style="margin-inline-start:6px;" :class="{ 'ord-sexbox-on': current.content?.sexe === 'F' }">F</span>
                </p>
              </template>
            </div>

            <div class="ord-watermark" aria-hidden="true">
              <img src="/ordonnance-watermark.svg" alt="" class="ord-watermark-img">
            </div>

            <div class="ord-content">
              <ol v-if="!editing" style="margin:0;padding-inline-start:20px;">
                <li v-for="(line, idx) in current.content?.lines ?? []" :key="idx" style="margin-bottom:6px;">
                  {{ line }}
                </li>
              </ol>
              <p v-if="!editing && current.content?.note" class="small muted" style="margin-top:12px;">{{ current.content.note }}</p>
            </div>

            <div class="ord-footer">
              <div class="ord-footer-slot">
                <hr class="ord-signrule">
                <div class="ord-caption">{{ t("documents.date") }}</div>
              </div>
              <div class="ord-footer-slot" style="text-align:end;">
                <hr class="ord-signrule">
                <div class="ord-caption">{{ t("documents.signature") }}</div>
              </div>
            </div>
          </div>

          <div class="dialog-actions no-print" style="margin-top:16px;">
            <button class="btn btn-secondary" @click="current = null">{{ t("common.close") }}</button>
            <button v-if="!editing" class="btn btn-secondary" @click="startEdit">{{ t("documents.editer") }}</button>
            <button v-if="editing" class="btn btn-secondary" :disabled="savingEdit" @click="saveEdit">{{ t("common.save") }}</button>
            <button class="btn btn-primary" @click="printDoc">{{ t("common.print") }}</button>
          </div>
        </template>

        <template v-else>
          <!-- Certificat / attestation keep the simple sheet -->
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
            <div>
              <strong style="font-size:16px;">{{ settings?.clinic_name || "Clinique" }}</strong>
              <div class="small muted">{{ settings?.doctor_name }}</div>
              <div class="small muted">{{ settings?.address }}</div>
              <div class="small muted" style="font-variant-numeric:tabular-nums;">{{ settings?.phone }}</div>
            </div>
            <div class="small muted" style="text-align:end;">
              {{ dates.fmtDate(current.created_at) }}
            </div>
          </div>
          <hr style="border:none;border-top:1px solid var(--color-border);margin:16px 0;">
          <p v-if="settings?.header_note" class="small muted" style="margin-bottom:12px;">{{ settings.header_note }}</p>

          <p style="margin-bottom:12px;">
            <strong>{{ patient?.nom }} {{ patient?.prenom }}</strong>
            <span class="small muted" style="margin-inline-start:8px;">{{ patient?.code }}</span>
          </p>

          <h2 class="section-title" style="margin-bottom:12px;">{{ t(`documents.${current.doc_type}`) }}</h2>

          <template v-if="editing">
            <div v-if="current.doc_type === 'certificat'" class="field" style="margin-bottom:12px;">
              <label for="doc-duration">{{ t("documents.duree_jours") }}</label>
              <input id="doc-duration" v-model="editForm.duration_days" type="number" min="0" max="90" class="input">
            </div>
            <div class="field" style="margin-bottom:16px;">
              <label for="doc-text">{{ t("documents.texte") }}</label>
              <textarea id="doc-text" v-model="editForm.text" class="textarea" />
            </div>
          </template>
          <template v-else>
            <p style="white-space:pre-wrap;">{{ current.content?.text }}</p>
            <p v-if="current.doc_type === 'certificat' && current.content?.duration_days" class="small" style="margin-top:8px;">
              {{ t("documents.duree_jours") }} : {{ current.content.duration_days }}
            </p>
          </template>

          <p v-if="settings?.footer_note" class="small muted" style="margin-top:24px;">{{ settings.footer_note }}</p>

          <div class="dialog-actions no-print" style="margin-top:24px;">
            <button class="btn btn-secondary" @click="current = null">{{ t("common.close") }}</button>
            <button v-if="!editing" class="btn btn-secondary" @click="startEdit">{{ t("documents.editer") }}</button>
            <button v-if="editing" class="btn btn-secondary" :disabled="savingEdit" @click="saveEdit">{{ t("common.save") }}</button>
            <button class="btn btn-primary" @click="printDoc">{{ t("common.print") }}</button>
          </div>
        </template>
      </div>

      <!-- List -->
      <div v-else class="card" style="padding:0;">
        <div v-if="loading" style="padding:8px 16px 16px;" aria-hidden="true">
          <div v-for="i in 4" :key="i" class="skeleton skeleton-row" />
        </div>
        <div v-else-if="!docs.length" class="empty-state">
          <span class="empty-icon">▤</span>
          {{ t("documents.aucun") }}
          <div class="empty-hint">{{ t("documents.nouveau") }}</div>
        </div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>{{ t("documents.type") }}</th>
              <th>{{ t("appointment.date") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id" class="row-link" @click="openDoc(d.id)">
              <td style="font-weight:600;">{{ t(`documents.${d.doc_type}`) }}</td>
              <td class="small muted">{{ dates.fmtDate(d.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Create document dialog -->
    <AppDialog :open="showNew" :title="t('documents.nouveau')" @close="showNew = false">
        <p class="small muted" style="margin-bottom:12px;">
          {{ patient?.nom }} {{ patient?.prenom }}
        </p>

        <div class="field" style="margin-bottom:12px;">
          <label for="doc-type">{{ t("documents.type") }}</label>
          <select id="doc-type" v-model="form.doc_type" class="select">
            <option value="ordonnance">{{ t("documents.ordonnance") }}</option>
            <option value="certificat">{{ t("documents.certificat") }}</option>
            <option value="attestation">{{ t("documents.attestation") }}</option>
          </select>
        </div>

        <template v-if="form.doc_type === 'ordonnance'">
          <div v-for="(_, idx) in form.lines" :key="idx" class="field" style="margin-bottom:8px;">
            <label :for="`doc-line-${idx}`">{{ t("documents.ligne") }} {{ idx + 1 }}</label>
            <input :id="`doc-line-${idx}`" v-model="form.lines[idx]" class="input">
          </div>
          <button class="btn btn-text btn-sm" @click="form.lines.push('')">
            {{ t("documents.ajouter_ligne") }}
          </button>
          <div class="field" style="margin:12px 0 16px;">
            <label for="doc-note">{{ t("common.notes") }}</label>
            <input id="doc-note" v-model="form.note" class="input">
          </div>
        </template>

        <template v-else>
          <div v-if="form.doc_type === 'certificat'" class="field" style="margin-bottom:12px;">
            <label for="doc-duration">{{ t("documents.duree_jours") }}</label>
            <input id="doc-duration" v-model.number="form.duration_days" type="number" min="0" max="90" class="input">
          </div>
          <div class="field" style="margin-bottom:16px;">
            <label for="doc-text">{{ t("documents.texte") }}</label>
            <textarea id="doc-text" v-model="form.text" class="textarea" />
          </div>
        </template>

        <div v-if="formError" class="alert alert-error">{{ t(formError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showNew = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="create">{{ t("common.save") }}</button>
        </div>
    </AppDialog>
  </div>
</template>

<style scoped>
/* ---- HKN Dental Care ordonnance sheet ---------------------------------- */
.ord-sheet {
  position: relative;
  padding: 24px 28px;
  color: #0040dc;
  background: #fff;
  font-family: inherit;
}

.ord-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.ord-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ord-logo {
  width: 54px;
  height: 48px;
  display: block;
  color: #0040dc;
}

.ord-brandtext {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: 0.4px;
  color: #0040dc;
}

.ord-brand-hkn {
  font-size: 17px;
}

.ord-brand-sub {
  font-size: 11.5px;
  font-weight: 700;
}

.ord-doctor {
  text-align: start;
}

.ord-doctor-name {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.2px;
}

.ord-doctor-sub {
  margin-top: 2px;
  font-size: 13px;
}

.ord-clinic-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  margin-top: 8px;
  min-height: 52px;
}

.ord-logo-xs {
  position: absolute;
  inset-inline-start: 0;
  top: 100px;
  width: 30px;
  opacity: 0.9;
}

.ord-rule {
  border: none;
  border-top: 1px solid #0040dc;
  margin: 12px 0 20px;
}

.ord-patient {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ord-line-label {
  font-size: 13.5px;
  color: #0040dc;
}

.ord-sexbox,
.ord-sexbtn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 20px;
  border: 0.7px solid #0040dc;
  border-radius: 2px;
  font-size: 11px;
  color: #0040dc;
  background: transparent;
}

.ord-sexbtn {
  cursor: pointer;
}

.ord-sexbtn-on,
.ord-sexbox-on {
  background: #0040dc;
  color: #fff;
}

.ord-watermark {
  position: absolute;
  inset-inline: 0;
  top: 46%;
  transform: translateY(-28%);
  display: flex;
  justify-content: center;
  pointer-events: none;
  z-index: 1;
}

.ord-watermark-img {
  width: 340px;
  opacity: 0.06;
  mix-blend-mode: multiply;
}

.ord-content {
  position: relative;
  z-index: 2;
  margin-top: 42px;
  min-height: 200px;
  font-size: 13.5px;
  color: #0b1a4a;
}

.ord-footer {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 60px;
}

.ord-footer-slot {
  width: 160px;
}

.ord-signrule {
  width: 70px;
  border: none;
  border-top: 0.7px solid #0040dc;
  margin: 0 0 6px;
}

.ord-footer-slot:nth-child(2) .ord-signrule {
  margin-inline: auto;
}

.ord-caption {
  font-size: 12px;
  color: #0040dc;
}

@media print {
  .no-print,
  aside,
  header,
  .toolbar,
  .alert {
    display: none !important;
  }

  .print-area {
    max-width: none !important;
    border: none !important;
    box-shadow: none !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .ord-sheet {
    padding: 0;
  }
}
</style>