<script setup lang="ts">
const { t } = useI18n()
const open = usePrintHintOpen()

function openDialogNow() {
  ackPrintHint()
  open.value = false
  window.print()
}

function dismissForever() {
  ackPrintHint()
  open.value = false
}
</script>

<template>
  <AppDialog :open="open" :title="t('print_hint.title')" @close="open = false">
    <ul class="ph-list">
      <li>{{ t("print_hint.margins") }}</li>
      <li>{{ t("print_hint.background") }}</li>
      <li>{{ t("print_hint.scale") }}</li>
    </ul>
    <p class="small muted" style="margin-top:10px;">{{ t("print_hint.note") }}</p>
    <div class="dialog-actions" style="margin-top:16px;">
      <button class="btn btn-text" @click="dismissForever">
        {{ t("print_hint.never") }}
      </button>
      <button class="btn btn-primary" @click="openDialogNow">
        {{ t("print_hint.ok") }}
      </button>
    </div>
  </AppDialog>
</template>

<style scoped>
.ph-list {
  margin: 0;
  padding-inline-start: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}
</style>
