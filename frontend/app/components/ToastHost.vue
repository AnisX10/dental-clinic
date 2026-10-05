<script setup lang="ts">
/**
 * Toast region: fixed, top-end, RTL-aware (inset-inline-end), aria-live.
 * Rendered once from app.vue.
 */
const { t } = useI18n()
const toast = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="toast-region" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="toast">
        <div
          v-for="item in toast.toasts.value"
          :key="item.id"
          class="toast"
          :class="item.kind === 'success' ? 'toast-success' : 'toast-error'"
          role="status"
        >
          <span class="toast-dot" aria-hidden="true" />
          <span class="toast-msg">{{ t(item.messageKey) }}</span>
          <button class="toast-close" :aria-label="t('common.close')" @click="toast.dismiss(item.id)">
            ✕
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
