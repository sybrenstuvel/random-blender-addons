"""
Disable constraints without moving.

Really simple add-on for disabling constraints without moving the constrained object.
"""

bl_info = {
    'name': 'Copy Visual Transform',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (2, 80, 0),
    'location': 'N-panel in the 3D Viewport',
    'category': 'Animation',
    'support': 'COMMUNITY',
}

import bpy


def get_matrix(context):
    bone = context.active_pose_bone
    if bone:
        # Convert matrix to world space
        arm = context.active_object
        mat = arm.matrix_world @ bone.matrix
    else:
        mat = context.active_object.matrix_world

    return mat


def set_matrix(context, mat):
    bone = context.active_pose_bone
    if bone:
        # Convert matrix to local space
        arm = context.active_object
        bone.matrix = arm.matrix_world.inverted() @ mat
    else:
        context.active_object.matrix_world = mat


class OBJECT_OT_copy_matrix(bpy.types.Operator):
    bl_idname = 'object.copy_matrix'
    bl_label = 'Copy matrix'
    bl_description = 'Copies the matrix of the currently active object or pose bone ' \
                     'to the clipboard. Uses world-space matrices'

    @classmethod
    def poll(cls, context):
        return bool(context.active_pose_bone) or bool(context.active_object)

    def execute(self, context):
        context.window_manager.clipboard = repr(get_matrix(context))
        return {'FINISHED'}


class OBJECT_OT_paste_matrix(bpy.types.Operator):
    bl_idname = 'object.paste_matrix'
    bl_label = 'Paste matrix'
    bl_description = 'Pastes the matrix of the clipboard to the currently active pose bone ' \
                     'or object. Uses world-space matrices'

    @classmethod
    def poll(cls, context):
        return bool(context.active_pose_bone) or bool(context.active_object)

    def execute(self, context):
        from mathutils import Matrix

        mat = eval(context.window_manager.clipboard, {}, {'Matrix': Matrix})
        set_matrix(context, mat)

        return {'FINISHED'}


class VIEW3D_PT_copy_matrix(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "View"
    bl_label = "Copy Matrix"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator('object.copy_matrix', text="Copy Transform")
        col.operator('object.paste_matrix', text="Paste Transform")


def render_constraint_stuff(self, context):
    if not context.active_object.constraints:
        return

    row = self.layout.row(align=True)
    row.prop_search(
        context.window_manager, 'disable_constraint',
        context.object, 'constraints',
        text='',
        icon='CONSTRAINT')
    row.operator(CONSTRAINT_OT_disable_without_moving.bl_idname)


classes = (
    OBJECT_OT_copy_matrix,
    OBJECT_OT_paste_matrix,
    VIEW3D_PT_copy_matrix,
)
register, unregister = bpy.utils.register_classes_factory(classes)
