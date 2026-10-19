<script setup lang="ts">
/**
 * Laboratoire (DESIGN.md §12): ordres de travail (state machine
 * envoye→en_fabrication→pret→recu, annule) + factures labo avec paiements,
 * plus registre des laboratoires. All money DZD, all dates Africa/Algiers.
 */
const { t } = useI18n()
const api = useApi()
const money = useMoney()
const dates = useDates()
const toast = useToast()

// ---------------------------------------------------------------- types ----
interface Lab {
  id: number
  name: string
  phone: string
  address: string
  notes: string
  is_active: boolean
}
interface LabOrder {
  id: number
  patient: { id: number, code: string, nom: string, prenom: string }
  lab: { id: number, name: string }
  work_type: string
  teeth: string
  shade: string
  price: string
  status: string
  sent_date: string
  due_date: string | null
  received_date: string | null
  notes: string
  created_at: string
}
interface InvoicePayment {
  id: number
  amount: string
  note: string
  created_at: string
  created_by_name: string
}
interface Invoice {
  id: number
  lab: { id: number, name: string }
  number: string
  label: string
  amount: string
  paye: string
  reste: string
  issued_date: string
  notes: string
  created_at: string
  payments?: InvoicePayment[]
}

// ----------------------------------------------------------------- tabs ----
const tab = ref<"orders" | "invoices">("orders")

// --------------------------------------------------------------- orders ----
const ORDER_STATUSES = ["envoye", "en_fabrication", "pret", "recu", "annule"] as const
const ACTIVE_STATUSES = ORDER_STATUSES.filter(s => s !== "recu" && s !== "annule")

const orders = ref<LabOrder[]>([])
const counts = ref<Record<string, number>>({})
const ordersLoading = ref(true)
const ordersError = ref("")
const statusFilter = ref("")

async function loadOrders() {
  ordersLoading.value = true
  ordersError.value = ""
  try {
    const data = await api.get<{ orders: LabOrder[], counts: Record<string, number> }>(
      "/lab-orders",
      { status: statusFilter.value || undefined },
    )
    orders.value = data.orders
    counts.value = data.counts
  }
  catch (e: any) {
    ordersError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    ordersLoading.value = false
  }
}
watch(statusFilter, loadOrders)

// Lazily fetch invoice data + labs registry the first time the tab is shown.
watch(tab, (v) => {
  if (v === "invoices") {
    if (!labs.value.length) void loadLabs()
    void loadInvoices()
  }
})

async function setOrderStatus(order: LabOrder, status: string) {
  try {
    await api.post(`/lab-orders/${order.id}/status`, { status })
    toast.success(status === "annule" ? "lab.order_cancelled" : "lab.order_updated")
    await loadOrders()
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
}

/** Next allowed statuses for the inline workflow buttons. */
function nextStatuses(order: LabOrder): string[] {
  if (order.status === "envoye") return ["en_fabrication", "pret"]
  if (order.status === "en_fabrication") return ["pret"]
  if (order.status === "pret") return ["recu"]
  return []
}

const WORK_TYPES = ["couronne", "bridge", "prothese", "gouttiere", "autre"] as const

function workTypeLabel(workType: string): string {
  const known = WORK_TYPES.includes(workType as (typeof WORK_TYPES)[number])
  return known ? t(`lab.work_${workType}`) : workType
}

// ---------------------------------------------------------- new order ------
const labs = ref<Lab[]>([])
const showNewOrder = ref(false)
const orderForm = ref({
  patient_id: "", lab_id: "", work_type: "couronne" as string,
  teeth: "", shade: "", price: "", sent_date: dates.todayIso(), due_date: "", notes: "",
})
const orderSaving = ref(false)
const orderError = ref("")

interface PatientHit { id: number, code: string, nom: string, prenom: string, telephone: string }
const patientQuery = ref("")
const patientHits = ref<PatientHit[]>([])
const patientSearching = ref(false)
const patientPicked = ref<PatientHit | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined

watch(patientQuery, (q) => {
  clearTimeout(searchTimer)
  if (!q.trim() || patientPicked.value) {
    patientHits.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    patientSearching.value = true
    try {
      const data = await api.get<{ patients: PatientHit[] }>("/patients", { q, page: 1 })
      patientHits.value = data.patients.slice(0, 6)
    }
    catch {
      patientHits.value = []
    }
    finally {
      patientSearching.value = false
    }
  }, 220)
})

