<script setup lang="ts">
/**
 * Stock & matériaux: append-only ledger (create → adjust/correct → history),
 * valuation, low-stock alerts and owner-managed treatment consumable links.
 */
const { t } = useI18n()
const api = useApi()
const money = useMoney()
const dates = useDates()
const toast = useToast()
const auth = useAuth()

interface StockItem {
  id: number
  name: string
  category: string
  unit: string
  stock_quantity: string
  min_quantity: string
  unit_cost: string | null
  is_low: boolean
  is_active: boolean
  notes: string
}
interface Movement {
  id: number
  item_id: number
  delta: string
  reason: string
  note: string
  reference_type: string
  reference_id: number | null
  created_by_name: string
  created_at: string
}
interface Link {
  id: number
  catalog_item_id: number
  stock_item_id: number
  stock_item_name: string
  unit: string
  quantity: string
}
interface CatalogItem { id: number, name: string, category: string, default_price: string, is_active: boolean }

const CATEGORIES = ["consommable", "equipement", "bureau", "autre"] as const
const ADJUST_REASONS = ["restock", "consumption", "adjustment", "initial"] as const

function fmtQty(value: string): string {
  const n = Number.parseFloat(value)
  if (!Number.isFinite(n)) return "—"
  return new Intl.NumberFormat("fr-DZ", { maximumFractionDigits: 2 }).format(n)
}

// ------------------------------------------------------------------ items ---
const items = ref<StockItem[]>([])
const lowCount = ref(0)
const valuation = ref({ valeur: "0", nb_articles: 0 })
const loading = ref(true)
const errorMsg = ref("")
const route = useRoute()
// /stock?bas=1 ouvre la page avec le filtre « stock bas » actif (lien depuis Aujourd'hui).
const lowOnly = ref(route.query.bas === "1")

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const [list, val] = await Promise.all([
      api.get<{ items: StockItem[], low_count: number }>("/stock", { low_stock: lowOnly.value ? "true" : undefined }),
      api.get<{ valeur: string, nb_articles: number }>("/stock/valuation"),
    ])
    items.value = list.items
    lowCount.value = list.low_count
    valuation.value = val
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
watch(lowOnly, load)

function catLabel(cat: string): string {
  const known = CATEGORIES.includes(cat as (typeof CATEGORIES)[number])
  return known ? t(`stock.cat_${cat}`) : cat
}

// ------------------------------------------------------ create / edit form --
const showForm = ref(false)
const editId = ref<number | null>(null)
const form = ref({
  name: "", category: "consommable" as string, unit: "unite",
  initial_quantity: "0", min_quantity: "0", unit_cost: "", notes: "", is_active: true,
})
const saving = ref(false)
const formError = ref("")

function openCreate() {
  editId.value = null
  form.value = { name: "", category: "consommable", unit: "unite", initial_quantity: "0", min_quantity: "0", unit_cost: "", notes: "", is_active: true }
  formError.value = ""
  showForm.value = true
}

function openEdit(item: StockItem) {
  editId.value = item.id
  form.value = {
    name: item.name, category: item.category, unit: item.unit,
    initial_quantity: "0", min_quantity: item.min_quantity,
    unit_cost: item.unit_cost ?? "", notes: item.notes, is_active: item.is_active,
  }
  formError.value = ""
  showForm.value = true
}

