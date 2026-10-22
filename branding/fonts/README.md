# Brand fonts — licensing status

HKN brand typography per client brief:

| Font | Foundry | Used for | License status |
|---|---|---|---|
| **PP Neue Montreal** | Pangram Pangram (/pangrampangram.com) | Latin UI + documents | **Commercial.** Bundling inside the app requires a paid **App License** (desktop/print licenses do NOT cover app embedding). Source: https://pangrampangram.com/products/neue-montreal + https://pangrampangram.com/pages/eula |
| **Janah LT** (aka Janna LT) | Linotype / Monotype (Nadine Chahine) | Arabic UI + documents | **Commercial.** MyFonts lists Desktop/Webfont/App licenses; the App license is mobile-focused — confirm desktop-software embedding with MyFonts/Monotype before shipping files. Source: https://www.myfonts.com/collections/janna-font-linotype/ |

## Until license files are purchased

The app runs on the bundled open-license fallbacks (already offline-bundled):

- Latin: **Inter** (@fontsource/inter)
- Arabic: **Noto Sans Arabic** (@fontsource/noto-sans-arabic)

Drop licensed `.woff2` files into `frontend/public/fonts/` with exactly these names (they are
served at `/fonts/…` in dev and production; the `@font-face` rules in `main.css` pick them up
automatically, no code change needed):

```
frontend/public/fonts/NeueMontreal-Regular.woff2
frontend/public/fonts/NeueMontreal-Medium.woff2
frontend/public/fonts/NeueMontreal-SemiBold.woff2
frontend/public/fonts/NeueMontreal-Bold.woff2
frontend/public/fonts/JanahLT-Regular.woff2
frontend/public/fonts/JanahLT-Medium.woff2
frontend/public/fonts/JanahLT-SemiBold.woff2
frontend/public/fonts/JanahLT-Bold.woff2
```

Do NOT download free copies from unofficial sites — that is not a license.

## Buying checklist (owner action)

1. **PP Neue Montreal** — pangrampangram.com/products/neue-montreal. Ask specifically for the
   **App License** (their EULA: desktop/print licenses do not cover bundling inside an app).
   State the use case: "bundled inside locally installed dental practice software, one copy per
   clinic deployment". Ask whether their App License is one-time per product or per-deployment —
   put their written answer in the purchase email before paying.
2. **Janna LT** — MyFonts: myfonts.com/collections/janna-font-linotype. Buy the **App license
   tier**, then follow up with MyFonts/Monotype support **in writing** to confirm embedding in a
   packaged desktop web app (their App tier is mobile-oriented; get the confirmation email before
   shipping the files to clinics).
3. Budget note: both are one-time license fees, not subscriptions. Keep invoices and EULA copies
   for the file that ships inside every clinic build.

## When the files arrive

1. Copy the 8 `.woff2` files listed above into `frontend/public/fonts/` — keep the exact names;
   the `@font-face` rules in `main.css` pick them up automatically (build warnings about
   unresolved `/fonts/*.woff2` disappear once the files exist).
2. Rebuild (`npm run generate`) and restart. Fallback (Inter / Noto Sans Arabic) stays active for
   any missing file, so a partial delivery is still safe.
3. Verify: ordonnance letterhead brand text, Devis/DSP letterhead, and the عربي UI should now
   render in the brand faces (or their intended look).

## Keep in sync

- Keep delivery zips + original `.woff2` + license PDFs in `branding/fonts/purchases/` (this
  folder is intentionally NOT committed; `branding/fonts/` only carries this README).
- If a weight/stylistic decision changes the 8 files above, update the `@font-face` block in
  `frontend/app/assets/css/main.css` and this list together.
