<script setup lang="ts">
/**
 * Anatomical odontogram chart (DentalPin-style): a 4-row layout —
 * upper anatomy / upper occlusal + numbers / lower occlusal + numbers /
 * lower anatomy — so the two occlusal rows face each other at the midline.
 * Surface wedges, occlusal hatching for crowns/bridges, bridge connector
 * bars at crown level and ghosted missing teeth.
 */
import {
  ANATOMY,
  DECIDUOUS,
  OCCLUSAL,
  OCCLUSAL_DETAIL,
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
const GAP_W = 22
const ANAT_H = 90
// Crown band of the 50x90 anatomy drawing: unflipped y ≈ 51–86; the lower
// arch is scaleY(-1)-flipped, so its crown band is mirrored to y ≈ 6–42.
const UPPER_BAR_Y = 58
const LOWER_BAR_Y = 23

const uid = Math.random().toString(36).slice(2, 8)
const hatchId = `odont-hatch-${uid}`
const hatchRef = `url(#${hatchId})`

const arches = computed(() => (props.dentition === "temporaire" ? DECIDUOUS : PERMANENT))

const anatomyRows = computed(() => [
  { key: "sup", teeth: arches.value.upper, barY: UPPER_BAR_Y },
  { key: "inf", teeth: arches.value.lower, barY: LOWER_BAR_Y },
])

const occlusalRows = computed(() => [
  { key: "occl-sup", teeth: arches.value.upper, numFirst: false },
  { key: "occl-inf", teeth: arches.value.lower, numFirst: true },
])

const halfCount = computed(() => arches.value.upper.length / 2)
const rowW = computed(() => arches.value.upper.length * STRIDE - 4 + GAP_W)
const midX = computed(() => halfCount.value * STRIDE + 9)

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

function hatched(tooth: number): boolean {
  const w = whole(tooth)
  return w === "couronne" || w === "bridge"
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
  return whole(tooth) !== "absent"
}

function wedgeTransform(tooth: number): string {
  const parts: string[] = []
  if (mirrorHorizontal(tooth)) parts.push("translate(40 0) scale(-1 1)")
  if (mirrorVertical(tooth)) parts.push("translate(0 40) scale(1 -1)")
  return parts.join(" ")
}

/** Cell left edge inside a row (accounts for the midline gap). */
function cellX(i: number, half: number): number {
  return i * STRIDE + (i >= half ? GAP_W : 0)
}

function bridgeBars(row: number[]): { x: number, w: number }[] {
  const bars: { x: number, w: number }[] = []
  const half = row.length / 2
  let start = -1
  for (let i = 0; i <= row.length; i++) {
    const isBridge = i < row.length && whole(row[i]!) === "bridge"
    if (isBridge && start === -1) start = i
    if (!isBridge && start !== -1) {
      if (i - start >= 2) {
        // Span symmetrically across the crowns (graphic spans cellX+4..+54).
        const x = cellX(start, half) + 10
        const end = cellX(i - 1, half) + 48
        bars.push({ x, w: end - x })
      }
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

    <div class="odonto-arch-label">{{ t("odontogram.arcade_sup") }}</div>

    <div class="odonto-rows">
      <div class="odonto-midline" :style="{ left: `${midX}px` }" aria-hidden="true" />

      <div
        v-for="anat in anatomyRows"
        :key="anat.key"
        class="odonto-row odonto-row-anat"
        :style="{ width: `${rowW}px` }"
      >
        <svg class="odonto-bars" :width="rowW" :height="ANAT_H" aria-hidden="true">
          <rect
            v-for="(b, i) in bridgeBars(anat.teeth)"
            :key="i"
            :x="b.x"
            :y="anat.barY"
            :width="b.w"
            height="9"
            rx="4.5"
            fill="#FFFFFF"
            stroke="#C98A2E"
            stroke-width="1.5"
          />
        </svg>
        <button
          v-for="(tooth, i) in anat.teeth"
          :key="tooth"
          type="button"
          class="odonto-cell"
          :class="[{ half2: i === halfCount }, cellClass(tooth)]"
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
              v-for="(root, ri) in ANATOMY[toothType(tooth)].roots"
              :key="ri"
              :d="root"
              class="tooth-fill"
            />
            <path :d="ANATOMY[toothType(tooth)].crown" class="tooth-fill" />
            <path
              v-for="(d, di) in ANATOMY[toothType(tooth)].detail"
              :key="`d${di}`"
              :d="d"
              class="tooth-detail"
            />
          </svg>
        </button>
      </div>

      <div
        v-for="oc in occlusalRows"
        :key="oc.key"
        class="odonto-row odonto-row-occl"
        :style="{ width: `${rowW}px` }"
      >
        <button
          v-for="(tooth, i) in oc.teeth"
          :key="tooth"
          type="button"
          class="odonto-cell odonto-cell-occl"
          :class="[{ half2: i === halfCount }, cellClass(tooth)]"
          :aria-label="`${t('odontogram.dent')} ${tooth}`"
          :title="toothTitle(tooth)"
          @click="emit('select', tooth)"
        >
          <span v-if="oc.numFirst" class="tooth-num">{{ tooth }}</span>
          <svg class="tooth-occl" viewBox="0 0 40 40" aria-hidden="true">
            <path :d="OCCLUSAL[toothType(tooth)]" class="occl-shape" />
            <path
              v-if="hatched(tooth)"
              :d="OCCLUSAL[toothType(tooth)]"
              :fill="hatchRef"
              stroke="none"
            />
            <path :d="OCCLUSAL_DETAIL[toothType(tooth)]" class="occl-detail" />
            <path
              v-if="toothType(tooth) === 'molaire' && whole(tooth) !== 'absent'"
              d="M20,14.5 v11 M14.5,20 h11"
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
          <span v-if="!oc.numFirst" class="tooth-num">{{ tooth }}</span>
        </button>
      </div>
    </div>

    <div class="odonto-arch-label">{{ t("odontogram.arcade_inf") }}</div>

    <div class="odonto-legend">
      <span class="lg-item"><span class="lg-glyph lg-plain" />{{ t("odontogram.sain") }}</span>
      <span v-for="l in LEGEND" :key="l.key" class="lg-item">
        <span class="lg-glyph" :class="`lg-${l.kind}`" />
        {{ t(`odontogram.cond_${l.key}`) }}
      </span>
    </div>
  </div>
</template>
