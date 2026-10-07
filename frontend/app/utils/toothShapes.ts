/**
 * Stylised hand-drawn tooth shapes for the odontogram (DentalPin-style).
 *
 * - Anatomy viewBox is `0 0 60 110`, drawn "upper arch" (roots up, crown down).
 *   Lower-arch teeth reuse the same geometry flipped vertically by the chart.
 * - Occlusal viewBox is `0 0 40 40`; surface wedges are drawn from the centre.
 */

export type ToothType = "incisive" | "canine" | "premolaire" | "molaire"

/** One odontogram mark as returned by the API. */
export interface ToothCondition {
  tooth: number
  condition: string
  surface: string
}

export interface Anatomy {
  crown: string
  roots: string[]
}

export const ANATOMY: Record<ToothType, Anatomy> = {
  incisive: {
    crown: "M15,64 Q15,60 19,60 L41,60 Q45,60 45,64 L43,97 Q43,104 36,104 L24,104 Q17,104 17,97 Z",
    roots: ["M20,60 C20,48 23,38 24,26 Q25,8 30,8 Q35,8 36,26 C37,38 40,48 40,60 Z"],
  },
  canine: {
    crown: "M16,62 L25,97 Q27,104 30,104 Q33,104 35,97 L44,62 Z",
    roots: ["M22,62 C22,50 24,42 25,30 Q26,8 30,8 Q34,8 35,30 C36,42 38,50 38,62 Z"],
  },
  premolaire: {
    crown: "M14,65 Q14,61 18,61 L42,61 Q46,61 46,65 L46,94 Q46,102 38,102 L34,98 Q30,103 26,98 L22,102 Q14,102 14,94 Z",
    roots: ["M21,61 C20,50 22,42 24,32 Q26,14 30,14 Q34,14 36,32 C38,42 40,50 39,61 Z"],
  },
  molaire: {
    crown: "M10,66 Q10,61 15,61 L45,61 Q50,61 50,66 L50,92 Q50,101 42,101 L36,97 Q30,102 24,97 L18,101 Q10,101 10,92 Z",
    roots: [
      "M15,61 C14,48 16,40 18,30 Q19,19 22,19 Q25,19 26,30 C27,40 29,48 28,61 Z",
      "M32,61 C31,48 33,40 34,30 Q35,19 38,19 Q41,19 42,30 C44,40 46,48 45,61 Z",
    ],
  },
}

export const OCCLUSAL: Record<ToothType, string> = {
  incisive: "M14,3 h12 a7,7 0 0 1 7,7 v20 a7,7 0 0 1 -7,7 h-12 a7,7 0 0 1 -7,-7 v-20 a7,7 0 0 1 7,-7 z",
  canine: "M10,20 a10,17 0 1 0 20,0 a10,17 0 1 0 -20,0 z",
  premolaire: "M11,5 h18 a6,6 0 0 1 6,6 v18 a6,6 0 0 1 -6,6 h-18 a6,6 0 0 1 -6,-6 v-18 a6,6 0 0 1 6,-6 z",
  molaire: "M9,4 h22 a7,7 0 0 1 7,7 v18 a7,7 0 0 1 -7,7 h-22 a7,7 0 0 1 -7,-7 v-18 a7,7 0 0 1 7,-7 z",
}

/** Wedge paths from the occlusal centre — default orientation:
 *  mésiale points left, distale right, vestibulaire up, linguale down. */
export const SURFACE_WEDGE: Record<string, string> = {
  occlusale: "M20,10 L29,20 L20,30 L11,20 Z",
  mesiale: "M20,20 L3,9 L3,31 Z",
  distale: "M20,20 L37,9 L37,31 Z",
  vestibulaire: "M20,20 L9,3 L31,3 Z",
  linguale: "M20,20 L9,37 L31,37 Z",
}

export const SURFACES = ["occlusale", "mesiale", "distale", "vestibulaire", "linguale"] as const
export type Surface = (typeof SURFACES)[number]

export const CONDITIONS = ["a_traiter", "carie", "obturation", "couronne", "bridge", "absent"] as const
export type Condition = (typeof CONDITIONS)[number]

export const SURFACE_CONDITIONS: Condition[] = ["carie", "obturation"]

export const PERMANENT = {
  upper: [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28],
  lower: [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38],
}

export const DECIDUOUS = {
  upper: [55, 54, 53, 52, 51, 61, 62, 63, 64, 65],
  lower: [85, 84, 83, 82, 81, 71, 72, 73, 74, 75],
}

export const ALL_TEETH = [...PERMANENT.upper, ...PERMANENT.lower, ...DECIDUOUS.upper, ...DECIDUOUS.lower]

export function isDeciduous(tooth: number): boolean {
  return tooth >= 51
}

export function quadrant(tooth: number): number {
  return Math.floor(tooth / 10)
}

/** Anatomy family for a FDI tooth number (deciduous molars have no premolars). */
export function toothType(tooth: number): ToothType {
  const unit = tooth % 10
  if (unit <= 2) return "incisive"
  if (unit === 3) return "canine"
  if (isDeciduous(tooth)) return "molaire"
  return unit <= 5 ? "premolaire" : "molaire"
}

/** Lower arch: anatomy drawing flipped vertically (roots down). */
export function isLower(tooth: number): boolean {
  const q = quadrant(tooth)
  return q === 3 || q === 4 || q === 7 || q === 8
}

/** Right-side quadrants (14) are drawn on the screen-left half: mésial points
 *  right (toward the midline), so the wedge group is mirrored horizontally. */
export function mirrorHorizontal(tooth: number): boolean {
  const q = quadrant(tooth)
  return q === 1 || q === 4 || q === 5 || q === 8
}

/** Lower occlusal views: vestibulaire points down (outside of the arch). */
export function mirrorVertical(tooth: number): boolean {
  return isLower(tooth)
}
