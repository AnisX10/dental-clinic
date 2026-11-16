<script setup lang="ts">
/**
 * Root: reactive <html lang/dir> so RTL survives re-renders (unhead owns the
 * html attributes; direct DOM writes get clobbered). The session is loaded by
 * the global route middleware, which also skips it while the licence is locked.
 */
const { lang, isRtl } = useI18n()

useHead({
  htmlAttrs: {
    lang: lang,
    dir: computed(() => (isRtl.value ? "rtl" : "ltr")),
  } as any,
})
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <ToastHost />
</template>
