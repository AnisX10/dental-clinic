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
    // Deep links (/documents?open=N) may arrive without a patient selected;
    // the preview needs the patient for the header, so load it from the doc.
    if (!patient.value || patient.value.id !== data.document.patient_id) {
      const full = await api.get<{ patient: PatientFull }>(`/patients/${data.document.patient_id}`)
      patient.value = full.patient
      await reloadDocs()
    }
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
  askPrint()
}

// ---- Continued-page running head ------------------------------------------
// Chromium print has no per-page margin boxes, so a repeated header is done
// with the reliable table trick: for long ordonnances the sheet becomes a
// table whose first section is a table-header-group, which Chrome repeats on
// every printed page. Short docs keep the flex layout (footer bottom-anchored).
const sheetEl = ref<HTMLElement | null>(null)
const isPaged = ref(false)

async function measurePaged() {
  await nextTick()
  try { await document.fonts.ready } catch { /* ignore */ }
  const sheet = sheetEl.value
  if (!sheet || !current.value || current.value.doc_type !== "ordonnance" || editing.value) {
    isPaged.value = false
    return
  }
  // Screen sheet has 26px top/bottom padding that print drops; the print page
  // box offers ~1032px (297mm - 2 x 12mm @96dpi). Only switch modes when the
  // letterhead + content clearly exceeds one page.
  isPaged.value = sheet.scrollHeight - 52 > 1000
}

