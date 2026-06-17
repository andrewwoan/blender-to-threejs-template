bl_info = {
    "name": "Asset Reloader",
    "author": "andrewwoan",
    "version": (1, 5, 0),
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


def _export_options(scene):
    """Map the panel's Export Options to glTF exporter kwargs."""
    return {
        "export_apply": scene.reloader_apply_modifiers,
        "export_draco_mesh_compression_enable": scene.reloader_draco,
        "export_draco_mesh_compression_level": scene.reloader_draco_level,
        "export_materials": scene.reloader_materials,
        "export_image_format": scene.reloader_image_format,
        "export_animations": scene.reloader_export_animations,
        "export_cameras": scene.reloader_export_cameras,
        "export_lights": scene.reloader_export_lights,
        "export_tangents": scene.reloader_export_tangents,
        "export_extras": scene.reloader_export_extras,
        "export_yup": scene.reloader_yup,
    }


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

        opts = _export_options(scene)
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
                **opts,
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
        header = layout.row()
        header.prop(
            scene,
            "reloader_show_options",
            icon="TRIA_DOWN" if scene.reloader_show_options else "TRIA_RIGHT",
            text="Export Options",
            emboss=False,
        )
        if scene.reloader_show_options:
            box = layout.box()
            box.prop(scene, "reloader_apply_modifiers")
            box.prop(scene, "reloader_draco")
            if scene.reloader_draco:
                box.prop(scene, "reloader_draco_level")
            box.prop(scene, "reloader_materials")
            box.prop(scene, "reloader_image_format")
            box.prop(scene, "reloader_export_animations")
            box.prop(scene, "reloader_export_cameras")
            box.prop(scene, "reloader_export_lights")
            box.prop(scene, "reloader_export_tangents")
            box.prop(scene, "reloader_export_extras")
            box.prop(scene, "reloader_yup")
            box.prop(scene, "reloader_export_textures")

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
        description="Save texture-paint / image datablocks as PNGs into texturesDir",
        default=True,
    )
    bpy.types.Scene.reloader_apply_modifiers = bpy.props.BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers (on a temporary copy) before export",
        default=False,
    )
    bpy.types.Scene.reloader_draco = bpy.props.BoolProperty(
        name="Draco Compression",
        description="Compress mesh data with Draco (web side needs a DRACOLoader)",
        default=False,
    )
    bpy.types.Scene.reloader_draco_level = bpy.props.IntProperty(
        name="Compression Level",
        description="Draco compression level (higher = smaller files, slower)",
        default=6,
        min=0,
        max=10,
    )
    bpy.types.Scene.reloader_materials = bpy.props.EnumProperty(
        name="Materials",
        description="How materials are exported",
        items=[
            ("EXPORT", "Export", "Export full materials"),
            ("PLACEHOLDER", "Placeholder", "Material slots only, no data"),
            ("VIEWPORT", "Viewport", "Export viewport material settings"),
            ("NONE", "No Export", "Do not export materials"),
        ],
        default="EXPORT",
    )
    bpy.types.Scene.reloader_image_format = bpy.props.EnumProperty(
        name="Images",
        description="How images embedded in the GLB are encoded",
        items=[
            ("AUTO", "Automatic", "Keep PNGs as PNG, JPEGs as JPEG"),
            ("JPEG", "JPEG", "Encode all images as JPEG"),
            ("WEBP", "WebP", "Encode all images as WebP"),
            ("NONE", "None", "Do not embed images"),
        ],
        default="AUTO",
    )
    bpy.types.Scene.reloader_export_animations = bpy.props.BoolProperty(
        name="Animations",
        description="Export actions / animation data",
        default=True,
    )
    bpy.types.Scene.reloader_export_cameras = bpy.props.BoolProperty(
        name="Cameras",
        description="Export cameras",
        default=False,
    )
    bpy.types.Scene.reloader_export_lights = bpy.props.BoolProperty(
        name="Punctual Lights",
        description="Export lights via KHR_lights_punctual",
        default=False,
    )
    bpy.types.Scene.reloader_export_tangents = bpy.props.BoolProperty(
        name="Tangents",
        description="Export vertex tangents (needed for some normal-map setups)",
        default=False,
    )
    bpy.types.Scene.reloader_export_extras = bpy.props.BoolProperty(
        name="Custom Properties",
        description="Export custom properties as glTF extras",
        default=False,
    )
    bpy.types.Scene.reloader_yup = bpy.props.BoolProperty(
        name="+Y Up",
        description="Convert to glTF's +Y up convention (recommended for three.js)",
        default=True,
    )
    bpy.types.Scene.reloader_show_options = bpy.props.BoolProperty(
        name="Show Export Options",
        description="Expand the export options section",
        default=False,
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
    del bpy.types.Scene.reloader_apply_modifiers
    del bpy.types.Scene.reloader_draco
    del bpy.types.Scene.reloader_draco_level
    del bpy.types.Scene.reloader_materials
    del bpy.types.Scene.reloader_image_format
    del bpy.types.Scene.reloader_export_animations
    del bpy.types.Scene.reloader_export_cameras
    del bpy.types.Scene.reloader_export_lights
    del bpy.types.Scene.reloader_export_tangents
    del bpy.types.Scene.reloader_export_extras
    del bpy.types.Scene.reloader_yup
    del bpy.types.Scene.reloader_show_options


if __name__ == "__main__":
    register()