function pickPatient(hit: PatientHit) {
  patientPicked.value = hit
  patientQuery.value = `${hit.nom} ${hit.prenom}`
  patientHits.value = []
}

async function openNewOrder() {
  orderForm.value = {
    patient_id: "", lab_id: "", work_type: "couronne",
    teeth: "", shade: "", price: "", sent_date: dates.todayIso(), due_date: "", notes: "",
  }
  patientPicked.value = null
  patientQuery.value = ""
  patientHits.value = []
  orderError.value = ""
  showNewOrder.value = true
  if (!labs.value.length) await loadLabs()
}

async function saveOrder() {
  if (!patientPicked.value) {
    orderError.value = "errors.patient_required"
    return
  }
  orderSaving.value = true
  orderError.value = ""
  try {
    await api.post("/lab-orders", {
      patient_id: patientPicked.value.id,
      lab_id: Number(orderForm.value.lab_id),
      work_type: orderForm.value.work_type,
      teeth: orderForm.value.teeth,
      shade: orderForm.value.shade,
      price: orderForm.value.price === "" ? "0" : orderForm.value.price,
      sent_date: orderForm.value.sent_date || undefined,
      due_date: orderForm.value.due_date || undefined,
      notes: orderForm.value.notes,
    })
    showNewOrder.value = false
    toast.success("lab.order_created")
    await loadOrders()
  }
  catch (e: any) {
    orderError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    orderSaving.value = false
  }
}

// ------------------------------------------------------------- invoices ----
const invoices = ref<Invoice[]>([])
const totaux = ref({ total: 0, paye: 0 })
const invoicesLoading = ref(true)
const invoicesError = ref("")
const invoiceLabFilter = ref("")

async function loadInvoices() {
  invoicesLoading.value = true
  invoicesError.value = ""
  try {
    const data = await api.get<{ invoices: Invoice[], totaux: { total: number, paye: number } }>(
      "/lab-invoices",
      { lab_id: invoiceLabFilter.value || undefined },
    )
    invoices.value = data.invoices
    totaux.value = data.totaux
  }
  catch (e: any) {
    invoicesError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    invoicesLoading.value = false
  }
}
watch(invoiceLabFilter, loadInvoices)

// -------------------------------------------------------- new invoice ------
const showNewInvoice = ref(false)
const invoiceForm = ref({ lab_id: "", number: "", label: "", amount: "", issued_date: dates.todayIso(), notes: "" })
const invoiceSaving = ref(false)
const invoiceError = ref("")

async function openNewInvoice() {
  invoiceForm.value = { lab_id: "", number: "", label: "", amount: "", issued_date: dates.todayIso(), notes: "" }
  invoiceError.value = ""
  showNewInvoice.value = true
  if (!labs.value.length) await loadLabs()
}

async function saveInvoice() {
  invoiceSaving.value = true
  invoiceError.value = ""
  try {
    await api.post("/lab-invoices", {
      lab_id: Number(invoiceForm.value.lab_id),
      number: invoiceForm.value.number,
      label: invoiceForm.value.label,
      amount: invoiceForm.value.amount,
      issued_date: invoiceForm.value.issued_date || undefined,
      notes: invoiceForm.value.notes,
    })
    showNewInvoice.value = false
    toast.success("lab.invoice_created")
    await loadInvoices()
  }
  catch (e: any) {
    invoiceError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    invoiceSaving.value = false
  }
}

// ---------------------------------------------------- invoice detail -------
const detailInvoice = ref<Invoice | null>(null)
const detailLoading = ref(false)
const showPay = ref(false)
const payForm = ref({ amount: "", note: "" })
const paySaving = ref(false)
const payError = ref("")

function openInvoice(inv: Invoice) {
  detailInvoice.value = inv
  void loadInvoiceDetail(inv.id)
}

async function loadInvoiceDetail(id: number) {
  detailLoading.value = true
  try {
    const data = await api.get<{ invoice: Invoice }>(`/lab-invoices/${id}`)
    detailInvoice.value = data.invoice
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    detailLoading.value = false
  }
}