watch([current, editing], () => { void measurePaged() })

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
      <!-- Preview / print: shared HKN letterhead for every document type -->
      <div v-if="current" class="card print-area" style="max-width:720px;">
        <div ref="sheetEl" class="ord-sheet" :class="{ 'ord-ispaged': isPaged }">
          <thead class="ord-runhead" aria-hidden="true">
            <tr>
              <td colspan="2" class="ord-rh-cell">
                <div class="ord-rh-in">
                  <span>
                    <strong>{{ t(`documents.${current.doc_type}`) }}</strong>
                    · {{ patient?.nom }} {{ patient?.prenom }} ({{ patient?.code }})
                  </span>
                  <span v-if="settings?.clinic_name" class="ord-rh-end">{{ settings.clinic_name }}</span>
                </div>
              </td>
            </tr>
          </thead>
          <tbody class="ord-headbody">
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell">
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
                    <div v-if="settings?.header_note" class="ord-doctor-sub">{{ settings?.header_note }}</div>
                  </div>
                </div>
              </td>
            </tr>
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell">
                <div class="ord-clinic-info">
                  <div v-if="settings?.address" class="ord-contact">
                    <svg class="ord-icon" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 21.2c4.2-4.3 7-7.6 7-11a7 7 0 1 0-14 0c0 3.4 2.8 6.7 7 11Z" />
                      <circle cx="12" cy="10" r="2.6" />
                    </svg>
                    <span>{{ settings.address }}</span>
                  </div>
                  <div v-if="settings?.phone" class="ord-contact">
                    <svg class="ord-icon" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7 12.8 12.8 0 0 0 .7 2.8 2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4 12.8 12.8 0 0 0 2.8.7 2 2 0 0 1 1.7 2Z" />
                    </svg>
                    <span>{{ settings.phone }}</span>
                  </div>
                  <div v-if="settings?.clinic_name" class="ord-clinic-name">{{ settings.clinic_name }}</div>
                </div>
              </td>
            </tr>
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell"><hr class="ord-rule"></td>
            </tr>
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell">
                <div class="ord-patient">
                  <p class="ord-line-label">
                    {{ t("documents.nom_prenom") }} : <strong>{{ patient?.nom }} {{ patient?.prenom }}</strong>
                    <span class="ord-code">{{ patient?.code }}</span>
                  </p>
                  <template v-if="current.doc_type === 'ordonnance'">
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
                    </template>
                    <template v-else>
                      <p class="ord-line-label">{{ t("documents.age") }} : {{ current.content?.age || "—" }}</p>
                      <p class="ord-line-label">
                        {{ t("documents.sexe") }} :
                        <span class="ord-sexbox" :class="{ 'ord-sexbox-on': current.content?.sexe === 'M' }">M</span>
                        <span class="ord-sexbox" style="margin-inline-start:6px;" :class="{ 'ord-sexbox-on': current.content?.sexe === 'F' }">F</span>
                      </p>
                    </template>
                  </template>
                </div>
              </td>
            </tr>
            <tr class="ord-spacer">
              <td colspan="2"></td>
            </tr>
          </tbody>

          <div class="ord-content">
            <div class="ord-watermark" aria-hidden="true">
              <img src="/ordonnance-watermark.svg" alt="" class="ord-watermark-img">
            </div>

            <template v-if="current.doc_type === 'ordonnance'">
              <template v-if="editing">
                <div v-for="(_, idx) in editForm.lines" :key="idx" class="field" style="margin-bottom:6px;">
                  <label :for="`ord-line-${idx}`">{{ t("documents.ligne") }} {{ idx + 1 }}</label>
                  <input :id="`ord-line-${idx}`" v-model="editForm.lines[idx]" class="input">
                </div>
                <button class="btn btn-text btn-sm" @click="editForm.lines.push('')">{{ t("documents.ajouter_ligne") }}</button>
                <div class="field" style="margin-top:12px;">
                  <label for="ord-note">{{ t("common.notes") }}</label>
                  <input id="ord-note" v-model="editForm.note" class="input">
                </div>
              </template>
              <template v-else>
                <ol class="ord-list">
                  <li v-for="(line, idx) in current.content?.lines ?? []" :key="idx">{{ line }}</li>
                </ol>
              </template>
            </template>

            <template v-else>
              <h2 class="ord-title">{{ t(`documents.${current.doc_type}`) }}</h2>
              <template v-if="editing">
                <div v-if="current.doc_type === 'certificat'" class="field" style="margin-bottom:12px;">
                  <label for="doc-duration">{{ t("documents.duree_jours") }}</label>
                  <input id="doc-duration" v-model="editForm.duration_days" type="number" min="0" max="90" class="input">
                </div>
                <div class="field" style="margin-bottom:8px;">
                  <label for="doc-text">{{ t("documents.texte") }}</label>
                  <textarea id="doc-text" v-model="editForm.text" class="textarea" />
                </div>
              </template>
              <template v-else>
                <p class="ord-text">{{ current.content?.text }}</p>
                <p v-if="current.doc_type === 'certificat' && current.content?.duration_days" class="ord-duration">
                  {{ t("documents.duree_jours") }} : {{ current.content.duration_days }}
                </p>
              </template>
              <p v-if="settings?.footer_note" class="ord-footer-note">{{ settings.footer_note }}</p>
            </template>
          </div>

          <tbody class="ord-footbody">
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell">
                <p v-if="current.doc_type === 'ordonnance' && current.content?.note" class="ord-note">
                  {{ current.content.note }}
                </p>
              </td>
            </tr>
            <tr class="ord-hrow">
              <td colspan="2" class="ord-hcell">
                <div class="ord-footer">
                  <div class="ord-footer-slot">
                    <div class="ord-date-value">{{ dates.fmtDate(current.created_at) }}</div>
                    <hr class="ord-signrule">
                    <div class="ord-caption">{{ t("documents.date") }}</div>
                  </div>
                  <div class="ord-footer-slot ord-footer-end">
                    <hr class="ord-signrule">
                    <div class="ord-caption">{{ t("documents.signature") }}</div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </div>

        <div class="dialog-actions no-print" style="margin-top:16px;">
          <button class="btn btn-secondary" @click="current = null">{{ t("common.close") }}</button>
          <button v-if="!editing" class="btn btn-secondary" @click="startEdit">{{ t("documents.editer") }}</button>
          <button v-if="editing" class="btn btn-secondary" :disabled="savingEdit" @click="saveEdit">{{ t("common.save") }}</button>
          <button class="btn btn-primary" @click="printDoc">{{ t("common.print") }}</button>
        </div>
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
/* ---- HKN Dental Care document sheet ------------------------------------ */
.ord-sheet {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 620px;
  padding: 26px 30px;
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
  gap: 12px;
}

.ord-logo {
  width: 64px;
  height: 56px;
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
  font-size: 18px;
}

.ord-brand-sub {
  font-size: 12px;
  font-weight: 700;
}

.ord-doctor {
  text-align: start;
  padding-top: 2px;
}

.ord-doctor-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.2px;
}

.ord-doctor-sub {
  margin-top: 4px;
  font-size: 13px;
}

.ord-clinic-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  margin-top: 10px;
}

