# Asset Reloader

A Blender → web live-reload pipeline. Click one button in Blender and your
exported `.glb` models (and texture-paint images) drop straight into your web
project, the JS wiring regenerates itself, and the page hot-reloads.

Inspired by studio workflows like Merci Michel's "Coastal World".

It has **two halves** — you need both:

| Half | What it does | Where it lives |
| --- | --- | --- |
| **Blender addon** | Exports *marked, non-empty* collections → one GLB each, saves texture images, writes a `manifest.json`. | Installed once in Blender (global). |
| **Integration** (Vite plugin + codegen) | Watches the export folder, regenerates your asset list + per-model classes + a registry, reloads the page. | Copied into each web project. |

A small `asset-reloader.config.json` at your project root ties them together,
so the addon is **completely project-agnostic** — no hardcoded paths.

---

## Requirements

- Blender 4.0+ (tested on 5.1).
- A Vite project. The default codegen template targets a Bruno-Simon-style
  `Experience` class (`Experience.getInstance()`, `resources.items.<key>.scene`,
  `three/webgpu`). **Using a different structure? Override the template** — see
  [Custom template](#custom-template). Paths are configurable regardless.

---

## Install — the addon (once)

1. Download `addon/asset_reloader.zip` (or zip the `addon/asset_reloader.py` file).
2. Blender → Edit → Preferences → Add-ons → **Install from Disk…** → pick the zip.
3. Enable **"Asset Reloader"**.

It now appears in the 3D viewport sidebar (**N**) under the **Asset Reloader** tab.

## Install — the integration (per project)

Copy these into your web project:

- `integration/asset-codegen.mjs`        → `scripts/asset-codegen.mjs`
- `integration/vite-plugin-asset-reloader.mjs` → `scripts/vite-plugin-asset-reloader.mjs`
- `integration/asset-reloader.config.example.json` → `asset-reloader.config.json` (edit paths)

Then register the plugin in `vite.config.js`:

```js
import { defineConfig } from "vite";
import assetReloader from "./scripts/vite-plugin-asset-reloader.mjs";

export default defineConfig({
  plugins: [assetReloader()],
});
```

Finally adopt the `World.js` pattern (see `integration/World.example.js`): loop
over the generated `modelClasses` instead of hand-instantiating each model.

---

## Workflow

1. In Blender, set the **Project** field (the panel) to your project root — saved
   per `.blend`, so each file remembers its own target.
2. Tick the collections you want to export (empty ones are skipped automatically).
3. Hit **Export Marked Collections** (or press **Shift+E** in the viewport in Object Mode).
4. With `npm run dev` running, the page reloads with the new/updated models.

New model = new collection → tick → export. A `World/<Name>.js` class is
scaffolded automatically the first time and **never overwritten after**, so your
custom behavior is safe. Edit that file freely.

---

## Config reference (`asset-reloader.config.json`)

All keys optional; defaults shown.

```json
{
  "publicDir": "public",
  "modelsDir": "public/models",
  "texturesDir": "public/textures",
  "assetsFile": "src/Experience/Utils/assets.js",
  "worldDir": "src/Experience/World",
  "registryFile": "src/Experience/World/models.generated.js",
  "template": null
}
```

- `assetsFile`: set to `null` to skip generating the resource list (handle loading yourself).
- `template`: path to a custom per-model class template (see below).
- The web path written into `assetsFile` is derived from `publicDir` → `modelsDir`
  (e.g. `public/models` ⇒ `/models/<file>.glb`).

---

## Custom template

To target a framework other than the default `Experience` structure, point
`template` at your own file and use these placeholders:

- `{{className}}` — PascalCase class name (e.g. `Hat`)
- `{{key}}` — camelCase asset key (e.g. `hat`)
- `{{file}}` — the GLB filename (e.g. `hat.glb`)

See `integration/model.template.js` for the default to copy and adapt.

---

## Caveats

- One global addon serves all projects; it's the **Project** field (saved in the
  `.blend`) that targets a specific repo.
- Generated files (`assetsFile`, `registryFile`) are rewritten every export —
  don't hand-edit them. Scaffolded `World/<Name>.js` files are yours to edit.
- Unchecking a collection drops it from the manifest immediately, but its stale
  `.glb` stays on disk — delete it if you want it gone.

## License

MIT
