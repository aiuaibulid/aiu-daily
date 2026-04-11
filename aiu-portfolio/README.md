# AIU Portfolio on Cloudflare Pages

This folder is a static site for Cloudflare Pages.

## Included files

- `index.html`: English home page
- `indexZH.html`: Traditional Chinese home page
- `guide-en.html`: English guide library
- `guide.html`: Traditional Chinese guide library
- `harness-en.html`: English Harness document page
- `harness.html`: Traditional Chinese Harness document page
- `harness.pdf`: Embedded and downloadable PDF
- `_redirects`: pretty route aliases for Pages
- `_headers`: security and cache headers for Pages
- `404.html`: custom not found page

## Recommended Cloudflare Pages setup

If this repository is connected to Cloudflare Pages and `aiu-portfolio` stays as a subfolder:

- Framework preset: `None`
- Build command: leave empty, or use `exit 0` if the dashboard requires a command
- Build output directory: `aiu-portfolio`

If you instead set the Pages project root directory to `aiu-portfolio`:

- Framework preset: `None`
- Build command: leave empty, or use `exit 0` if the dashboard requires a command
- Build output directory: `.`

## Recommended build watch path

Because this repository contains multiple unrelated projects, set the Pages build watch path to:

- `aiu-portfolio/**`

This keeps unrelated file changes from triggering a new portfolio deployment.

## Route aliases added by `_redirects`

- `/en` -> English home
- `/zh` -> Chinese home
- `/guide` -> English guide library
- `/guide/zh` -> Chinese guide library
- `/harness` -> English Harness page
- `/harness/zh` -> Chinese Harness page
- `/harness/pdf` -> PDF

## Notes before production

- No canonical URLs are set yet because the final production domain is not defined.
- If you later bind a custom domain, update each HTML file with canonical and social image metadata.
- The current site is static-only. No Functions or build pipeline are required.
