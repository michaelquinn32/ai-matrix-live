// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  // Static output (default) — no SSR, pure static HTML/CSS/JS.
  // Cloudflare Pages serves the built files from dist/.
  output: 'static',

  // Will be set to the Cloudflare Pages URL once deployed.
  // site: 'https://ai-matrix-live.pages.dev',
});
