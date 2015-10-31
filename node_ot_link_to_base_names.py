bl_info = {
    'name': 'Material node fixer',
    'author': 'Sybren A. Stüvel',
    'version': (0, 1),
    'blender': (2, 75, 0),
    'location': 'Press [Space], search for "link material node"',
    'category': 'Material',
}

import bpy


class NODE_OT_link_to_base_names(bpy.types.Operator):
    bl_idname = 'node.link_to_base_names'
    bl_label = 'Link material nodes to base names'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue

            for node in mat.node_tree.nodes:
                if node.type != 'GROUP':
                    continue

                self.fixup_node_group(node)

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

    def fixup_node_group(self, node_group):

        base, suffix = self.split_name(node_group.node_tree.name)
        if suffix is None:
            return

        try:
            base_group = bpy.data.node_groups[base]
        except KeyError:
            print('Base node group %r not found' % base)
            return

        node_group.node_tree = base_group
        node_group.name = base


def register():
    bpy.utils.register_class(NODE_OT_link_to_base_names)


def unregister():
    bpy.utils.unregister_class(NODE_OT_link_to_base_names)


if __name__ == "__main__":
    register()
