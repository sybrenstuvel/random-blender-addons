bl_info = {
    'name': 'Show Context',
    'author': 'Sybren A. Stüvel',
    'version': (1, 1),
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
        _show_properties("Context", context)
        self.report({'INFO'}, "Check the terminal")
        return {'FINISHED'}


class DEVELOPER_OT_show_space_data(bpy.types.Operator):
    bl_idname = 'developer.show_space_data'
    bl_label = 'Show Space Data'
    bl_description = 'List the space data properties in the terminal'
    bl_options = {'REGISTER'}

    def execute(self, context: bpy.types.Context) -> set[str]:
        _show_properties("Space Data", context.space_data)
        self.report({'INFO'}, "Check the terminal")
        return {'FINISHED'}


def _show_properties(header: str, python_object: object) -> None:
    to_print = {name: repr(getattr(python_object, name, '-error-')) for name in dir(python_object)}

    print(f"--- {header}: {30*'-'}")
    pprint(to_print, width=120)


classes = (
    DEVELOPER_OT_show_context,
    DEVELOPER_OT_show_space_data,
)
register, unregister = bpy.utils.register_classes_factory(classes)
