// Default per-model class template.
//
// Copy this file, customize it, and point "template" in asset-reloader.config.json
// at your copy to target a different framework/structure.
//
// Placeholders replaced by the codegen:
//   {{className}}  PascalCase class name   (e.g. Hat)
//   {{key}}        camelCase asset key     (e.g. hat)
//   {{file}}       GLB filename            (e.g. hat.glb)

import * as THREE from "three/webgpu";
import { Experience } from "../Experience";

export class {{className}} {
  constructor() {
    this.experience = Experience.getInstance();
    this.model = this.experience.resources.items.{{key}}.scene;

    this.init();
  }

  init() {
    this.model.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    this.experience.scene.add(this.model);
  }

  resize() {}

  update() {}

  destroy() {}
}
