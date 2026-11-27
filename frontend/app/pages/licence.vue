<script setup lang="ts">
/**
 * Licence screen — the page shown while the application is locked out.
 * DESIGN.md: calm, one primary action, no decorative noise.
 * The clinic staff pastes the licence key (one line, from the vendor) into
 * the box; no file import and no shell access is ever needed.
 */
definePageMeta({ layout: false })

const { t, lang, setLang } = useI18n()
const license = useLicense()

const pastedKey = ref("")
const installing = ref(false)
const errorKey = ref("")
const successKey = ref("")
const statusUnavailable = ref(false)

async function refreshStatus() {
  statusUnavailable.value = !(await license.fetchStatus(true))
}

if (!license.status.value) await refreshStatus()

async function onActivate() {
  if (installing.value || !pastedKey.value.trim()) return
  installing.value = true
  errorKey.value = ""
  successKey.value = ""
  try {
    await license.activateKey(pastedKey.value)
    successKey.value = "license.installed_ok"
    await navigateTo("/login", { replace: true })
  }
  catch (err: any) {
    errorKey.value = err?.messageKey ?? "license.error_rejected"
    await refreshStatus()
  }
  finally {
    installing.value = false
  }
}
</script>

<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;">
    <div class="card" style="width:100%;max-width:420px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
        <img src="~/assets/logo.svg" alt="HKN" style="height:44px;width:auto;">
        <div>
          <h1 style="font-size:20px;font-weight:650;">{{ t("license.locked_title") }}</h1>
          <p class="muted small">{{ t("common.app_name") }}</p>
        </div>
      </div>

      <p class="small" style="margin-bottom:16px;">{{ t("license.locked_hint") }}</p>

      <div style="margin-bottom:16px;">
        <div class="money-row">
          <span class="money-label">{{ t("license.activation_key") }}</span>
          <span class="small">{{ t("license.key_hint") }}</span>
        </div>
        <textarea
          v-model="pastedKey"
          class="input-area"
          rows="3"
          style="margin-top:8px;width:100%;resize:none;white-space:nowrap;"
          spellcheck="false"
          autocomplete="off"
          :placeholder="t('license.key_placeholder')"
          @keydown.enter.exact.prevent="onActivate"
        />
        <button
          type="button"
          class="btn btn-primary"
          style="width:100%;margin-top:8px;"
          :disabled="installing || !pastedKey.trim()"
          @click="onActivate"
        >
          {{ installing ? t("license.installing") : t("license.activate_button") }}
        </button>
      </div>

      <div v-if="statusUnavailable" class="alert alert-error" role="alert" style="margin-bottom:12px;">
        {{ t("license.status_unavailable") }}
        <button type="button" class="btn btn-secondary" style="margin-top:8px;" @click="refreshStatus">
          {{ t("license.retry_status") }}
        </button>
      </div>

      <div v-if="license.status.value" style="margin-bottom:16px;">
        <div class="money-row">
          <span class="money-label">{{ t("license.installation_id") }}</span>
          <span
            class="small"
            style="font-family:monospace;font-variant-numeric:tabular-nums;user-select:all;"
          >{{ license.status.value.installation_id }}</span>
        </div>
        <div class="money-row">
          <span class="money-label">{{ t("common.statut") }}</span>
          <span class="small">{{ t(`license.reason_${license.status.value.reason}`) }}</span>
        </div>
      </div>

      <div v-if="errorKey" class="alert alert-error" role="alert">{{ t(errorKey) }}</div>
      <div v-if="successKey" class="alert" role="status">{{ t(successKey) }}</div>

      <div style="margin-top:20px;display:flex;justify-content:center;">
        <select
          class="select"
          style="height:32px;width:auto;font-size:12px;"
          :value="lang"
          aria-label="Langue"
          @change="setLang(($event.target as HTMLSelectElement).value as 'fr' | 'ar')"
        >
          <option value="fr">Français</option>
          <option value="ar">العربية</option>
        </select>
      </div>
    </div>
  </div>
</template>