async function saveForm() {
  saving.value = true
  formError.value = ""
  try {
    if (editId.value === null) {
      await api.post("/stock", {
        name: form.value.name,
        category: form.value.category,
        unit: form.value.unit,
        initial_quantity: form.value.initial_quantity,
        min_quantity: form.value.min_quantity,
        unit_cost: form.value.unit_cost === "" ? null : form.value.unit_cost,
        notes: form.value.notes,
      })
      toast.success("stock.item_created")
    }
    else {
      await api.patch(`/stock/${editId.value}`, {
        name: form.value.name,
        category: form.value.category,
        unit: form.value.unit,
        min_quantity: form.value.min_quantity,
        unit_cost: form.value.unit_cost === "" ? null : form.value.unit_cost,
        notes: form.value.notes,
        is_active: form.value.is_active,
      })
      toast.success("stock.item_updated")
    }
    showForm.value = false
    await load()
  }
  catch (e: any) {
    formError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------- adjust ----
const adjustItem = ref<StockItem | null>(null)
const adjustForm = ref({ delta: "", reason: "restock", note: "" })
const adjustSaving = ref(false)
const adjustError = ref("")

function openAdjust(item: StockItem) {
  adjustItem.value = item
  adjustForm.value = { delta: "", reason: "restock", note: "" }
  adjustError.value = ""
}

async function saveAdjust() {
  if (!adjustItem.value) return
  adjustSaving.value = true
  adjustError.value = ""
  try {
    await api.post(`/stock/${adjustItem.value.id}/adjust`, {
      delta: adjustForm.value.delta,
      reason: adjustForm.value.reason,
      note: adjustForm.value.note,
    })
    toast.success("stock.adjusted")
    adjustItem.value = null
    await load()
  }
  catch (e: any) {
    adjustError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    adjustSaving.value = false
  }
}

// --------------------------------------------------------------- correct ----
const correctItem = ref<StockItem | null>(null)
const correctForm = ref({ quantity: "", note: "" })
const correctSaving = ref(false)
const correctError = ref("")

function openCorrect(item: StockItem) {
  correctItem.value = item
  correctForm.value = { quantity: item.stock_quantity, note: "" }
  correctError.value = ""
}

async function saveCorrect() {
  if (!correctItem.value) return
  correctSaving.value = true
  correctError.value = ""
  try {
    await api.post(`/stock/${correctItem.value.id}/correct`, {
      quantity: correctForm.value.quantity,
      note: correctForm.value.note,
    })
    toast.success("stock.corrected")
    correctItem.value = null
    await load()
  }
  catch (e: any) {
    correctError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    correctSaving.value = false
  }
}

// -------------------------------------------------------------- movements ---
const historyItem = ref<StockItem | null>(null)
const movements = ref<Movement[]>([])
const movementsLoading = ref(false)

function openHistory(item: StockItem) {
  historyItem.value = item
  movements.value = []
  void loadMovements(item.id)
}

async function loadMovements(itemId: number) {
  movementsLoading.value = true
  try {
    const data = await api.get<{ movements: Movement[] }>(`/stock/${itemId}/movements`)
    movements.value = data.movements
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
  finally {
    movementsLoading.value = false
  }
}

// ------------------------------------------------------------------ links ---
const catalog = ref<CatalogItem[]>([])
const links = ref<Link[]>([])
const showLinks = ref(false)
const linkForm = ref({ catalog_item_id: "", stock_item_id: "", quantity: "1" })
const linkSaving = ref(false)
const linkError = ref("")

async function openLinks() {
  showLinks.value = true
  try {
    const [lk, cat] = await Promise.all([
      api.get<{ links: Link[] }>("/stock/links"),
      api.get<{ items: CatalogItem[] }>("/clinical/catalog"),
    ])
    links.value = lk.links
    catalog.value = cat.items.filter(i => i.is_active)
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
}

function catalogName(catalogItemId: number): string {
  return catalog.value.find(i => i.id === catalogItemId)?.name ?? `#${catalogItemId}`
}

async function saveLink() {
  linkSaving.value = true
  linkError.value = ""
  try {
    await api.post("/stock/links", {
      catalog_item_id: Number(linkForm.value.catalog_item_id),
      stock_item_id: Number(linkForm.value.stock_item_id),
      quantity: linkForm.value.quantity,
    })
    toast.success("stock.link_created")
    linkForm.value = { catalog_item_id: linkForm.value.catalog_item_id, stock_item_id: "", quantity: "1" }
    links.value = (await api.get<{ links: Link[] }>("/stock/links")).links
  }
  catch (e: any) {
    linkError.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    linkSaving.value = false
  }
}

async function deleteLink(link: Link) {
  try {
    await api.del(`/stock/links/${link.id}`)
    toast.success("stock.link_deleted")
    links.value = links.value.filter(l => l.id !== link.id)
  }
  catch (e: any) {
    toast.error(e?.messageKey ?? "errors.generic")
  }
}

function skeletonRows(n: number) {
  return Array.from({ length: n }, (_, i) => i)
}

useHead({ title: () => t("stock.title") })
await load()
</script>

<template>
  <div>
    <!-- ------------------------------------------------------ toolbar ---- -->
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("stock.title") }}</h1>
        <p class="page-subtitle">{{ items.length }} {{ t("stock.nb_articles") }}
          <span v-if="lowCount > 0" style="color:var(--color-danger);">
            · {{ lowCount }} {{ t("stock.stock_bas").toLowerCase() }}
          </span>
        </p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button
          v-if="auth.user.value?.is_owner"
          class="btn btn-secondary"
          @click="openLinks"
        >
          {{ t("stock.liens_treatments") }}
        </button>
        <button class="btn btn-primary" @click="openCreate">{{ t("stock.nouvel_article") }}</button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div style="display:grid;grid-template-columns:280px 1fr;gap:16px;align-items:start;">
      <!-- summary card -->
      <div class="card">
        <h2 class="section-title" style="margin-bottom:12px;">{{ t("stock.valeur_stock") }}</h2>
        <div class="money-row">
          <span class="money-label">{{ t("stock.valeur_stock") }}</span>
          <span class="money-value">{{ money.fmt(valuation.valeur) }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("stock.nb_articles") }}</span>
          <span class="money-value">{{ valuation.nb_articles }}</span>
        </div>
        <div style="margin-top:12px;">
          <button
            class="badge"
            :class="{ 'badge-active': lowOnly }"
            style="cursor:pointer;"
            @click="lowOnly = !lowOnly"
          >
            {{ t("stock.stock_bas") }} · {{ lowCount }}
          </button>
        </div>
      </div>

      <!-- items table -->
      <div class="card" style="padding:0;">
        <div v-if="loading" style="padding:8px 16px 16px;" aria-hidden="true">
          <div v-for="i in skeletonRows(6)" :key="i" class="skeleton skeleton-row" />
        </div>

        <div v-else-if="!items.length" class="empty-state">
          <span class="empty-icon">◫</span>
          {{ t("stock.aucun") }}
          <div class="empty-hint">{{ t("stock.nouvel_article") }}</div>
        </div>

        <div v-else class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>{{ t("stock.article") }}</th>
                <th>{{ t("stock.categorie") }}</th>
                <th class="num">{{ t("stock.quantite") }}</th>
                <th class="num">{{ t("stock.seuil") }}</th>
                <th class="num">{{ t("stock.cout_unitaire") }}</th>
                <th style="min-width:230px;">{{ t("common.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id" :style="item.is_active ? '' : 'opacity:0.55;'">
                <td>
                  <div style="font-weight:600;">{{ item.name }}</div>
                  <div v-if="item.notes" class="small muted">{{ item.notes }}</div>
                </td>
                <td class="small">{{ catLabel(item.category) }}</td>
                <td class="num" :style="item.is_low ? 'color:var(--color-danger);font-weight:600;' : ''">
                  {{ fmtQty(item.stock_quantity) }} <span class="small muted">{{ item.unit }}</span>
                  <div v-if="item.is_low"><span class="badge badge-low">{{ t("stock.stock_bas") }}</span></div>
                </td>
                <td class="num small muted">{{ fmtQty(item.min_quantity) }}</td>
                <td class="num small">{{ item.unit_cost !== null ? money.fmt(item.unit_cost) : "—" }}</td>
                <td>
                  <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    <button
                      v-if="item.is_active"
                      class="btn btn-text btn-sm"
                      @click="openAdjust(item)"
                    >
                      {{ t("stock.ajuster") }}
                    </button>
                    <button class="btn btn-text btn-sm" @click="openCorrect(item)">
                      {{ t("stock.corriger") }}
                    </button>
                    <button class="btn btn-text btn-sm" @click="openHistory(item)">
                      {{ t("stock.historique") }}
                    </button>
                    <button class="btn btn-text btn-sm" @click="openEdit(item)">
                      {{ t("common.edit") }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- -------------------------------------------------- create/edit ---- -->
    <AppDialog
      :open="showForm"
      :title="editId === null ? t('stock.nouvel_article') : t('common.edit')"
      @close="showForm = false"
    >
      <div class="field" style="margin-bottom:12px;">
        <label for="st-name">{{ t("stock.article") }}</label>
        <input id="st-name" v-model="form.name" class="input">
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="st-cat">{{ t("stock.categorie") }}</label>
          <select id="st-cat" v-model="form.category" class="select">
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ t(`stock.cat_${c}`) }}</option>
          </select>
        </div>
        <div class="field" style="width:120px;margin-bottom:12px;">
          <label for="st-unit">{{ t("stock.unite") }}</label>
          <input id="st-unit" v-model="form.unit" class="input">
        </div>
      </div>
      <div style="display:flex;gap:12px;">
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="st-init">{{ editId === null ? t("stock.quantite_initiale") : t("stock.quantite") }}</label>
          <input
            id="st-init"
            v-model="form.initial_quantity"
            class="input"
            inputmode="decimal"
            :disabled="editId !== null"
          >
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="st-min">{{ t("stock.seuil") }}</label>
          <input id="st-min" v-model="form.min_quantity" class="input" inputmode="decimal">
        </div>
        <div class="field" style="flex:1;margin-bottom:12px;">
          <label for="st-cost">{{ t("stock.cout_unitaire") }} ({{ t("common.currency_da") }})</label>
          <input id="st-cost" v-model="form.unit_cost" class="input" inputmode="decimal">
        </div>
      </div>
      <div class="field" style="margin-bottom:12px;">
        <label for="st-notes">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
        <input id="st-notes" v-model="form.notes" class="input">
      </div>
      <label v-if="editId !== null" class="small" style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <input v-model="form.is_active" type="checkbox" style="width:18px;height:18px;">
        {{ t("stock.actif") }}
      </label>
      <div v-if="formError" class="alert alert-error">{{ t(formError) }}</div>
      <div class="dialog-actions">
        <button class="btn btn-secondary" @click="showForm = false">{{ t("common.cancel") }}</button>
        <button class="btn btn-primary" :disabled="saving || !form.name" @click="saveForm">
          {{ t("common.save") }}
        </button>
      </div>
    </AppDialog>

    <!-- ------------------------------------------------------- adjust ---- -->
    <AppDialog :open="adjustItem !== null" :title="t('stock.ajuster')" @close="adjustItem = null">
      <template v-if="adjustItem">
        <p class="small muted" style="margin-bottom:12px;">
          {{ adjustItem.name }} — {{ t("stock.quantite") }} : <strong>{{ fmtQty(adjustItem.stock_quantity) }} {{ adjustItem.unit }}</strong>
        </p>
        <div style="display:flex;gap:12px;">
          <div class="field" style="width:130px;margin-bottom:12px;">
            <label for="adj-delta">± {{ t("stock.quantite") }}</label>
            <input id="adj-delta" v-model="adjustForm.delta" class="input" inputmode="decimal" placeholder="+10 / -3">
          </div>
          <div class="field" style="flex:1;margin-bottom:12px;">
            <label for="adj-reason">{{ t("stock.raison") }}</label>
            <select id="adj-reason" v-model="adjustForm.reason" class="select">
              <option v-for="r in ADJUST_REASONS" :key="r" :value="r">{{ t(`movement.${r}`) }}</option>
            </select>
          </div>
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="adj-note">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
          <input id="adj-note" v-model="adjustForm.note" class="input">
        </div>
        <div v-if="adjustError" class="alert alert-error">{{ t(adjustError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="adjustItem = null">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="adjustSaving || !adjustForm.delta" @click="saveAdjust">
            {{ t("common.confirm") }}
          </button>
        </div>
      </template>
    </AppDialog>

    <!-- ------------------------------------------------------ correct ---- -->
    <AppDialog :open="correctItem !== null" :title="t('stock.corriger')" @close="correctItem = null">
      <template v-if="correctItem">
        <p class="small muted" style="margin-bottom:12px;">
          {{ correctItem.name }} — {{ t("stock.quantite") }} : <strong>{{ fmtQty(correctItem.stock_quantity) }} {{ correctItem.unit }}</strong>
        </p>
        <div class="field" style="margin-bottom:12px;">
          <label for="cor-qty">{{ t("stock.nouvelle_quantite") }}</label>
          <input id="cor-qty" v-model="correctForm.quantity" class="input" inputmode="decimal">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="cor-note">{{ t("common.notes") }} ({{ t("common.optional") }})</label>
          <input id="cor-note" v-model="correctForm.note" class="input">
        </div>
        <div v-if="correctError" class="alert alert-error">{{ t(correctError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="correctItem = null">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="correctSaving" @click="saveCorrect">
            {{ t("common.confirm") }}
          </button>
        </div>
      </template>
    </AppDialog>

    <!-- ------------------------------------------------------ history ---- -->
    <AppDialog
      :open="historyItem !== null"
      :title="historyItem ? `${t('stock.historique')} — ${historyItem.name}` : ''"
      wide
      @close="historyItem = null"
    >
      <div v-if="movementsLoading" style="padding:8px 0;" aria-hidden="true">
        <div v-for="i in skeletonRows(4)" :key="i" class="skeleton skeleton-row" />
      </div>
      <div v-else-if="!movements.length" class="empty-state">{{ t("common.none") }}</div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t("appointment.date") }}</th>
            <th class="num">±</th>
            <th>{{ t("stock.raison") }}</th>
            <th>{{ t("common.notes") }}</th>
            <th>{{ t("auth.username") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in movements" :key="m.id">
            <td class="small muted">{{ dates.fmtDateTime(m.created_at) }}</td>
            <td class="num" :class="Number(m.delta) >= 0 ? 'delta-pos' : 'delta-neg'" style="font-weight:600;">
              {{ Number(m.delta) >= 0 ? "+" : "" }}{{ fmtQty(m.delta) }}
            </td>
            <td class="small">{{ t(`movement.${m.reason}`) }}</td>
            <td class="small muted">{{ m.note || "—" }}</td>
            <td class="small muted">{{ m.created_by_name || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </AppDialog>

    <!-- -------------------------------------------------------- links ---- -->
    <AppDialog :open="showLinks" :title="t('stock.liens_treatments')" wide @close="showLinks = false">
      <h3 class="section-title" style="font-size:14px;margin-bottom:8px;">{{ t("stock.lien_ajouter") }}</h3>
      <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;">
        <div class="field" style="flex:1;min-width:180px;">
          <label for="lk-cat">{{ t("stock.traitement_catalogue") }}</label>
          <select id="lk-cat" v-model="linkForm.catalog_item_id" class="select">
            <option value="">—</option>
            <option v-for="i in catalog" :key="i.id" :value="String(i.id)">{{ i.name }}</option>
          </select>
        </div>
        <div class="field" style="flex:1;min-width:180px;">
          <label for="lk-item">{{ t("stock.article") }}</label>
          <select id="lk-item" v-model="linkForm.stock_item_id" class="select">
            <option value="">—</option>
            <option v-for="i in items.filter(x => x.is_active)" :key="i.id" :value="String(i.id)">
              {{ i.name }} ({{ fmtQty(i.stock_quantity) }} {{ i.unit }})
            </option>
          </select>
        </div>
        <div class="field" style="width:110px;">
          <label for="lk-qty">{{ t("stock.lien_quantite") }}</label>
          <input id="lk-qty" v-model="linkForm.quantity" class="input" inputmode="decimal">
        </div>
        <button
          class="btn btn-primary"
          :disabled="linkSaving || !linkForm.catalog_item_id || !linkForm.stock_item_id"
          style="margin-bottom:2px;"
          @click="saveLink"
        >
          {{ t("common.add") }}
        </button>
      </div>
      <div v-if="linkError" class="alert alert-error" style="margin-top:12px;">{{ t(linkError) }}</div>

      <h3 class="section-title" style="font-size:14px;margin:20px 0 8px;">{{ t("stock.liens_treatments") }}</h3>
      <div v-if="!links.length" class="empty-state" style="padding:16px 0;">{{ t("common.none") }}</div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t("stock.traitement_catalogue") }}</th>
            <th>{{ t("stock.article") }}</th>
            <th class="num">{{ t("stock.lien_quantite") }}</th>
            <th style="width:1%;" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in links" :key="l.id">
            <td>{{ catalogName(l.catalog_item_id) }}</td>
            <td>{{ l.stock_item_name }}</td>
            <td class="num">{{ fmtQty(l.quantity) }} <span class="small muted">{{ l.unit }}</span></td>
            <td>
              <button class="btn btn-text btn-sm" style="color:var(--color-danger);" @click="deleteLink(l)">
                {{ t("common.delete") }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </AppDialog>
  </div>
</template>
