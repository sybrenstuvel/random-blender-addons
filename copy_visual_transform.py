#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

"""
Disable constraints without moving.

Really simple add-on for disabling constraints without moving the constrained object.
"""

bl_info = {
    'name': 'Copy Visual Transform',
    'author': 'Sybren A. Stüvel',
    'version': (1, 1),
    'blender': (2, 81, 0),
    'location': 'N-panel in the 3D Viewport',
    'category': 'Animation',
    'support': 'COMMUNITY',
}

from typing import Iterable, Optional, Set, Union

import bpy


class AutoKeying:
    """Auto-keying support.

    Based on Rigify code by Alexander Gavrilov.
    """

    @classmethod
    def keying_options(cls, context) -> Set[str]:
        """Retrieve the general keyframing options from user preferences."""

        prefs = context.preferences
        ts = context.scene.tool_settings
        options = set()

        if prefs.edit.use_visual_keying:
            options.add('INSERTKEY_VISUAL')
        if prefs.edit.use_keyframe_insert_needed:
            options.add('INSERTKEY_NEEDED')
        if prefs.edit.use_insertkey_xyz_to_rgb:
            options.add('INSERTKEY_XYZ_TO_RGB')
        if ts.use_keyframe_cycle_aware:
            options.add('INSERTKEY_CYCLE_AWARE')
        return options

    @classmethod
    def autokeying_options(cls, context) -> Optional[Set[str]]:
        """Retrieve the Auto Keyframe options, or None if disabled."""

        ts = context.scene.tool_settings

        if not ts.use_keyframe_insert_auto:
            return None

        if ts.use_keyframe_insert_keyingset:
            # No support for keying sets (yet).
            return None

        prefs = context.preferences
        options = cls.keying_options(context)

        if prefs.edit.use_keyframe_insert_available:
            options.add('INSERTKEY_AVAILABLE')
        if ts.auto_keying_mode == 'REPLACE_KEYS':
            options.add('INSERTKEY_REPLACE')
        return options

    @staticmethod
    def get_4d_rotlock(bone: bpy.types.PoseBone) -> Iterable[bool]:
        "Retrieve the lock status for 4D rotation."
        if bone.lock_rotations_4d:
            return [bone.lock_rotation_w, *bone.lock_rotation]
        else:
            return [all(bone.lock_rotation)] * 4

    @staticmethod
    def keyframe_channels(
            target: Union[bpy.types.Object, bpy.types.PoseBone],
            options: Set[str],
            data_path: str,
            group: str,
            locks: Iterable[bool],
        ) -> None:
        if all(locks):
            return

        if not any(locks):
            target.keyframe_insert(data_path, group=group, options=options)
            return

        for index, lock in enumerate(locks):
            if lock:
                continue
            target.keyframe_insert(data_path, index=index, group=group, options=options)

    @classmethod
    def key_transformation(
            cls,
            target: Union[bpy.types.Object, bpy.types.PoseBone],
            options: Set[str],
        ) -> None:
        """Keyframe transformation properties, avoiding keying locked channels."""

        is_bone = isinstance(target, bpy.types.PoseBone)
        if is_bone:
            group = target.name
        else:
            group = 'Object Transforms'

        def keyframe(data_path, locks):
            cls.keyframe_channels(target, options, data_path, group, locks)

        if not (is_bone and target.bone.use_connect):
            keyframe('location', target.lock_location)

        if target.rotation_mode == 'QUATERNION':
            keyframe('rotation_quaternion', cls.get_4d_rotlock(target))
        elif target.rotation_mode == 'AXIS_ANGLE':
            keyframe('rotation_axis_angle', cls.get_4d_rotlock(target))
        else:
            keyframe('rotation_euler', target.lock_rotation)

        keyframe('scale', target.lock_scale)

    @classmethod
    def autokey_transformation(cls, context, target: Union[bpy.types.Object, bpy.types.PoseBone]) -> None:
        """Auto-key transformation properties."""

        options = cls.autokeying_options(context)
        if options is None:
            return
        cls.key_transformation(target, options)


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
        AutoKeying.autokey_transformation(context, bone)
    else:
        context.active_object.matrix_world = mat
        AutoKeying.autokey_transformation(context, context.active_object)


class OBJECT_OT_copy_matrix(bpy.types.Operator):
    bl_idname = 'object.copy_matrix'
    bl_label = 'Copy matrix'
    bl_description = 'Copies the matrix of the currently active object or pose bone ' \
                     'to the clipboard. Uses world-space matrices'

    @classmethod
    def poll(cls, context) -> bool:
        return bool(context.active_pose_bone) or bool(context.active_object)

    def execute(self, context) -> Set[str]:
        context.window_manager.clipboard = repr(get_matrix(context))
        return {'FINISHED'}


class OBJECT_OT_paste_matrix(bpy.types.Operator):
    bl_idname = 'object.paste_matrix'
    bl_label = 'Paste matrix'
    bl_description = 'Pastes the matrix of the clipboard to the currently active pose bone ' \
                     'or object. Uses world-space matrices'

    @classmethod
    def poll(cls, context) -> bool:
        return bool(context.active_pose_bone) or bool(context.active_object)

    def execute(self, context) -> Set[str]:
        from mathutils import Matrix

        mat = eval(context.window_manager.clipboard, {}, {'Matrix': Matrix})
        set_matrix(context, mat)

        return {'FINISHED'}


class VIEW3D_PT_copy_matrix(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "View"
    bl_label = "Copy Matrix"

    def draw(self, context) -> None:
        layout = self.layout

        col = layout.column(align=True)
        col.operator('object.copy_matrix', text="Copy Transform")
        col.operator('object.paste_matrix', text="Paste Transform")


classes = (
    OBJECT_OT_copy_matrix,
    OBJECT_OT_paste_matrix,
    VIEW3D_PT_copy_matrix,
)
register, unregister = bpy.utils.register_classes_factory(classes)
