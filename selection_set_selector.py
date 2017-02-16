bl_info = {
    'name': 'Selection Set Selector',
    'author': 'Dr. Sybren',
    'version': (1, 0),
    'blender': (2, 78, 0),
    'location': 'View3D > Pose > Show/Hide > Show Single Selection Set, or Ctrl+Alt+W',
    'description': 'In pose mode, when pressing Ctrl+Alt+W, a menu is shown to select a '
                   'Selection Set. All bones in this Selection Set are shown, the rest is '
                   'hidden. Hidden bones are also deselected.',
    'category': 'Animation',
}


import bpy
from bpy.types import Operator, Menu
from bpy.props import StringProperty


class POSE_OT_select_selection_set(Operator):
    bl_idname = 'post.select_selection_set'
    bl_label = 'Select Selection Set'
    bl_options = {'UNDO', 'REGISTER'}

    selection_set_name = StringProperty(name='Selection Set Name')

    @classmethod
    def poll(cls, context):
        return (context.object
                and context.mode == 'POSE'
                and context.object.type == 'ARMATURE'
                and context.object.pose
                and len(context.object.selection_sets) > 0)

    def execute(self, context):
        arm = context.object
        sel_set = arm.selection_sets[self.selection_set_name]

        for bone in context.visible_pose_bones:
            if bone.name in sel_set.bone_ids:
                 bone.bone.select = True

        return {'FINISHED'}


class POSE_OT_select_selection_set_call_menu(Operator):
    bl_idname = 'pose.select_selection_set_call_menu'
    bl_label = 'Show Single Selection Set'

    def execute(self, context):
        context.window_manager.popup_menu(drawmenu)
        return {'FINISHED'}


class POSE_MT_selection_sets(Menu):
    bl_label = POSE_OT_select_selection_set.bl_label
    poll = POSE_OT_select_selection_set.poll

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        for ss in context.object.selection_sets:
            props = layout.operator(POSE_OT_select_selection_set.bl_idname, text=ss.name)
            props.selection_set_name = ss.name


def add_ssss_button(self, context):
    self.layout.menu('POSE_MT_selection_sets')


def register():
    bpy.utils.register_class(POSE_OT_select_selection_set)
    bpy.utils.register_class(POSE_OT_select_selection_set_call_menu)
    bpy.utils.register_class(POSE_MT_selection_sets)

    wm = bpy.context.window_manager
    km = wm.keyconfigs.active.keymaps['Pose']

    kmi = km.keymap_items.new('wm.call_menu', 'W', 'PRESS', alt=True, shift=True)
    kmi.properties.name = 'POSE_MT_selection_sets'

    bpy.types.VIEW3D_MT_pose_showhide.append(add_ssss_button)


def unregister():
    bpy.utils.unregister_class(POSE_OT_select_selection_set)
    bpy.utils.unregister_class(POSE_OT_select_selection_set_call_menu)
    bpy.utils.unregister_class(POSE_MT_selection_sets)
    bpy.types.VIEW3D_MT_pose_showhide.remove(add_ssss_button)


if __name__ == "__main__":
    register()
