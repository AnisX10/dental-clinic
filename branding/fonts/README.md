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
