<script setup lang="ts">
interface SettingsLike {
  clinic_name?: string
  doctor_name?: string
  header_note?: string
  address?: string
  phone?: string
}
defineProps<{ settings: SettingsLike | null | undefined }>()
</script>

<template>
  <div class="pl-letter">
    <div class="pl-header">
      <div class="pl-brand">
        <img src="/ordonnance-mark.svg" alt="" class="pl-logo" aria-hidden="true">
        <div class="pl-brandtext">
          <span class="pl-brand-hkn">HKN</span>
          <span class="pl-brand-sub">Dental Care</span>
        </div>
      </div>
      <div class="pl-doctor">
        <div class="pl-doctor-name">{{ settings?.doctor_name }}</div>
        <div v-if="settings?.header_note" class="pl-doctor-sub">{{ settings.header_note }}</div>
      </div>
    </div>
    <div class="pl-clinic-info">
      <div v-if="settings?.address" class="pl-contact">
        <svg class="pl-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 21.2c4.2-4.3 7-7.6 7-11a7 7 0 1 0-14 0c0 3.4 2.8 6.7 7 11Z" />
          <circle cx="12" cy="10" r="2.6" />
        </svg>
        <span>{{ settings.address }}</span>
      </div>
      <div v-if="settings?.phone" class="pl-contact">
        <svg class="pl-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7 12.8 12.8 0 0 0 .7 2.8 2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4 12.8 12.8 0 0 0 2.8.7 2 2 0 0 1 1.7 2Z" />
        </svg>
        <span>{{ settings.phone }}</span>
      </div>
      <div v-if="settings?.clinic_name" class="pl-clinic-name">{{ settings.clinic_name }}</div>
    </div>
    <hr class="pl-rule">
  </div>
</template>

<style scoped>
.pl-letter {
  color: var(--color-ink);
}

.pl-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.pl-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pl-logo {
  width: 64px;
  height: 56px;
  display: block;
  color: #0040dc;
}

.pl-brandtext {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: 0.4px;
  color: #0040dc;
}

.pl-brand-hkn {
  font-size: 18px;
}

.pl-brand-sub {
  font-size: 12px;
  font-weight: 700;
}

.pl-doctor {
  text-align: start;
  padding-top: 2px;
}

.pl-doctor-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.2px;
}

.pl-doctor-sub {
  margin-top: 4px;
  font-size: 13px;
}

.pl-clinic-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  margin-top: 10px;
}

.pl-contact {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pl-icon {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.pl-clinic-name {
  margin-top: 2px;
}

.pl-rule {
  border: none;
  border-top: 1px solid #0040dc;
  margin: 14px 0 20px;
}
</style>
