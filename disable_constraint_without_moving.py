"""
Disable constraints without moving.

Really simple add-on for disabling constraints without moving the constrained object.
"""

bl_info = {
    'name': 'Disable constraint without moving',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (2, 78, 0),
    'location': 'Constraints panel',
    'category': 'Animation',
    'support': 'COMMUNITY',
    'warning': 'This is a quickly hacked-together add-on. Let me know if it works for you.',
}

import bpy


class OBJECT_OT_copy_matrix(bpy.types.Operator):
    bl_idname = 'object.copy_matrix'
    bl_label = 'Copy matrix'
    bl_description = 'Copies the matrix of the currently active object or pose bone ' \
                     'to the clipboard. Uses world-space matrices'

    @classmethod
    def poll(cls, context):
        return bool(context.active_pose_bone) or bool(context.active_object)

    @staticmethod
    def copy_matrix(context):
        bone = context.active_pose_bone
        if bone:
            # Convert matrix to world space
            arm = context.active_object
            mat = arm.matrix_world * bone.matrix
        else:
            mat = context.active_object.matrix_world

        return mat

    def execute(self, context):
        context.window_manager.clipboard = repr(self.copy_matrix(context))
        return {'FINISHED'}


class OBJECT_OT_paste_matrix(bpy.types.Operator):
    bl_idname = 'object.paste_matrix'
    bl_label = 'Paste matrix'
    bl_description = 'Pastes the matrix of the clipboard to the currently active pose bone ' \
                     'or object. Uses world-space matrices'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.active_pose_bone) or bool(context.active_object)

    @staticmethod
    def paste_matrix(context, mat):
        bone = context.active_pose_bone
        if bone:
            # Convert matrix to local space
            arm = context.active_object
            bone.matrix = arm.matrix_world.inverted() * mat
        else:
            context.active_object.matrix_world = mat

    def execute(self, context):
        from mathutils import Matrix

        mat = eval(context.window_manager.clipboard, {}, {'Matrix': Matrix})
        self.paste_matrix(context, mat)

        return {'FINISHED'}


class CONSTRAINT_OT_disable_without_moving(bpy.types.Operator):
    bl_idname = 'constraint.disable_without_moving'
    bl_label = 'Disable constraint without moving'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (OBJECT_OT_paste_matrix.poll(context)
                and OBJECT_OT_copy_matrix.poll(context)
                and context.window_manager.disable_constraint in context.active_object.constraints)

    def execute(self, context):
        mat = OBJECT_OT_copy_matrix.copy_matrix(context)
        context.active_object.constraints[context.window_manager.disable_constraint].influence = 0.0
        OBJECT_OT_paste_matrix.paste_matrix(context, mat)

        return {'FINISHED'}


def render_constraint_stuff(self, context):
    if not context.active_object.constraints:
        return

    row = self.layout.row(align=True)
    row.prop_search(
        context.window_manager, 'disable_constraint',
        context.object, 'constraints',
        text='')
    row.operator(CONSTRAINT_OT_disable_without_moving.bl_idname)


def register():
    bpy.types.WindowManager.disable_constraint = bpy.props.StringProperty()

    bpy.utils.register_class(OBJECT_OT_copy_matrix)
    bpy.utils.register_class(OBJECT_OT_paste_matrix)
    bpy.utils.register_class(CONSTRAINT_OT_disable_without_moving)
    bpy.types.OBJECT_PT_constraints.append(render_constraint_stuff)


def unregister():
    del bpy.types.WindowManager.disable_constraint

    bpy.utils.unregister_class(OBJECT_OT_copy_matrix)
    bpy.utils.unregister_class(OBJECT_OT_paste_matrix)
    bpy.utils.unregister_class(CONSTRAINT_OT_disable_without_moving)
    bpy.types.OBJECT_PT_constraints.remove(render_constraint_stuff)
