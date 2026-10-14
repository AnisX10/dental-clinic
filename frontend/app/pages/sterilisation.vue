<script setup lang="ts">
/**
 * Stérilisation: autoclave cycle tracing. Create a cycle with loaded
 * instruments, then finish it (conforme or échec). Locked after finishing.
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const toast = useToast()

interface CycleItem { item_name: string, quantity: number, instrument_status: string }
interface Cycle {
  id: number, cycle_no: string, status: string, started_at: string,
  finished_at: string | null, autoclave_name: string, program: string, notes: string,
  items?: CycleItem[],
}

const cycles = ref<Cycle[]>([])
const loading = ref(true)
const errorMsg = ref("")

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ cycles: Cycle[] }>("/sterilization/cycles")
    cycles.value = data.cycles
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await load()

function statusBadge(status: string) {
  if (status === "done") return "badge badge-ok"
  if (status === "failed") return "badge badge-error"
  return "badge badge-warn"
}

function statusKey(status: string) {
  return status === "done" ? "sterilisation.etat_termine" : status === "failed" ? "sterilisation.etat_echec" : "sterilisation.etat_en_cours"
}

// ---- Create cycle ----------------------------------------------------------
const showNew = ref(false)
const saving = ref(false)
const formError = ref("")
const form = ref({ autoclave_name: "", program: "", notes: "" })
const items = ref<CycleItem[]>([])

function openNew() {
  form.value = { autoclave_name: "", program: "", notes: "" }
  items.value = [{ item_name: "", quantity: 1, instrument_status: "sterile" }]
  formError.value = ""
  showNew.value = true
}

function addLine() {
  items.value.push({ item_name: "", quantity: 1, instrument_status: "sterile" })
}

function removeLine(idx: number) {
  items.value.splice(idx, 1)
}

async function create() {
  const clean = items.value.filter(i => i.item_name.trim())
  if (!clean.length) {
    formError.value = "errors.invalid_sterilization_item"
    return
  }
  saving.value = true
  formError.value = ""
  try {
    await api.post("/sterilization/cycles", {
      ...form.value,
      items: clean.map(i => ({
        item_name: i.item_name.trim(),
        quantity: Number(i.quantity) || 1,
        instrument_status: i.instrument_status,
      })),
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
const current = ref<Cycle | null>(null)
const detailError = ref("")
const finishBusy = ref(false)

async function openCycle(id: number) {
  detailError.value = ""
  loading.value = true
  try {
    const data = await api.get<{ cycle: Cycle }>(`/sterilization/cycles/${id}`)
    current.value = data.cycle
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}

const hasFailedItems = computed(() =>
  (current.value?.items ?? []).some(i => i.instrument_status === "failed"),
)

const isRunning = computed(() => current.value?.status === "in_progress")

async function finishCycle(result: string) {
  if (!current.value) return
  finishBusy.value = true
  detailError.value = ""
  try {
    const data = await api.post<{ cycle: Cycle }>(`/sterilization/cycles/${current.value.id}/finish`, { result })
    current.value = data.cycle
    toast.success("common.save")
    await load()
  }
  catch (e: any) {
    detailError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    finishBusy.value = false
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("sterilisation.title") }}</h1>
        <p class="page-subtitle">{{ t("sterilisation.subtitle") }}</p>
      </div>
      <button class="btn btn-primary" @click="openNew">
        {{ t("sterilisation.nouveaux_cycle") }}
      </button>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <!-- Detail -->
    <div v-if="current" class="card" style="max-width:760px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
        <div>
          <strong style="font-size:16px;">{{ t("sterilisation.cycle_no") }} {{ current.cycle_no }}</strong>
          <div class="small muted">
            {{ current.autoclave_name || "—" }}
            <template v-if="current.program"> · {{ t("sterilisation.programme") }}: {{ current.program }}</template>
          </div>
        </div>
        <div style="text-align:end;">
          <span :class="statusBadge(current.status)" style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);">
            {{ t(statusKey(current.status)) }}
          </span>
          <div class="small muted" style="margin-top:6px;">
            {{ dates.fmtDateTime(current.started_at) }}
            <template v-if="current.finished_at">
              → {{ dates.fmtDateTime(current.finished_at) }}
            </template>
          </div>
        </div>
      </div>
      <hr style="border:none;border-top:1px solid var(--color-border);margin:16px 0;">

      <h2 class="section-title" style="margin-bottom:8px;">{{ t("sterilisation.articles") }}</h2>
      <table class="table">
        <thead>
          <tr>
            <th>{{ t("sterilisation.article") }}</th>
            <th>{{ t("sterilisation.quantite_lbl") }}</th>
            <th>{{ t("sterilisation.controle") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in current.items" :key="idx">
            <td>{{ item.item_name }}</td>
            <td class="small muted">{{ item.quantity }}</td>
            <td>
              <span :class="item.instrument_status === 'failed' ? 'badge badge-error' : 'badge badge-ok'" style="padding:2px 8px;border-radius:999px;font-size:12px;background:var(--color-surface-2);">
                {{ t(item.instrument_status === "failed" ? "sterilisation.controle_echec" : "sterilisation.controle_sterile") }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <p v-if="current.notes" class="small muted" style="margin-top:12px;">{{ current.notes }}</p>
      <p v-if="isRunning" class="small muted" style="margin-top:8px;">{{ t("sterilisation.articles_hint") }}</p>

      <div v-if="detailError" class="alert alert-error" style="margin-top:12px;">{{ t(detailError) }}</div>
      <div class="dialog-actions" style="margin-top:16px;">
        <button class="btn btn-secondary" @click="current = null">{{ t("common.back") }}</button>
        <template v-if="isRunning">
          <button class="btn btn-text" style="color:var(--color-danger);" :disabled="finishBusy" @click="finishCycle('failed')">
            {{ t("sterilisation.terminer_echec") }}
          </button>
          <button class="btn btn-primary" :disabled="finishBusy" @click="finishCycle('done')">
            {{ t("sterilisation.terminer_valide") }}
          </button>
        </template>
      </div>
    </div>

    <!-- List -->
    <template v-else>
      <div v-if="loading" class="card" style="padding:16px;" aria-hidden="true">
        <div v-for="i in 4" :key="i" class="skeleton skeleton-line" :class="i % 2 ? 'w-60' : 'w-40'" />
      </div>
      <div v-else-if="!cycles.length" class="card empty-state">
        <span class="empty-icon">☢</span>
        {{ t("sterilisation.aucun") }}
        <div class="empty-hint">{{ t("sterilisation.nouveaux_cycle") }}</div>
      </div>
      <div v-else class="card" style="padding:0;">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t("sterilisation.cycle_no") }}</th>
              <th>{{ t("sterilisation.autoclave") }}</th>
              <th>{{ t("sterilisation.debut") }}</th>
              <th>{{ t("sterilisation.fin") }}</th>
              <th>{{ t("sterilisation.etat_col") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in cycles" :key="c.id" class="row-link" @click="openCycle(c.id)">
              <td><strong>{{ c.cycle_no }}</strong></td>
              <td class="small muted">{{ c.autoclave_name || "—" }}</td>
              <td class="small muted">{{ dates.fmtDateTime(c.started_at) }}</td>
              <td class="small muted">{{ c.finished_at ? dates.fmtDateTime(c.finished_at) : "—" }}</td>
              <td>
                <span :class="statusBadge(c.status)" style="padding:4px 10px;border-radius:999px;font-size:12px;background:var(--color-surface-2);display:inline-block;">
                  {{ t(statusKey(c.status)) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Create cycle dialog -->
    <AppDialog :open="showNew" :title="t('sterilisation.nouveaux_cycle')" @close="showNew = false">
      <div style="display:flex;gap:12px;margin-bottom:12px;">
        <div class="field" style="flex:1;">
          <label for="st-autoclave">{{ t("sterilisation.autoclave") }}</label>
          <input id="st-autoclave" v-model="form.autoclave_name" class="input" :placeholder="t('common.optional')">
        </div>
        <div class="field" style="flex:1;">
          <label for="st-program">{{ t("sterilisation.programme") }}</label>
          <input id="st-program" v-model="form.program" class="input" :placeholder="t('common.optional')">
        </div>
      </div>

      <div class="nav-group-label" style="margin-bottom:8px;">{{ t("sterilisation.articles") }}</div>
      <div v-for="(item, idx) in items" :key="idx" style="display:flex;gap:8px;align-items:end;margin-bottom:8px;flex-wrap:wrap;">
        <input v-model="item.item_name" class="input" style="flex:1;min-width:150px;" :placeholder="t('sterilisation.article')">
        <input v-model.number="item.quantity" type="number" min="1" max="500" class="input" style="width:64px;">
        <select v-model="item.instrument_status" class="select" style="width:130px;">
          <option value="sterile">{{ t("sterilisation.controle_sterile") }}</option>
          <option value="failed">{{ t("sterilisation.controle_echec") }}</option>
        </select>
        <button class="btn btn-text btn-sm" @click="removeLine(idx)">✕</button>
      </div>
      <button class="btn btn-text btn-sm" @click="addLine">{{ t("documents.ajouter_ligne") }}</button>

      <div class="field" style="margin-top:12px;">
        <label for="st-notes">{{ t("common.notes") }}</label>
        <textarea id="st-notes" v-model="form.notes" class="textarea" rows="2" />
      </div>

      <div v-if="formError" class="alert alert-error">{{ t(formError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showNew = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="saving" @click="create">{{ t("common.save") }}</button>
      </div>
    </AppDialog>
  </div>
</template>
