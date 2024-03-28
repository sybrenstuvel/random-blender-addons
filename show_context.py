bl_info = {
    'name': 'Show Context',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (4, 1, 0),
    'location': 'Anywhere',
    'category': 'Developer',
}

from pprint import pprint

import bpy


class DEVELOPER_OT_show_context(bpy.types.Operator):
    bl_idname = 'developer.show_context'
    bl_label = 'Show Context'
    bl_description = 'List the context properties in the terminal'
    bl_options = {'REGISTER'}

    def execute(self, context: bpy.types.Context) -> set[str]:
        to_print = {name: repr(getattr(context, name, '-error-')) for name in dir(context)}

        print("--- Context: " + 30 * "-")
        pprint(to_print, width=120)
        self.report({'INFO'}, "Check the terminal")
        return {'FINISHED'}


classes = (DEVELOPER_OT_show_context,)
register, unregister = bpy.utils.register_classes_factory(classes)