function openPay() {
  if (!detailInvoice.value) return
  payForm.value = { amount: detailInvoice.value.reste, note: "" }
  payError.value = ""
  showPay.value = true
}

async function savePay() {
  if (!detailInvoice.value) return
  paySaving.value = true
  payError.value = ""
  try {
    await api.post(`/lab-invoices/${detailInvoice.value.id}/payments`, {
      amount: payForm.value.amount,
      note: payForm.value.note,
    })
    showPay.value = false
    toast.success("lab.payment_saved")
    const refreshed = detailInvoice.value.id
    await Promise.all([loadInvoiceDetail(refreshed), loadInvoices()])
  }
  catch (e: any) {
    payError.value = e?.messageKey ?? "errors.generic"
    if (e?.values?.reste) payForm.value.amount = e.values.reste
  }
  finally {
    paySaving.value = false
  }
}

// ---------------------------------------------------------- labs registry --
const showLabs = ref(false)
const showLabForm = ref(false)
const editLabId = ref<number | null>(null)
const labForm = ref({ name: "", phone: "", address: "", notes: "" })
const labSaving = ref(false)
const labError = ref("")

async function loadLabs() {
  try {
    const data = await api.get<{ labs: Lab[] }>("/labs", { include_inactive: "true" })
    labs.value = data.labs
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
}

function openLabs() {
  showLabs.value = true
  void loadLabs()
}

function openCreateLab() {
  editLabId.value = null
  labForm.value = { name: "", phone: "", address: "", notes: "" }
  labError.value = ""
  showLabForm.value = true
}

function openEditLab(lab: Lab) {
  editLabId.value = lab.id
  labForm.value = { name: lab.name, phone: lab.phone, address: lab.address, notes: lab.notes }
  labError.value = ""
  showLabForm.value = true
}

async function saveLab() {
  labSaving.value = true
  labError.value = ""
  try {
    if (editLabId.value === null) {
      await api.post("/labs", labForm.value)
    }
    else {
      await api.put(`/labs/${editLabId.value}`, labForm.value)
    }
    showLabForm.value = false
    toast.success(editLabId.value === null ? "lab.lab_created" : "lab.lab_updated")
    await loadLabs()
  }
  catch (e: any) {
    labError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    labSaving.value = false
  }
}

async function toggleLab(lab: Lab) {
  try {
    await api.put(`/labs/${lab.id}`, { is_active: !lab.is_active })
    toast.success("lab.lab_updated")
    await loadLabs()
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
}

// --------------------------------------------------------------- helpers ---
function skeletonRows(n: number) {
  return Array.from({ length: n }, (_, i) => i)
}

useHead({ title: () => t("lab.title") })
await loadOrders()
</script>

<template>
  <div>
    <!-- ------------------------------------------------------ toolbar ---- -->
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("lab.title") }}</h1>
        <p class="page-subtitle">{{ counts.envoye ?? 0 }} {{ t("status.envoye").toLowerCase() }} ·
          {{ counts.en_fabrication ?? 0 }} {{ t("status.en_fabrication").toLowerCase() }} ·
          {{ counts.pret ?? 0 }} {{ t("status.pret").toLowerCase() }}</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="btn btn-secondary" @click="openLabs">{{ t("lab.nouveau_lab") }}</button>
        <button v-if="tab === 'orders'" class="btn btn-primary" @click="openNewOrder">
          {{ t("lab.new_order") }}
        </button>
        <button v-else class="btn btn-primary" @click="openNewInvoice">
          {{ t("lab.nouveau_facture") }}
        </button>
      </div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'orders' }" @click="tab = 'orders'">
        {{ t("lab.tab_orders") }}
      </button>
      <button class="tab" :class="{ active: tab === 'invoices' }" @click="tab = 'invoices'">
        {{ t("lab.tab_invoices") }}
      </button>
    </div>

    <!-- ------------------------------------------------ ORDERS TAB ------ -->
    <template v-if="tab === 'orders'">
      <div v-if="ordersError" class="alert alert-error">{{ t(ordersError) }}</div>

      <div class="card" style="padding:0;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px 0;">
          <button
            v-for="s in ['']"
            :key="s"
            class="badge"
            :class="{ 'badge-active': statusFilter === s }"
            style="cursor:pointer;"
            @click="statusFilter = s"
          >
            {{ t("common.none") }}
          </button>
          <button
            v-for="s in ORDER_STATUSES"
            :key="s"
            class="badge"
            :class="[`badge-${s}`, { 'badge-active': statusFilter === s }]"
            style="cursor:pointer;"
            @click="statusFilter = statusFilter === s ? '' : s"
          >
            {{ t(`status.${s}`) }} · {{ counts[s] ?? 0 }}
          </button>
        </div>

        <div v-if="ordersLoading" style="padding:8px 16px 16px;" aria-hidden="true">
          <div v-for="i in skeletonRows(6)" :key="i" class="skeleton skeleton-row" />
        </div>

        <div v-else-if="!orders.length" class="empty-state">
          <span class="empty-icon">⚒</span>
          {{ t("lab.aucun_ordre") }}
          <div class="empty-hint">{{ t("lab.new_order") }}</div>
        </div>

        <div v-else class="table-wrap" style="padding-bottom:8px;">
          <table class="table">
            <thead>
              <tr>
                <th>{{ t("appointment.patient") }}</th>
                <th>{{ t("lab.labo") }}</th>
                <th>{{ t("lab.type_travail") }}</th>
                <th>{{ t("lab.dents") }}</th>
                <th>{{ t("lab.teinte") }}</th>
                <th class="num">{{ t("lab.prix") }}</th>
                <th>{{ t("lab.date_souhaitee") }}</th>
                <th>{{ t("common.statut") }}</th>
                <th style="min-width:220px;">{{ t("common.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="o in orders" :key="o.id">
                <td>
                  <NuxtLink :to="`/patients/${o.patient.id}`" style="font-weight:600;">
                    {{ o.patient.nom }} {{ o.patient.prenom }}
                  </NuxtLink>
                </td>
                <td>{{ o.lab.name }}</td>
                <td>{{ workTypeLabel(o.work_type) }}</td>
                <td class="small">{{ o.teeth || "—" }}</td>
                <td class="small">{{ o.shade || "—" }}</td>
                <td class="num">{{ money.fmt(o.price) }}</td>
                <td class="small">{{ dates.fmtDate(o.due_date) }}</td>
                <td><span class="badge" :class="`badge-${o.status}`">{{ t(`status.${o.status}`) }}</span></td>
                <td>
                  <div v-if="nextStatuses(o).length || o.status !== 'annule'" style="display:flex;gap:6px;flex-wrap:wrap;">
                    <button
                      v-for="s in nextStatuses(o)"
                      :key="s"
                      class="btn btn-text btn-sm"
                      @click="setOrderStatus(o, s)"
                    >
                      {{ t(`status.${s}`) }} →
                    </button>
                    <button
                      v-if="ACTIVE_STATUSES.includes(o.status as any)"
                      class="btn btn-text btn-sm"
                      style="color:var(--color-danger);"
                      @click="setOrderStatus(o, 'annule')"
                    >
                      {{ t("status.annule") }}
                    </button>
                  </div>
                  <span v-else class="small muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ------------------------------------------------ INVOICES TAB ---- -->
    <template v-else>
      <div v-if="invoicesError" class="alert alert-error">{{ t(invoicesError) }}</div>

      <div style="display:grid;grid-template-columns:280px 1fr;gap:16px;align-items:start;">
        <div class="card">
          <h2 class="section-title" style="margin-bottom:12px;">{{ t("lab.total_du") }}</h2>
          <div class="money-row">
            <span class="money-label">{{ t("lab.montant") }}</span>
            <span class="money-value">{{ money.fmt(totaux.total) }}</span>
          </div>
          <div class="money-row">
            <span class="money-label">{{ t("lab.paye") }}</span>
            <span class="money-value" style="color:var(--color-success);">{{ money.fmt(totaux.paye) }}</span>
          </div>
          <div class="money-row">
            <span class="money-label">{{ t("lab.reste") }}</span>
            <span class="money-value" :class="{ 'money-reste': totaux.total - totaux.paye > 0.005 }">
              {{ money.fmt(totaux.total - totaux.paye) }}
            </span>
          </div>
        </div>

        <div class="card" style="padding:0;">
          <div style="padding:12px 16px 0;">
            <select v-model="invoiceLabFilter" class="select" style="max-width:280px;">
              <option value="">{{ t("common.none") }} — {{ t("lab.labo") }}</option>
              <option v-for="l in labs" :key="l.id" :value="String(l.id)">{{ l.name }}</option>
            </select>
          </div>

          <div v-if="invoicesLoading" style="padding:8px 16px 16px;" aria-hidden="true">
            <div v-for="i in skeletonRows(5)" :key="i" class="skeleton skeleton-row" />
          </div>

          <div v-else-if="!invoices.length" class="empty-state">
            <span class="empty-icon">▤</span>
            {{ t("lab.aucune_facture") }}
            <div class="empty-hint">{{ t("lab.nouveau_facture") }}</div>
          </div>

          <div v-else class="table-wrap" style="padding-bottom:8px;">
            <table class="table">
              <thead>
                <tr>
                  <th>{{ t("lab.numero") }}</th>
                  <th>{{ t("lab.labo") }}</th>
                  <th>{{ t("lab.libelle") }}</th>
                  <th>{{ t("lab.date_facture") }}</th>
                  <th class="num">{{ t("lab.montant") }}</th>
                  <th class="num">{{ t("lab.paye") }}</th>
                  <th class="num">{{ t("lab.reste") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="inv in invoices" :key="inv.id" class="row-link" @click="openInvoice(inv)">
                  <td style="font-weight:600;">{{ inv.number }}</td>
                  <td>{{ inv.lab.name }}</td>
                  <td class="small">{{ inv.label || "—" }}</td>
                  <td class="small muted">{{ dates.fmtDate(inv.issued_date) }}</td>
                  <td class="num">{{ money.fmt(inv.amount) }}</td>
                  <td class="num" style="color:var(--color-success);">{{ money.fmt(inv.paye) }}</td>
                  <td class="num" :style="Number(inv.reste) > 0 ? 'color:var(--color-danger);' : ''">
                    {{ money.fmt(inv.reste) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- ----------------------------------------------- NEW ORDER DLG ---- -->
    <AppDialog :open="showNewOrder" :title="t('lab.new_order')" wide @close="showNewOrder = false">
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-patient">{{ t("appointment.patient") }}</label>
          <input
            id="lo-patient"
            v-model="patientQuery"
            class="input"
            :placeholder="t('common.search_placeholder')"
            autocomplete="off"
          >
          <ul v-if="patientHits.length" class="search-hits">
            <li v-for="hit in patientHits" :key="hit.id">
              <button type="button" @click="pickPatient(hit)">
                <strong>{{ hit.nom }} {{ hit.prenom }}</strong>
                <span class="small muted"> · {{ hit.telephone }}</span>
              </button>
            </li>
          </ul>
          <div v-else-if="patientSearching" class="small muted">{{ t("common.loading") }}</div>
          <div v-else-if="patientPicked" class="field-error" style="color:var(--color-success);">
            ✓ {{ patientPicked.code }}
          </div>
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-lab">{{ t("lab.labo") }}</label>
          <select id="lo-lab" v-model="orderForm.lab_id" class="select">
            <option value="">—</option>
            <option v-for="l in labs.filter(x => x.is_active)" :key="l.id" :value="String(l.id)">
              {{ l.name }}
            </option>
          </select>
        </div>
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-type">{{ t("lab.type_travail") }}</label>
          <select id="lo-type" v-model="orderForm.work_type" class="select">
            <option v-for="wt in WORK_TYPES" :key="wt" :value="wt">{{ t(`lab.work_${wt}`) }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom:12px;width:110px;">
          <label for="lo-teeth">{{ t("lab.dents") }}</label>
          <input id="lo-teeth" v-model="orderForm.teeth" class="input" placeholder="16, 17">
        </div>
        <div class="field" style="margin-bottom:12px;width:110px;">
          <label for="lo-shade">{{ t("lab.teinte") }}</label>
          <input id="lo-shade" v-model="orderForm.shade" class="input" placeholder="A2">
        </div>
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-price">{{ t("lab.prix") }} ({{ t("common.currency_da") }})</label>
          <input id="lo-price" v-model="orderForm.price" class="input" inputmode="decimal">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-sent">{{ t("lab.date_envoi") }}</label>
          <input id="lo-sent" v-model="orderForm.sent_date" type="date" class="input">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lo-due">{{ t("lab.date_souhaitee") }}</label>
          <input id="lo-due" v-model="orderForm.due_date" type="date" class="input">
        </div>
      </div>
      <div class="field" style="margin-bottom:16px;">
        <label for="lo-notes">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
        <textarea id="lo-notes" v-model="orderForm.notes" class="textarea" style="min-height:60px;" />
      </div>
      <div v-if="orderError" class="alert alert-error">{{ t(orderError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showNewOrder = false">{{ t("common.cancel") }}</button>
        <button
          class="btn btn-primary"
          :disabled="orderSaving || !patientPicked || !orderForm.lab_id"
          @click="saveOrder"
        >
          {{ t("common.save") }}
        </button>
      </div>
    </AppDialog>

    <!-- --------------------------------------------- NEW INVOICE DLG ---- -->
    <AppDialog :open="showNewInvoice" :title="t('lab.nouveau_facture')" @close="showNewInvoice = false">
      <div class="field" style="margin-bottom:12px;">
        <label for="li-lab">{{ t("lab.labo") }}</label>
        <select id="li-lab" v-model="invoiceForm.lab_id" class="select">
          <option value="">—</option>
          <option v-for="l in labs.filter(x => x.is_active)" :key="l.id" :value="String(l.id)">
            {{ l.name }}
          </option>
        </select>
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="li-number">{{ t("lab.numero") }}</label>
          <input id="li-number" v-model="invoiceForm.number" class="input">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="li-date">{{ t("lab.date_facture") }}</label>
          <input id="li-date" v-model="invoiceForm.issued_date" type="date" class="input">
        </div>
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="li-amount">{{ t("lab.montant") }} ({{ t("common.currency_da") }})</label>
          <input id="li-amount" v-model="invoiceForm.amount" class="input" inputmode="decimal">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="li-label">{{ t("lab.libelle") }} ({{ t("common.optional") }})</label>
          <input id="li-label" v-model="invoiceForm.label" class="input">
        </div>
      </div>
      <div class="field" style="margin-bottom:16px;">
        <label for="li-notes">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
        <input id="li-notes" v-model="invoiceForm.notes" class="input">
      </div>
      <div v-if="invoiceError" class="alert alert-error">{{ t(invoiceError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showNewInvoice = false">{{ t("common.cancel") }}</button>
        <button
          class="btn btn-primary"
          :disabled="invoiceSaving || !invoiceForm.lab_id || !invoiceForm.number"
          @click="saveInvoice"
        >
          {{ t("common.save") }}
        </button>
      </div>
    </AppDialog>

    <!-- ------------------------------------------- INVOICE DETAIL DLG --- -->
    <AppDialog
      :open="detailInvoice !== null"
      :title="detailInvoice ? `${t('lab.numero')} ${detailInvoice.number}` : ''"
      wide
      @close="detailInvoice = null"
    >
      <template v-if="detailInvoice">
        <div class="money-row">
          <span class="money-label">{{ t("lab.labo") }}</span>
          <span>{{ detailInvoice.lab.name }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("lab.libelle") }}</span>
          <span>{{ detailInvoice.label || "—" }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("lab.date_facture") }}</span>
          <span>{{ dates.fmtDate(detailInvoice.issued_date) }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("lab.montant") }}</span>
          <span class="money-value">{{ money.fmt(detailInvoice.amount) }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("lab.paye") }}</span>
          <span class="money-value" style="color:var(--color-success);">{{ money.fmt(detailInvoice.paye) }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("lab.reste") }}</span>
          <span class="money-value" :class="{ 'money-reste': Number(detailInvoice.reste) > 0 }">
            {{ money.fmt(detailInvoice.reste) }}
          </span>
        </div>

        <h3 class="section-title" style="font-size:14px;margin:16px 0 4px;">
          {{ t("lab.enregistrer_paiement") }}
        </h3>
        <div v-if="detailLoading" style="padding:8px 0;" aria-hidden="true">
          <div class="skeleton skeleton-line w-60" />
          <div class="skeleton skeleton-line w-40" />
        </div>
        <div v-else-if="!detailInvoice.payments?.length" class="empty-state" style="padding:12px 0;">
          {{ t("payments.aucun") }}
        </div>
        <table v-else class="table">
          <tbody>
            <tr v-for="p in detailInvoice.payments" :key="p.id">
              <td class="small muted">{{ dates.fmtDateTime(p.created_at) }}</td>
              <td class="num">{{ money.fmt(p.amount) }}</td>
              <td class="small muted">{{ p.note }}</td>
              <td class="small muted">{{ p.created_by_name }}</td>
            </tr>
          </tbody>
        </table>

        <div class="dialog-actions" style="margin-top:8px;">
          <button
            v-if="Number(detailInvoice.reste) > 0"
            class="btn btn-primary"
            @click="openPay"
          >
            {{ t("lab.enregistrer_paiement") }}
          </button>
          <span v-else class="badge badge-recu" style="align-self:center;">{{ t("lab.paye") }}</span>
        </div>
      </template>
    </AppDialog>

    <!-- ---------------------------------------------- PAY INVOICE DLG --- -->
    <AppDialog :open="showPay" :title="t('lab.enregistrer_paiement')" @close="showPay = false">
      <p v-if="detailInvoice" class="small muted" style="margin-bottom:12px;">
        {{ t("lab.reste") }} : {{ money.fmt(detailInvoice.reste) }}
      </p>
      <div class="field" style="margin-bottom:12px;">
        <label for="lip-amount">{{ t("payments.montant") }}</label>
        <input id="lip-amount" v-model="payForm.amount" class="input" inputmode="decimal">
      </div>
      <div class="field" style="margin-bottom:16px;">
        <label for="lip-note">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
        <input id="lip-note" v-model="payForm.note" class="input">
      </div>
      <div v-if="payError" class="alert alert-error">{{ t(payError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showPay = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="paySaving" @click="savePay">{{ t("common.confirm") }}</button>
      </div>
    </AppDialog>

    <!-- -------------------------------------------------- LABS DLG ------ -->
    <AppDialog :open="showLabs" :title="t('lab.nouveau_lab')" wide @close="showLabs = false">
      <div style="display:flex;justify-content:flex-end;margin-bottom:8px;">
        <button class="btn btn-secondary btn-sm" @click="openCreateLab">{{ t("common.add") }}</button>
      </div>
      <div v-if="!labs.length" class="empty-state">
        <span class="empty-icon">⚒</span>
        {{ t("lab.aucun") }}
        <div class="empty-hint">{{ t("lab.nom_lab") }}</div>
      </div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t("lab.nom_lab") }}</th>
            <th>{{ t("lab.telephone") }}</th>
            <th>{{ t("patients.adresse") }}</th>
            <th style="width:1%;" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in labs" :key="l.id" :style="l.is_active ? '' : 'opacity:0.55;'">
            <td style="font-weight:600;">{{ l.name }}</td>
            <td class="small">{{ l.phone || "—" }}</td>
            <td class="small muted">{{ l.address || "—" }}</td>
            <td style="white-space:nowrap;">
              <button class="btn btn-text btn-sm" @click="openEditLab(l)">{{ t("common.edit") }}</button>
              <button class="btn btn-text btn-sm" @click="toggleLab(l)">
                {{ l.is_active ? "✕" : "✓" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </AppDialog>

    <!-- ---------------------------------------------- LAB FORM DLG ------ -->
    <AppDialog
      :open="showLabForm"
      :title="editLabId === null ? t('lab.nouveau_lab') : t('common.edit')"
      @close="showLabForm = false"
    >
      <div class="field" style="margin-bottom:12px;">
        <label for="lab-name">{{ t("lab.nom_lab") }}</label>
        <input id="lab-name" v-model="labForm.name" class="input">
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lab-phone">{{ t("lab.telephone") }} ({{ t("common.optional") }})</label>
          <input id="lab-phone" v-model="labForm.phone" class="input" inputmode="tel">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="lab-addr">{{ t("patients.adresse") }} ({{ t("common.optional") }})</label>
          <input id="lab-addr" v-model="labForm.address" class="input">
        </div>
      </div>
      <div class="field" style="margin-bottom:16px;">
        <label for="lab-notes">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
        <input id="lab-notes" v-model="labForm.notes" class="input">
      </div>
      <div v-if="labError" class="alert alert-error">{{ t(labError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showLabForm = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="labSaving || !labForm.name" @click="saveLab">
          {{ t("common.save") }}
        </button>
      </div>
    </AppDialog>
  </div>
</template>
