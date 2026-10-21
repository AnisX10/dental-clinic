<script setup lang="ts">
/**
 * Paramètres: clinic identity, document header/footer, backup hour — all
 * owner-only writes (backend enforces too). Manual backup button + last
 * backup status. Users list for reference. License card (status + install).
 */
import type { LicenseStatus } from "~/composables/useLicense"
const { t } = useI18n()
const api = useApi()
const dates = useDates()
const auth = useAuth()
const toast = useToast()

interface Settings {
  clinic_name: string, doctor_name: string, address: string, phone: string,
  header_note: string, footer_note: string,
  backup_hour: number, backup_keep_daily: number, backup_keep_manual: number,
  version: string,
}
interface BackupStatus {
  last_success: { at: string, kind: string, size_bytes: number } | null
}

const settings = ref<Settings | null>(null)
const backup = ref<BackupStatus | null>(null)
const users = ref<{ id: number, username: string, full_name: string, role: string, is_owner: boolean, is_active: boolean }[]>([])
const license = ref<LicenseStatus | null>(null)
const licenseInput = ref<HTMLInputElement | null>(null)
const loading = ref(true)
const errorMsg = ref("")
const running = ref(false)
const saving = ref(false)
const installing = ref(false)
const canEdit = computed(() => auth.user.value?.is_owner ?? false)
const licenseApi = useLicense()

async function loadLicense() {
  try {
    license.value = await licenseApi.fetchStatus(true)
  }
  catch {
    license.value = null
  }
}

async function installLicense(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file || installing.value) return
  installing.value = true
  errorMsg.value = ""
  try {
    await licenseApi.installContent(await file.text())
    toast.success("license.installed_ok")
    await loadLicense()
  }
  catch (err: any) {
    errorMsg.value = err?.messageKey ?? "license.error_rejected"
  }
  finally {
    installing.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const [s, b, u] = await Promise.all([
      api.get<{ settings: Settings }>("/settings"),
      api.get<BackupStatus>("/backup/status"),
      api.get<{ users: typeof users.value }>("/auth/users"),
    ])
    settings.value = s.settings
    backup.value = b
    users.value = u.users
    await loadLicense()
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    loading.value = false
  }
}
await load()

async function save() {
  if (!settings.value) return
  saving.value = true
  errorMsg.value = ""
  try {
    await api.put("/settings", {
      clinic_name: settings.value.clinic_name,
      doctor_name: settings.value.doctor_name,
      address: settings.value.address,
      phone: settings.value.phone,
      header_note: settings.value.header_note,
      footer_note: settings.value.footer_note,
      backup_hour: Number(settings.value.backup_hour),
    })
    toast.success("settings.saved")
    await load()
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    saving.value = false
  }
}

async function runBackup() {
  running.value = true
  errorMsg.value = ""
  try {
    await api.post("/backup/run")
    toast.success("settings.backup_done")
    await load()
  }
  catch (e: any) {
    errorMsg.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    running.value = false
  }
}
</script>

