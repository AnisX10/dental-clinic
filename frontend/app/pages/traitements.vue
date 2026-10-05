<script setup lang="ts">
/**
 * Traitements (catalog): grouped by category, add/edit owner-only per spec
 * (reception can view; owner manages catalog and prices).
 */
const { t } = useI18n()
const api = useApi()
const money = useMoney()
const auth = useAuth()
const toast = useToast()

const CATEGORIES = ["Consultation", "Soins", "Chirurgie", "Prothèse", "Orthodontie", "Parodontologie", "Autre"]

interface CatalogItem { id: number, name: string, category: string, default_price: string, is_active: boolean }

const items = ref<CatalogItem[]>([])
const loading = ref(true)
const errorMsg = ref("")

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ items: CatalogItem[] }>("/clinical/catalog")
    items.value = data.items
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await load()

const grouped = computed(() =>
  CATEGORIES.map(cat => ({ category: cat, rows: items.value.filter(i => i.category === cat) }))
    .filter(g => g.rows.length),
)

// ---- Create / edit dialog --------------------------------------------------
const showForm = ref(false)
const editId = ref<number | null>(null)
const form = ref({ name: "", category: CATEGORIES[0], default_price: "" })
const saving = ref(false)
const formError = ref("")

function openCreate() {
  editId.value = null
  form.value = { name: "", category: CATEGORIES[0], default_price: "" }
  formError.value = ""
  showForm.value = true
}

function openEdit(item: CatalogItem) {
  editId.value = item.id
  form.value = { name: item.name, category: item.category, default_price: item.default_price }
  formError.value = ""
  showForm.value = true
}

async function save() {
  saving.value = true
  formError.value = ""
  try {
    if (editId.value === null) {
      await api.post("/clinical/catalog", form.value)
      toast.success("common.save")
    }
    else {
      await api.put(`/clinical/catalog/${editId.value}`, form.value)
      toast.success("common.save")
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
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("nav.traitements") }}</h1>
        <p class="page-subtitle">{{ items.length }}</p>
      </div>
      <button v-if="auth.user.value?.is_owner" class="btn btn-primary" @click="openCreate">
        {{ t("common.add") }}
      </button>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div v-if="loading" class="card" style="padding:16px;" aria-hidden="true">
      <div v-for="i in 6" :key="i" class="skeleton skeleton-line" :class="i % 2 ? 'w-60' : 'w-40'" />
    </div>
    <div v-else-if="!items.length" class="card empty-state">
      <span class="empty-icon">✚</span>
      {{ t("treatments.aucun") }}
    </div>

    <div v-for="g in grouped" v-else :key="g.category" class="card" style="padding:0;margin-bottom:16px;">
      <div class="nav-group-label" style="padding:12px 16px 0;">{{ g.category }}</div>
      <table class="table">
        <tbody>
          <tr v-for="i in g.rows" :key="i.id">
            <td :style="i.is_active ? '' : 'color:var(--color-text-muted);text-decoration:line-through;'">
              {{ i.name }}
            </td>
            <td style="text-align:end;font-variant-numeric:tabular-nums;width:140px;">
              {{ money.fmt(i.default_price) }}
            </td>
            <td v-if="auth.user.value?.is_owner" style="width:1%;">
              <button class="btn btn-text btn-sm" @click="openEdit(i)">{{ t("common.edit") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppDialog
      :open="showForm"
      :title="editId === null ? t('common.add') : t('common.edit')"
      @close="showForm = false"
    >
        <div class="field" style="margin-bottom:12px;">
          <label for="cat-name">{{ t("treatments.title") }}</label>
          <input id="cat-name" v-model="form.name" class="input">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="cat-cat">{{ t("treatments.categorie") }}</label>
          <select id="cat-cat" v-model="form.category" class="select">
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="cat-price">{{ t("treatments.prix") }} ({{ t("common.currency_da") }})</label>
          <input id="cat-price" v-model="form.default_price" class="input" inputmode="decimal">
        </div>
        <div v-if="formError" class="alert alert-error">{{ t(formError) }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showForm = false">{{ t("common.cancel") }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">{{ t("common.save") }}</button>
        </div>
    </AppDialog>
  </div>
</template>
