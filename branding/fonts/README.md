# Fonts

Dentilo ships only open-licence fonts, bundled offline through `@fontsource`
(see `frontend/nuxt.config.ts`):

- Latin: **Inter** (SIL OFL 1.1)
- Arabic: **Noto Sans Arabic** (SIL OFL 1.1)

The commercial faces from the previous client brief (PP Neue Montreal, Janah LT)
were never licensed or shipped and are no longer referenced. To add a licensed
brand font later, put the `.woff2` files in `frontend/public/fonts/` and declare
them in `frontend/app/assets/css/main.css` in the same commit, so the app never
requests a file that is not there.
