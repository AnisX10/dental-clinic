<script setup lang="ts">
defineProps<{ date?: string, dateCaption?: string, signs?: string[] }>()
</script>

<template>
  <div class="plf">
    <div v-if="dateCaption !== undefined" class="plf-slot">
      <div v-if="date" class="plf-date">{{ date }}</div>
      <hr class="plf-rule">
      <div class="plf-caption">{{ dateCaption }}</div>
    </div>
    <div v-for="s in signs ?? []" :key="s" class="plf-slot plf-end">
      <hr class="plf-rule">
      <div class="plf-caption">{{ s }}</div>
    </div>
  </div>
</template>

<style scoped>
.plf {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-top: 44px;
}

.plf-slot {
  width: 180px;
  flex: 0 0 auto;
}

.plf-end {
  text-align: end;
}

.plf-end .plf-rule {
  margin-inline-start: auto;
}

.plf-date {
  margin-bottom: 6px;
  font-size: 12px;
}

.plf-rule {
  width: 80px;
  border: none;
  border-top: 0.7px solid #0040dc;
  margin: 0 0 6px;
}

.plf-caption {
  font-size: 12px;
  letter-spacing: 0.3px;
  color: #0040dc;
  text-transform: uppercase;
}
</style>
