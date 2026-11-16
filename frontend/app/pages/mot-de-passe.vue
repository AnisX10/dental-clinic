<script setup lang="ts">
/**
 * Change own password. Mandatory (and the only reachable screen) for accounts
 * created with a bootstrap password; also reachable voluntarily from the
 * user badge in the app shell.
 */
definePageMeta({ layout: false })

const { t } = useI18n()
const auth = useAuth()
const toast = useToast()

const forced = computed(() => !!auth.user.value?.must_change_password)
const current = ref("")
const next = ref("")
const confirm = ref("")
const submitting = ref(false)
const errorKey = ref("")

async function submit() {
  if (submitting.value) return
  errorKey.value = ""
  if (next.value !== confirm.value) {
    errorKey.value = "auth.password_mismatch"
    return
  }
  submitting.value = true
  try {
    await auth.changePassword(current.value, next.value)
    toast.success("auth.password_changed")
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
    <div class="card" style="width:100%;max-width:400px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
        <img src="~/assets/logo.svg" alt="Dentilo" style="height:36px;width:auto;">
        <h1 style="font-size:20px;font-weight:650;">{{ t("auth.change_password") }}</h1>
      </div>

      <div v-if="forced" class="alert" role="status" style="margin-bottom:16px;">
        {{ t("auth.change_password_forced") }}
      </div>

      <form style="display:contents;" @submit.prevent="submit">
        <div class="field" style="margin-bottom:12px;">
          <label for="current-password">{{ t("auth.current_password") }}</label>
          <input
            id="current-password"
            v-model="current"
            class="input"
            type="password"
            autocomplete="current-password"
            required
            autofocus
          >
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label for="new-password">{{ t("auth.new_password") }}</label>
          <input
            id="new-password"
            v-model="next"
            class="input"
            type="password"
            autocomplete="new-password"
            minlength="10"
            required
            aria-describedby="password-rules"
          >
          <p id="password-rules" class="muted small" style="margin-top:4px;">{{ t("auth.password_rules") }}</p>
        </div>
        <div class="field" style="margin-bottom:20px;">
          <label for="confirm-password">{{ t("auth.confirm_password") }}</label>
          <input
            id="confirm-password"
            v-model="confirm"
            class="input"
            type="password"
            autocomplete="new-password"
            required
          >
        </div>

        <div v-if="errorKey" class="alert alert-error" role="alert">{{ t(errorKey) }}</div>

        <button type="submit" class="btn btn-primary" style="width:100%;" :disabled="submitting">
          {{ t("auth.change_password") }}
        </button>
      </form>

      <div style="margin-top:16px;display:flex;justify-content:center;gap:16px;">
        <NuxtLink v-if="!forced" to="/" class="small">{{ t("common.back") }}</NuxtLink>
        <button v-else type="button" class="btn btn-text btn-sm" @click="auth.logout()">
          {{ t("auth.logout") }}
        </button>
      </div>
    </div>
  </div>
</template>