.ord-contact {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ord-icon {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.ord-clinic-name {
  margin-top: 2px;
}

.ord-rule {
  border: none;
  border-top: 1px solid #0040dc;
  margin: 14px 0 20px;
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

.ord-code {
  margin-inline-start: 10px;
  font-size: 11.5px;
  color: #0040dc;
  opacity: 0.7;
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

.ord-content {
  position: relative;
  z-index: 2;
  flex: 1;
  margin-top: 30px;
  min-height: 240px;
  font-size: 13.5px;
  color: #0b1a4a;
}

.ord-content > *:not(.ord-watermark) {
  position: relative;
  z-index: 1;
}

.ord-watermark {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 0;
}

.ord-watermark-img {
  width: 340px;
  max-width: 72%;
  opacity: 0.07;
}

.ord-list {
  margin: 0;
  padding-inline-start: 20px;
}

.ord-list li {
  margin-bottom: 7px;
  padding-inline-start: 2px;
  line-height: 1.5;
}

.ord-note {
  margin-top: 14px;
  font-size: 12.5px;
  color: #475569;
}

.ord-title {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: #0040dc;
}

.ord-text {
  white-space: pre-wrap;
  line-height: 1.65;
}

.ord-duration {
  margin-top: 12px;
  font-size: 12.5px;
  color: #0040dc;
}

.ord-footer-note {
  margin-top: 22px;
  font-size: 11.5px;
  color: #64748b;
}

.ord-footer {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 48px;
}

.ord-footer-slot {
  width: 170px;
}

.ord-footer-end {
  text-align: end;
}

.ord-date-value {
  margin-bottom: 6px;
  font-size: 12px;
}

.ord-signrule {
  width: 80px;
  border: none;
  border-top: 0.7px solid #0040dc;
  margin: 0 0 6px;
}

.ord-footer-end .ord-signrule {
  margin-inline-start: auto;
}

.ord-caption {
  font-size: 12px;
  letter-spacing: 0.3px;
  color: #0040dc;
}

/* ---- Continued-page running head (print only) ---------------------------- */
/* The letterhead is marked up with real thead/tbody/tr/td so Chromium print
   can repeat the running head and span sections correctly; neutralize the
   table semantics everywhere except the multi-page print mode. */
.ord-sheet > .ord-runhead {
  display: none;
}

.ord-sheet :is(thead, tbody, tr, td) {
  display: block;
}

.ord-sheet td {
  padding: 0;
}

.ord-rh-in {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 11px;
  letter-spacing: 0.3px;
  color: #0040dc;
}

.ord-rh-end {
  white-space: nowrap;
  opacity: 0.8;
}

@media print {
  .ord-sheet.ord-ispaged {
    display: table;
    width: 100%;
    min-height: 0;
    border-collapse: separate;
    border-spacing: 0 8px;
  }

  .ord-sheet.ord-ispaged thead {
    display: table-header-group;
  }

  .ord-sheet.ord-ispaged tbody {
    display: table-row-group;
  }

  .ord-sheet.ord-ispaged tr {
    display: table-row;
  }

  .ord-sheet.ord-ispaged td {
    display: table-cell;
    vertical-align: baseline;
  }

  .ord-sheet.ord-ispaged .ord-rh-cell {
    padding-bottom: 5px;
    border-bottom: 0.7px solid rgba(0, 64, 220, 0.45);
    vertical-align: bottom;
  }

  .ord-sheet.ord-ispaged .ord-spacer > td {
    height: 22px;
  }

  /* Long ordonnance body: atomic list rows that fragment between items */
  .ord-sheet.ord-ispaged .ord-content {
    display: table-row-group;
    min-height: 0;
    margin: 0;
  }

  .ord-sheet.ord-ispaged .ord-content > .ord-watermark {
    position: fixed;
    inset: auto;
    top: 36%;
    left: 0;
    right: 0;
    width: 340px;
    margin: 0 auto;
    z-index: -1;
  }

  .ord-sheet.ord-ispaged .ord-watermark-img {
    max-width: none;
  }

  .ord-sheet.ord-ispaged .ord-list {
    display: table-row-group;
    margin: 0;
    padding-inline-start: 0;
    counter-reset: ord-item;
  }

  .ord-sheet.ord-ispaged .ord-list > li {
    display: table-row;
    list-style: none;
    margin-bottom: 0;
    padding-inline-start: 0;
  }

  .ord-sheet.ord-ispaged .ord-list > li::before {
    content: counter(ord-item) ".";
    counter-increment: ord-item;
    display: table-cell;
    padding-inline-end: 8px;
    vertical-align: baseline;
  }
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
    min-height: 265mm;
    padding: 0;
  }

  .ord-list li,
  .ord-note,
  .ord-title,
  .ord-patient,
  .ord-footer {
    break-inside: avoid;
  }
}
</style>