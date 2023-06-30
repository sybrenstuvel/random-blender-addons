bl_info = {
    "name": "Only Show Selected Keyframes",
    "author": "dr. Sybren",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "location": "Graph Editor > View",
    "description": "Show a 'Only Show Selected Keyframes' option in the graph editor header",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}


import bpy


def draw_menu(self, context):
    layout = self.layout
    layout.prop(context.preferences.edit, 'show_only_selected_curve_keyframes')


def register():
    bpy.types.GRAPH_HT_header.append(draw_menu)


def unregister():
    bpy.types.GRAPH_HT_header.remove(draw_menu)


if __name__ == "__main__":
    register()
