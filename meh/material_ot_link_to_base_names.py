bl_info = {
    'name': 'Material fixer',
    'author': 'Sybren A. Stüvel',
    'version': (0, 1),
    'blender': (2, 75, 0),
    'location': 'Press [Space], search for "link materials"',
    'category': 'Material',
}

import bpy


class MATERIAL_OT_link_to_base_names(bpy.types.Operator):
    bl_idname = "material.link_to_base_names"
    bl_label = "Link materials to base names"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for ob in context.scene.objects:
            for slot in ob.material_slots:
                self.fixup_slot(slot)

        return {'FINISHED'}

    def split_name(self, name):
        if '.' not in name:
            return name, None

        base, suffix = name.rsplit('.', 1)
        try:
            num = int(suffix, 10)
        except ValueError:
            # Not a numeric suffix
            return name, None

        return base, suffix

    def fixup_slot(self, slot):
        if not slot.material:
            return

        base, suffix = self.split_name(slot.material.name)
        if suffix is None:
            return

        try:
            base_mat = bpy.data.materials[base]
        except KeyError:
            print('Base material %r not found' % base)
            return

        slot.material = base_mat


def register():
    bpy.utils.register_class(MATERIAL_OT_link_to_base_names)


def unregister():
    bpy.utils.unregister_class(MATERIAL_OT_link_to_base_names)


if __name__ == "__main__":
    register()
