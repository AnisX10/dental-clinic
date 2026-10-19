<script setup lang="ts">
/**
 * Paiements: day view (cash-only) — revenue summary + chronological payments
 * for the selected date (DESIGN.md §10, calm ledger style).
 */
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const money = useMoney()

interface PaymentRow {
  id: number
  amount: string
  note: string
  created_at: string
  created_by_name: string
  patient: { id: number, nom: string, prenom: string, code: string } | null
}

const day = ref(dates.todayIso())
const payments = ref<PaymentRow[]>([])
const summary = ref({ recettes_du_jour: "0.00", nombre_paiements: 0 })
const loading = ref(true)
const errorMsg = ref("")

function shiftDay(delta: number) {
  const d = new Date(`${day.value}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + delta)
  day.value = d.toISOString().slice(0, 10)
}

async function load() {
  loading.value = true
  errorMsg.value = ""
  try {
    const data = await api.get<{ summary: typeof summary.value, payments: PaymentRow[] }>(`/payments/day/${day.value}`)
    payments.value = data.payments
    summary.value = data.summary
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
watch(day, load)
await load()
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h1 class="page-title">{{ t("payments.day_title") }} {{ dates.weekdayLong(day) }}</h1>
        <p class="page-subtitle" style="text-transform:capitalize;">{{ dates.fmtDate(day) }}</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour précédent" @click="shiftDay(-1)">‹</button>
        <input v-model="day" type="date" class="input" style="width:170px;height:36px;">
        <button class="btn btn-secondary btn-sm" aria-label="Jour suivant" @click="shiftDay(1)">›</button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>

    <div class="day-grid">
      <div class="card">
        <h2 class="section-title" style="margin-bottom:12px;">{{ t("payments.journalier") }}</h2>
        <div class="money-row">
          <span class="money-label">{{ t("today.recettes_du_jour") }}</span>
          <span class="money-value">{{ money.fmt(summary.recettes_du_jour) }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("today.nombre_paiements") }}</span>
          <span class="money-value">{{ summary.nombre_paiements }}</span>
        </div>
      </div>

      <div class="card" style="padding:0;overflow-x:auto;">
        <div v-if="loading" style="padding:8px 16px 16px;" aria-hidden="true">
          <div v-for="i in 5" :key="i" class="skeleton skeleton-row" />
        </div>
        <div v-else-if="!payments.length" class="empty-state">
          <AppIcon name="paiements" size="32" class="empty-icon" style="margin-bottom:8px;opacity:0.6;" />
          <div>{{ t("payments.aucun") }}</div>
        </div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>{{ t("appointment.time") }}</th>
              <th>{{ t("appointment.patient") }}</th>
              <th style="text-align:end;">{{ t("payments.montant") }}</th>
              <th>{{ t("common.notes") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in payments" :key="p.id">
              <td class="small muted" style="font-variant-numeric:tabular-nums;">
                {{ dates.fmtTime(p.created_at) }}
              </td>
              <td>
                <NuxtLink v-if="p.patient" :to="`/patients/${p.patient.id}`" style="font-weight:600;">
                  {{ p.patient.nom }} {{ p.patient.prenom }}
                </NuxtLink>
              </td>
              <td style="text-align:end;font-variant-numeric:tabular-nums;">
                {{ money.fmt(p.amount) }}
              </td>
              <td class="small muted">{{ p.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.day-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 720px) {
  .day-grid {
    grid-template-columns: 1fr;
  }
}
</style>
