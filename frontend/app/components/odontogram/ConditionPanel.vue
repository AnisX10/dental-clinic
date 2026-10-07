<script setup lang="ts">
/**
 * Selected-tooth panel: pick a condition, choose a surface for carie/obturation,
 * clear individual surface marks, reset the tooth. Emits `apply` with the exact
 * payload to PUT; the parent performs the API call and refreshes.
 */
import { SURFACES, SURFACE_CONDITIONS } from "~/utils/toothShapes"
import type { ToothCondition } from "~/utils/toothShapes"

const props = withDefaults(defineProps<{
  tooth: number
  conditions: ToothCondition[]
  treatments?: { name: string }[]
  busy?: boolean
}>(), {
  treatments: () => [],
  busy: false,
})

const emit = defineEmits<{
  apply: [payload: { tooth: number, condition: string, surface: string }]
  close: []
}>()

const { t } = useI18n()

const pendingSurface = ref("")

watch(() => props.tooth, () => {
  pendingSurface.value = ""
})

const whole = computed(() => props.conditions.find(c => c.tooth === props.tooth && !c.surface)?.condition ?? "")
const marks = computed(() => props.conditions.filter(c => c.tooth === props.tooth && !!c.surface))

function markFor(surface: string): string {
  return marks.value.find(m => m.surface === surface)?.condition ?? ""
}

function apply(condition: string, surface = "") {
  if (props.busy) return
  emit("apply", { tooth: props.tooth, condition, surface })
}

function pickSurfaceCondition(condition: string) {
  pendingSurface.value = pendingSurface.value === condition ? "" : condition
}

function pickSurface(surface: string) {
  if (!pendingSurface.value) return
  const payload = { tooth: props.tooth, condition: pendingSurface.value, surface }
  pendingSurface.value = ""
  emit("apply", payload)
}

const WHOLE_BUTTONS = ["a_traiter", "couronne", "bridge", "absent"] as const
</script>

<template>
  <div class="card cond-panel">
    <div class="cond-head">
      <h2 class="section-title">{{ t("odontogram.dent") }} {{ tooth }}</h2>
      <button type="button" class="btn btn-text btn-sm" @click="emit('close')">✕</button>
    </div>

    <div v-if="whole || marks.length" class="cond-current">
      <span v-if="whole" class="badge badge-cond">{{ t(`odontogram.cond_${whole}`) }}</span>
      <button
        v-for="m in marks"
        :key="m.surface"
        type="button"
        class="badge badge-cond badge-click"
        :disabled="busy"
        :title="t('odontogram.remove_mark')"
        @click="apply('sain', m.surface)"
      >
        {{ t(`odontogram.cond_${m.condition}`) }} · {{ t(`odontogram.surf_${m.surface}`) }} ✕
      </button>
    </div>

    <div class="cond-grid">
      <button
        v-for="c in WHOLE_BUTTONS"
        :key="c"
        type="button"
        class="btn btn-secondary btn-sm cond-btn"
        :class="{ active: whole === c }"
        :disabled="busy"
        @click="apply(c)"
      >
        <span class="swatch" :class="`sw-${c}`" />
        {{ t(`odontogram.cond_${c}`) }}
      </button>
      <button
        v-for="c in SURFACE_CONDITIONS"
        :key="c"
        type="button"
        class="btn btn-secondary btn-sm cond-btn"
        :class="{ active: pendingSurface === c }"
        :disabled="busy"
        @click="pickSurfaceCondition(c)"
      >
        <span class="swatch" :class="`sw-${c}`" />
        {{ t(`odontogram.cond_${c}`) }}
      </button>
    </div>

    <div v-if="pendingSurface" class="cond-surfaces">
      <div class="small muted" style="margin-bottom:6px;">
        {{ t("odontogram.choisir_surface", { condition: t(`odontogram.cond_${pendingSurface}`) }) }}
      </div>
      <div class="surf-grid">
        <button
          v-for="s in SURFACES"
          :key="s"
          type="button"
          class="btn btn-secondary btn-sm surf-btn"
          :class="[`surf-${s}`, { active: markFor(s) === pendingSurface }]"
          :disabled="busy"
          @click="pickSurface(s)"
        >
          {{ t(`odontogram.surf_${s}`) }}
          <span v-if="markFor(s)" class="small muted">({{ t(`odontogram.cond_${markFor(s)}`) }})</span>
        </button>
      </div>
    </div>

    <div v-if="treatments.length" class="small muted" style="margin-top:12px;">
      <strong>{{ t("odontogram.traitements_lies") }}</strong>
      {{ treatments.map(x => x.name).join(", ") }}
    </div>

    <div class="dialog-actions" style="margin-top:16px;">
      <button type="button" class="btn btn-secondary btn-sm" :disabled="busy || (!whole && !marks.length)" @click="apply('sain')">
        {{ t("odontogram.reset") }}
      </button>
    </div>
  </div>
</template>
