<script setup lang="ts">
/**
 * Anatomical odontogram chart (DentalPin-style): two arches of hand-drawn
 * SVG teeth with occlusal views, FDI numbers, surface wedges, hatch overlays
 * for crowns/bridges and ghosted missing teeth.
 */
import {
  ANATOMY,
  DECIDUOUS,
  OCCLUSAL,
  PERMANENT,
  SURFACE_WEDGE,
  isLower,
  mirrorHorizontal,
  mirrorVertical,
  toothType,
} from "~/utils/toothShapes"
import type { ToothCondition } from "~/utils/toothShapes"

const props = withDefaults(defineProps<{
  conditions: ToothCondition[]
  treatments?: Record<number, { name: string }[]>
  selected?: number | null
  dentition?: "permanente" | "temporaire"
}>(), {
  treatments: () => ({}),
  selected: null,
  dentition: "permanente",
})

const emit = defineEmits<{ select: [tooth: number] }>()

const { t } = useI18n()

// Layout constants (kept in sync with the .odonto-* CSS).
const STRIDE = 62
const ROW_H = 158
const BAR_Y = 64

const uid = Math.random().toString(36).slice(2, 8)
const hatchId = `odont-hatch-${uid}`
const hatchRef = `url(#${hatchId})`

const arches = computed(() => (props.dentition === "temporaire" ? DECIDUOUS : PERMANENT))

const rows = computed(() => [
  { key: "upper", label: t("odontogram.arcade_sup"), teeth: arches.value.upper },
  { key: "lower", label: t("odontogram.arcade_inf"), teeth: arches.value.lower },
])

const wholeByTooth = computed(() => {
  const map = new Map<number, string>()
  for (const c of props.conditions) {
    if (!c.surface) map.set(c.tooth, c.condition)
  }
  return map
})

const surfacesByTooth = computed(() => {
  const map = new Map<number, { surface: string, condition: string }[]>()
  for (const c of props.conditions) {
    if (c.surface) {
      const list = map.get(c.tooth) ?? []
      list.push({ surface: c.surface, condition: c.condition })
      map.set(c.tooth, list)
    }
  }
  return map
})

function whole(tooth: number): string {
  return wholeByTooth.value.get(tooth) ?? ""
}

function marks(tooth: number) {
  return surfacesByTooth.value.get(tooth) ?? []
}

function cellClass(tooth: number): Record<string, boolean> {
  const w = whole(tooth)
  return {
    sel: props.selected === tooth,
    todo: w === "a_traiter" || w === "carie",
    absent: w === "absent",
  }
}

function wedgesVisible(tooth: number): boolean {
  const w = whole(tooth)
  return w !== "absent"
}

function wedgeTransform(tooth: number): string {
  const parts: string[] = []
  if (mirrorHorizontal(tooth)) parts.push("translate(40 0) scale(-1 1)")
  if (mirrorVertical(tooth)) parts.push("translate(0 40) scale(1 -1)")
  return parts.join(" ")
}

function rowWidth(row: number[]): number {
  return row.length * STRIDE - 4
}

function bridgeBars(row: number[]): { x: number, w: number }[] {
  const bars: { x: number, w: number }[] = []
  let start = -1
  for (let i = 0; i <= row.length; i++) {
    const isBridge = i < row.length && whole(row[i]!) === "bridge"
    if (isBridge && start === -1) start = i
    if (!isBridge && start !== -1) {
      if (i - start >= 2) bars.push({ x: start * STRIDE + 15, w: (i - 1 - start) * STRIDE + 24 })
      start = -1
    }
  }
  return bars
}

function toothTitle(tooth: number): string {
  const trs = props.treatments[tooth]
  const base = `${t("odontogram.dent")} ${tooth}`
  if (!trs?.length) return base
  return `${base} — ${trs.map(x => x.name).join(", ")}`
}

const LEGEND = [
  { key: "carie", kind: "wedge-carie" },
  { key: "obturation", kind: "wedge-obtu" },
  { key: "couronne", kind: "hatch" },
  { key: "bridge", kind: "bar" },
  { key: "a_traiter", kind: "todo" },
  { key: "absent", kind: "ghost" },
]
</script>

<template>
  <div class="odonto" dir="ltr">
    <svg class="odonto-defs" width="0" height="0" aria-hidden="true">
      <defs>
        <pattern :id="hatchId" patternUnits="userSpaceOnUse" width="5" height="5">
          <path d="M0,5 L5,0" stroke="#C98A2E" stroke-width="1.4" fill="none" />
        </pattern>
      </defs>
    </svg>

    <div v-for="row in rows" :key="row.key" class="odonto-arch">
      <div class="odonto-arch-label">{{ row.label }}</div>
      <div class="odonto-row" :style="{ width: `${rowWidth(row.teeth)}px` }">
        <svg class="odonto-bars" :width="rowWidth(row.teeth)" :height="ROW_H" aria-hidden="true">
          <rect
            v-for="(b, i) in bridgeBars(row.teeth)"
            :key="i"
            :x="b.x"
            :y="BAR_Y"
            :width="b.w"
            height="9"
            rx="4.5"
            fill="#FFFFFF"
            stroke="#C98A2E"
            stroke-width="1.5"
          />
        </svg>
        <button
          v-for="tooth in row.teeth"
          :key="tooth"
          type="button"
          class="odonto-cell"
          :class="cellClass(tooth)"
          :aria-label="`${t('odontogram.dent')} ${tooth}`"
          :title="toothTitle(tooth)"
          @click="emit('select', tooth)"
        >
          <svg
            class="tooth-anat"
            :class="{ flip: isLower(tooth) }"
            viewBox="0 0 60 110"
            aria-hidden="true"
          >
            <path
              v-for="(root, i) in ANATOMY[toothType(tooth)].roots"
              :key="i"
              :d="root"
              class="tooth-fill"
            />
            <path :d="ANATOMY[toothType(tooth)].crown" class="tooth-fill" />
            <path
              v-if="whole(tooth) === 'couronne' || whole(tooth) === 'bridge'"
              :d="ANATOMY[toothType(tooth)].crown"
              :fill="hatchRef"
              stroke="none"
              class="tooth-hatch"
            />
          </svg>

          <svg
            class="tooth-occl"
            viewBox="0 0 40 40"
            aria-hidden="true"
          >
            <path :d="OCCLUSAL[toothType(tooth)]" class="occl-shape" />
            <path
              v-if="whole(tooth) === 'couronne' || whole(tooth) === 'bridge'"
              :d="OCCLUSAL[toothType(tooth)]"
              :fill="hatchRef"
              stroke="none"
            />
            <path
              v-if="toothType(tooth) === 'molaire' && whole(tooth) !== 'absent'"
              d="M20,13 v14 M13,20 h14"
              class="occl-fissure"
            />
            <g v-if="wedgesVisible(tooth)" :transform="wedgeTransform(tooth)">
              <path
                v-for="m in marks(tooth)"
                :key="m.surface"
                :d="SURFACE_WEDGE[m.surface]"
                :class="`wedge wedge-${m.condition}`"
              />
            </g>
          </svg>

          <span class="tooth-num">{{ tooth }}</span>
        </button>
      </div>
    </div>

    <div class="odonto-legend">
      <span class="lg-item"><span class="lg-glyph lg-plain" />{{ t("odontogram.sain") }}</span>
      <span v-for="l in LEGEND" :key="l.key" class="lg-item">
        <span class="lg-glyph" :class="`lg-${l.kind}`" />
        {{ t(`odontogram.cond_${l.key}`) }}
      </span>
    </div>
  </div>
</template>
