/**
 * Minimal offline i18n: French + Arabic locale dictionaries, RTL switching,
 * localStorage persistence. No external dependencies (offline requirement).
 */
import { computed } from "vue"
import fr from "~/locales/fr"
import ar from "~/locales/ar"

export type Lang = "fr" | "ar"

const DICTS: Record<Lang, any> = { fr, ar }
const RTL_LANGS: Lang[] = ["ar"]
const STORAGE_KEY = "clinic.lang"

function resolveDict(dict: any, key: string): string | undefined {
  let node: any = dict
  for (const part of key.split(".")) {
    if (node == null || typeof node !== "object") return undefined
    node = node[part]
  }
  return typeof node === "string" ? node : undefined
}

function detectInitial(): Lang {
  if (import.meta.client) {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === "fr" || saved === "ar") return saved
  }
  return "fr"
}

export function useI18n() {
  const lang = useState<Lang>("i18n.lang", () => detectInitial())

  function setLang(l: Lang) {
    lang.value = l
    if (import.meta.client) {
      window.localStorage.setItem(STORAGE_KEY, l)
    }
  }

  function t(key: string, values?: Record<string, string | number>): string {
    const raw = resolveDict(DICTS[lang.value], key) ?? resolveDict(DICTS.fr, key) ?? key
    if (!values) return raw
    return raw.replace(/\{(\w+)\}/g, (_, name: string) =>
      values[name] !== undefined ? String(values[name]) : `{${name}}`,
    )
  }

  const isRtl = computed(() => RTL_LANGS.includes(lang.value))

  return { lang, setLang, t, isRtl }
}