<template>
  <div>
    <div class="toolbar">
      <h1 class="page-title">{{ t("settings.title") }}</h1>
    </div>

    <div v-if="errorMsg" class="alert alert-error">{{ t(errorMsg) }}</div>
    <div v-if="loading" style="max-width:640px;" aria-hidden="true">
      <div class="skeleton skeleton-line w-40" />
      <div class="skeleton skeleton-line w-80" />
      <div class="skeleton skeleton-line w-60" />
      <div class="skeleton skeleton-line w-80" />
      <div class="skeleton skeleton-line w-40" />
    </div>

    <template v-else-if="settings">
      <p v-if="!canEdit" class="alert">{{ t("settings.owner_only_hint") }}</p>

      <div class="card" style="max-width:640px;">
        <h2 class="section-title" style="margin-bottom:16px;">{{ t("settings.clinic_section") }}</h2>
        <div class="field" style="margin-bottom:12px;">
          <label for="st-name">{{ t("settings.nom_clinique") }}</label>
          <input id="st-name" v-model="settings.clinic_name" class="input" :disabled="!canEdit">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="st-doctor">{{ t("settings.nom_medecin") }}</label>
          <input id="st-doctor" v-model="settings.doctor_name" class="input" :disabled="!canEdit">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="st-address">{{ t("patients.adresse") }}</label>
          <input id="st-address" v-model="settings.address" class="input" :disabled="!canEdit">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="st-phone">{{ t("patients.telephone") }}</label>
          <input id="st-phone" v-model="settings.phone" class="input" :disabled="!canEdit">
        </div>

        <h2 class="section-title" style="margin:24px 0 16px;">{{ t("settings.documents_section") }}</h2>
        <div class="field" style="margin-bottom:12px;">
          <label for="st-header">{{ t("settings.entete") }}</label>
          <input id="st-header" v-model="settings.header_note" class="input" :disabled="!canEdit">
        </div>
        <div class="field" style="margin-bottom:16px;">
          <label for="st-footer">{{ t("settings.pied") }}</label>
          <input id="st-footer" v-model="settings.footer_note" class="input" :disabled="!canEdit">
        </div>

        <h2 class="section-title" style="margin:24px 0 16px;">{{ t("settings.backup_section") }}</h2>
        <div class="field" style="margin-bottom:16px;max-width:200px;">
          <label for="st-hour">{{ t("settings.backup_hour") }} (0–23)</label>
          <input
            id="st-hour"
            v-model.number="settings.backup_hour"
            type="number"
            min="0"
            max="23"
            class="input"
            :disabled="!canEdit"
          >
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("settings.backup_last") }}</span>
          <span class="small">
            {{ backup?.last_success ? dates.fmtDateTime(backup.last_success.at) : t("settings.backup_none") }}
          </span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("settings.version") }}</span>
          <span class="small" style="font-variant-numeric:tabular-nums;">{{ settings.version }}</span>
        </div>

        <h2 class="section-title" style="margin:24px 0 16px;">{{ t("license.card_title") }}</h2>
        <div v-if="license" style="display:contents;">
          <div class="money-row">
            <span class="money-label">{{ t("common.statut") }}</span>
            <span class="small">{{ license.active ? t("license.status_ok") : t("license.status_missing") }}</span>
          </div>
          <template v-if="license.active">
            <div class="money-row">
              <span class="money-label">{{ t("license.clinic") }}</span>
              <span class="small">{{ license.clinic }}</span>
            </div>
            <div class="money-row">
              <span class="money-label">{{ t("license.dentist") }}</span>
              <span class="small">{{ license.dentist }}</span>
            </div>
            <div class="money-row">
              <span class="money-label">{{ t("license.issued") }}</span>
              <span class="small">{{ license.issued_at ? dates.fmtDate(license.issued_at) : "" }}</span>
            </div>
          </template>
          <div class="money-row">
            <span class="money-label">{{ t("license.installation_id") }}</span>
            <span class="small" style="font-family:monospace;font-variant-numeric:tabular-nums;user-select:all;">{{ license.installation_id }}</span>
          </div>
          <div v-if="canEdit" class="money-row">
            <span class="money-label">{{ t("license.install_button") }}</span>
            <button class="btn btn-secondary" :disabled="installing" @click="licenseInput?.click()">
              {{ installing ? t("license.installing") : t("license.install_button") }}
            </button>
          </div>
          <input ref="licenseInput" type="file" accept=".lic,application/json,text/plain" style="display:none;" @change="installLicense">
        </div>

        <div v-if="canEdit" style="display:flex;justify-content:flex-end;gap:12px;margin-top:24px;">
          <button class="btn btn-secondary" :disabled="running" @click="runBackup">
            {{ running ? t("settings.backup_running") : t("settings.backup_run") }}
          </button>
          <button class="btn btn-primary" :disabled="saving" @click="save">{{ t("common.save") }}</button>
        </div>
      </div>

      <div class="card" style="max-width:640px;">
        <h2 class="section-title" style="margin-bottom:12px;">{{ t("settings.users_section") }}</h2>
        <table class="table">
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td style="font-weight:600;">{{ u.full_name }}</td>
              <td class="muted small">@{{ u.username }}</td>
              <td>{{ u.is_owner ? "Responsable" : (u.role === "dentiste" ? "Dentiste" : "Réception") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
