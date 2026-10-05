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
interface PatientFull { id: number, nom: string, prenom: string, telephone: string, code: string }
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

async function openDoc(id: number) {
  errorMsg.value = ""
  try {
    const data = await api.get<{ document: DocFull, clinic: ClinicSettings }>(`/documents/${id}`)
    current.value = data.document
    settings.value = data.clinic
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
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
      <!-- Preview / print -->
      <div v-if="current" class="card print-area" style="max-width:720px;">
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

        <template v-if="current.doc_type === 'ordonnance'">
          <ol style="margin:0;padding-inline-start:20px;">
            <li v-for="(line, idx) in current.content?.lines ?? []" :key="idx" style="margin-bottom:6px;">
              {{ line }}
            </li>
          </ol>
          <p v-if="current.content?.note" class="small muted" style="margin-top:12px;">{{ current.content.note }}</p>
        </template>
        <template v-else>
          <p style="white-space:pre-wrap;">{{ current.content?.text }}</p>
          <p v-if="current.doc_type === 'certificat' && current.content?.duration_days" class="small" style="margin-top:8px;">
            {{ t("documents.duree_jours") }} : {{ current.content.duration_days }}
          </p>
        </template>

        <p v-if="settings?.footer_note" class="small muted" style="margin-top:24px;">{{ settings.footer_note }}</p>

        <div class="dialog-actions" style="margin-top:24px;">
          <button class="btn btn-secondary" @click="current = null">{{ t("common.close") }}</button>
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
