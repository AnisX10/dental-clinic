<script setup lang="ts">
/**
 * Login screen — the only page outside the app shell.
 * DESIGN.md: calm, one primary action, errors in plain language.
 */
definePageMeta({ layout: false })

const { t } = useI18n()
const auth = useAuth()
const { lang, setLang } = useI18n()

const username = ref("")
const password = ref("")
const submitting = ref(false)
const errorKey = ref("")

async function submit() {
  if (submitting.value) return
  submitting.value = true
  errorKey.value = ""
  try {
    await auth.login(username.value.trim(), password.value)
    await navigateTo("/")
  }
  catch (e: any) {
    errorKey.value = e?.messageKey ?? "errors.generic"
  }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;">
    <div class="card" style="width:100%;max-width:380px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;">
        <img
          src="~/assets/logo.svg"
          alt="HKN"
          style="height:44px;width:auto;"
        >
        <div>
          <h1 style="font-size:20px;font-weight:650;">{{ t("common.app_name") }}</h1>
          <p class="muted small">{{ t("auth.login_title") }}</p>
        </div>
      </div>

      <form style="display:contents;" @submit.prevent="submit">
        <div class="field" style="margin-bottom:12px;">
          <label for="username">{{ t("auth.username") }}</label>
          <input
            id="username"
            v-model="username"
            class="input"
            name="username"
            autocomplete="username"
            autofocus
          >
        </div>
        <div class="field" style="margin-bottom:20px;">
          <label for="password">{{ t("auth.password") }}</label>
          <input
            id="password"
            v-model="password"
            class="input"
            name="password"
            type="password"
            autocomplete="current-password"
          >
        </div>

        <div v-if="errorKey" class="alert alert-error" role="alert">{{ t(errorKey) }}</div>

        <button
          type="submit"
          class="btn btn-primary"
          style="width:100%;"
          :disabled="submitting"
        >
          {{ submitting ? t("auth.logging_in") : t("auth.login") }}
        </button>
      </form>

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
