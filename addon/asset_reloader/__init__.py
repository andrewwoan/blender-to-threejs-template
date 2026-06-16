bl_info = {
    "name": "Asset Reloader",
    "author": "andrewwoan",
    "version": (1, 3, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > Asset Reloader",
    "description": "Export marked collections to GLB + texture images into a web project, with a manifest for JS codegen + HMR.",
    "category": "Import-Export",
}

import os
import json
import bpy

SKIP_IMAGES = {"Render Result", "Viewer Node"}
CONFIG_NAME = "asset-reloader.config.json"
DEFAULT_MODELS = "public/models"
DEFAULT_TEXTURES = "public/textures"


def _project_root(scene):
    if not scene.reloader_project_dir:
        return ""
    return bpy.path.abspath(scene.reloader_project_dir)


def _read_config(root):
    """Read modelsDir/texturesDir from the project's config, with fallbacks."""
    models, textures = DEFAULT_MODELS, DEFAULT_TEXTURES
    cfg_path = os.path.join(root, CONFIG_NAME)
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                data = json.load(fh)
            models = data.get("modelsDir", models)
            textures = data.get("texturesDir", textures)
        except (ValueError, OSError):
            pass
    return models, textures


def _dirs(scene):
    root = _project_root(scene)
    models, textures = _read_config(root)
    return (
        os.path.normpath(os.path.join(root, models)),
        os.path.normpath(os.path.join(root, textures)),
    )


def _find_layer_collection(layer_coll, name):
    if layer_coll.collection.name == name:
        return layer_coll
    for child in layer_coll.children:
        found = _find_layer_collection(child, name)
        if found:
            return found
    return None


def _export_textures(textures_dir):
    os.makedirs(textures_dir, exist_ok=True)
    count = 0
    for img in bpy.data.images:
        if img.name in SKIP_IMAGES:
            continue
        if img.size[0] == 0 or img.size[1] == 0:
            continue
        path = os.path.join(textures_dir, bpy.path.clean_name(img.name) + ".png")
        orig_fp, orig_fmt = img.filepath_raw, img.file_format
        try:
            img.filepath_raw = path
            img.file_format = "PNG"
            img.save()
            count += 1
        except RuntimeError:
            pass
        finally:
            img.filepath_raw, img.file_format = orig_fp, orig_fmt
    return count


class RELOADER_OT_export(bpy.types.Operator):
    bl_idname = "reloader.export_glb"
    bl_label = "Export Marked Collections"
    bl_description = "Export each marked, non-empty collection to its own GLB (+ textures) into the project"

    def execute(self, context):
        scene = context.scene
        view_layer = context.view_layer

        root = _project_root(scene)
        if not root or not os.path.isdir(root):
            self.report({"ERROR"}, "Set a valid Project folder in the Asset Reloader panel")
            return {"CANCELLED"}

        models_dir, textures_dir = _dirs(scene)
        os.makedirs(models_dir, exist_ok=True)

        original_active = view_layer.active_layer_collection
        exported_files = []
        skipped_empty = []

        for coll in bpy.data.collections:
            if not coll.glb_do_export:
                continue
            if len(coll.all_objects) == 0:
                skipped_empty.append(coll.name)
                continue
            lc = _find_layer_collection(view_layer.layer_collection, coll.name)
            if lc is None:
                self.report({"WARNING"}, f"'{coll.name}' not in view layer, skipped")
                continue

            view_layer.active_layer_collection = lc
            filename = bpy.path.clean_name(coll.name) + ".glb"
            bpy.ops.export_scene.gltf(
                filepath=os.path.join(models_dir, filename),
                export_format="GLB",
                use_active_collection=True,
                use_active_collection_with_nested=True,
                use_visible=False,
                export_apply=False,
            )
            exported_files.append(filename)

        view_layer.active_layer_collection = original_active

        with open(os.path.join(models_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"models": exported_files}, fh, indent=2)

        tex_count = _export_textures(textures_dir) if scene.reloader_export_textures else 0

        msg = f"Exported {len(exported_files)} GLB(s), {tex_count} texture(s)"
        if skipped_empty:
            msg += f"; skipped empty: {', '.join(skipped_empty)}"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class RELOADER_PT_panel(bpy.types.Panel):
    bl_label = "Asset Reloader"
    bl_idname = "RELOADER_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Asset Reloader"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "reloader_project_dir", text="Project")
        if not _project_root(scene) or not os.path.isdir(_project_root(scene)):
            layout.label(text="Set your project root folder", icon="ERROR")
        layout.prop(scene, "reloader_export_textures")

        layout.separator()
        layout.label(text="Collections to export:")
        box = layout.box()
        colls = list(bpy.data.collections)
        if not colls:
            box.label(text="(no collections)", icon="INFO")
        for coll in colls:
            row = box.row()
            row.prop(coll, "glb_do_export", text=coll.name)
            if len(coll.all_objects) == 0:
                row.label(text="empty", icon="ERROR")

        layout.separator()
        layout.operator("reloader.export_glb", icon="EXPORT")


classes = (RELOADER_OT_export, RELOADER_PT_panel)

addon_keymaps = []


def register():
    bpy.types.Collection.glb_do_export = bpy.props.BoolProperty(
        name="Export",
        description="Include this collection when exporting GLBs",
        default=True,
    )
    bpy.types.Scene.reloader_project_dir = bpy.props.StringProperty(
        name="Project Dir",
        description="Root folder of your web project (saved with this .blend)",
        subtype="DIR_PATH",
        default="",
    )
    bpy.types.Scene.reloader_export_textures = bpy.props.BoolProperty(
        name="Also export texture images",
        default=True,
    )
    for cls in classes:
        bpy.utils.register_class(cls)

    # Shift+E in the 3D viewport (Object Mode) triggers the export.
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")
        kmi = km.keymap_items.new(
            "reloader.export_glb", type="E", value="PRESS", shift=True
        )
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Collection.glb_do_export
    del bpy.types.Scene.reloader_project_dir
    del bpy.types.Scene.reloader_export_textures


if __name__ == "__main__":
    register()
