<script setup lang="ts">
/**
 * Root: auth bootstrap + reactive <html lang/dir> so RTL survives re-renders
 * (unhead owns the html attributes; direct DOM writes get clobbered).
 */
const auth = useAuth()
const { lang, isRtl } = useI18n()

useHead({
  htmlAttrs: {
    lang: lang,
    dir: computed(() => (isRtl.value ? "rtl" : "ltr")),
  } as any,
})

onMounted(() => {
  auth.fetchMe()
})
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <ToastHost />
</template>
