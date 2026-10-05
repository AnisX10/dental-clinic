<script setup lang="ts">
/**
 * Accessible dialog wrapper: overlay click + Escape to close, focus trap,
 * body scroll lock, entrance animation. All clinic dialogs use this.
 */
const props = defineProps<{
  open: boolean
  title: string
  wide?: boolean
}>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const box = ref<HTMLElement | null>(null)

function onKeydown(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === "Escape") {
    e.stopPropagation()
    emit("close")
    return
  }
  if (e.key === "Tab" && box.value) {
    // Minimal focus trap: cycle among focusable elements inside the dialog.
    const focusables = box.value.querySelectorAll<HTMLElement>(
      'button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])',
    )
    if (!focusables.length) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last!.focus()
    }
    else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first!.focus()
    }
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener("keydown", onKeydown, true)
      document.body.classList.add("dialog-open")
      nextTick(() => {
        const target = box.value?.querySelector<HTMLElement>("input, select, textarea, button")
        target?.focus()
      })
    }
    else {
      document.removeEventListener("keydown", onKeydown, true)
      document.body.classList.remove("dialog-open")
    }
  },
)

onUnmounted(() => {
  document.removeEventListener("keydown", onKeydown, true)
  document.body.classList.remove("dialog-open")
})
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div v-if="open" class="overlay" @click.self="emit('close')">
        <div
          ref="box"
          class="dialog"
          :class="{ 'dialog-wide': wide }"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
        >
          <div class="dialog-head">
            <h2>{{ title }}</h2>
            <button class="dialog-x" :aria-label="t('common.close')" @click="emit('close')">✕</button>
          </div>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
