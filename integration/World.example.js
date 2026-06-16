// Example World.js pattern: loop over the generated registry instead of
// hand-instantiating each model. Keep any non-model classes (lights, env,
// post-processing) hand-written alongside.

import * as THREE from "three/webgpu";
import { Experience } from "../Experience";
import { Environment } from "./Environment";
import { modelClasses } from "./models.generated.js";

export class World {
  constructor() {
    this.experience = Experience.getInstance();
    this.models = [];

    this.experience.resources.on("ready", () => {
      this.models = modelClasses.map((ModelClass) => new ModelClass());
      this.environment = new Environment();
    });

    this.init();
  }

  init() {}

  resize() {
    for (const model of this.models) model.resize?.();
  }

  update() {
    for (const model of this.models) model.update?.();
  }
}
