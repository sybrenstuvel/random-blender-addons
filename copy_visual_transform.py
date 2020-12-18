# ====================== BEGIN GPL LICENSE BLOCK ======================
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
# ======================= END GPL LICENSE BLOCK ========================

"""
Copy Visual Transform

Simple add-on for copying world-space transforms.
"""

bl_info = {
    "name": "Copy Visual Transform",
    "author": "Sybren A. Stüvel",
    "version": (1, 4),
    "blender": (2, 91, 0),
    "location": "N-panel in the 3D Viewport",
    "category": "Animation",
    "support": "COMMUNITY",
}

import math
from typing import Dict, Iterable, Optional, Set, Tuple, Union

import bpy
from bpy.types import Context, Object, Operator, Panel, PoseBone
from mathutils import Matrix


class AutoKeying:
    """Auto-keying support.

    Based on Rigify code by Alexander Gavrilov.
    """

    @classmethod
    def keying_options(cls, context: Context) -> Set[str]:
        """Retrieve the general keyframing options from user preferences."""

        prefs = context.preferences
        ts = context.scene.tool_settings
        options = set()

        if prefs.edit.use_visual_keying:
            options.add("INSERTKEY_VISUAL")
        if prefs.edit.use_keyframe_insert_needed:
            options.add("INSERTKEY_NEEDED")
        if prefs.edit.use_insertkey_xyz_to_rgb:
            options.add("INSERTKEY_XYZ_TO_RGB")
        if ts.use_keyframe_cycle_aware:
            options.add("INSERTKEY_CYCLE_AWARE")
        return options

    @classmethod
    def autokeying_options(cls, context: Context) -> Optional[Set[str]]:
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
            options.add("INSERTKEY_AVAILABLE")
        if ts.auto_keying_mode == "REPLACE_KEYS":
            options.add("INSERTKEY_REPLACE")
        return options

    @staticmethod
    def get_4d_rotlock(bone: PoseBone) -> Iterable[bool]:
        "Retrieve the lock status for 4D rotation."
        if bone.lock_rotations_4d:
            return [bone.lock_rotation_w, *bone.lock_rotation]
        else:
            return [all(bone.lock_rotation)] * 4

    @staticmethod
    def keyframe_channels(
        target: Union[Object, PoseBone],
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
        target: Union[Object, PoseBone],
        options: Set[str],
    ) -> None:
        """Keyframe transformation properties, avoiding keying locked channels."""

        is_bone = isinstance(target, PoseBone)
        if is_bone:
            group = target.name
        else:
            group = "Object Transforms"

        def keyframe(data_path: str, locks: Iterable[bool]) -> None:
            cls.keyframe_channels(target, options, data_path, group, locks)

        if not (is_bone and target.bone.use_connect):
            keyframe("location", target.lock_location)

        if target.rotation_mode == "QUATERNION":
            keyframe("rotation_quaternion", cls.get_4d_rotlock(target))
        elif target.rotation_mode == "AXIS_ANGLE":
            keyframe("rotation_axis_angle", cls.get_4d_rotlock(target))
        else:
            keyframe("rotation_euler", target.lock_rotation)

        keyframe("scale", target.lock_scale)

    @classmethod
    def autokey_transformation(
        cls, context: Context, target: Union[Object, PoseBone]
    ) -> None:
        """Auto-key transformation properties."""

        options = cls.autokeying_options(context)
        if options is None:
            return
        cls.key_transformation(target, options)


def get_matrix(context: Context) -> Matrix:
    bone = context.active_pose_bone
    if bone:
        # Convert matrix to world space
        arm = context.active_object
        mat = arm.matrix_world @ bone.matrix
    else:
        mat = context.active_object.matrix_world

    return mat


def set_matrix(context: Context, mat: Matrix) -> None:
    bone = context.active_pose_bone
    if bone:
        # Convert matrix to local space
        arm_eval = context.active_object.evaluated_get(context.view_layer.depsgraph)
        bone.matrix = arm_eval.matrix_world.inverted() @ mat
        AutoKeying.autokey_transformation(context, bone)
    else:
        context.active_object.matrix_world = mat
        AutoKeying.autokey_transformation(context, context.active_object)


class OBJECT_OT_copy_visual_transform(Operator):
    bl_idname = "object.copy_visual_transform"
    bl_label = "Copy Visual Transform"
    bl_description = (
        "Copies the matrix of the currently active object or pose bone "
        "to the clipboard. Uses world-space matrices"
    )
    bl_options = {"REGISTER"}  # This operator cannot be un-done.

    @classmethod
    def poll(cls, context: Context) -> bool:
        return bool(context.active_pose_bone) or bool(context.active_object)

    def execute(self, context: Context) -> Set[str]:
        mat = get_matrix(context)
        rows = [f"            {tuple(row)!r}," for row in mat]
        as_string = "\n".join(rows)
        context.window_manager.clipboard = f"Matrix((\n{as_string}\n        ))"
        return {"FINISHED"}


class OBJECT_OT_paste_transform(Operator):
    bl_idname = "object.paste_transform"
    bl_label = "Paste Transform"
    bl_description = (
        "Pastes the matrix from the clipboard to the currently active pose bone "
        "or object. Uses world-space matrices"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return bool(context.active_pose_bone) or bool(context.active_object)

    @staticmethod
    def parse_print_m4(value: str) -> Optional[Matrix]:
        """Parse output from Blender's print_m4() function.

        Expects four lines of space-separated floats.
        """

        lines = value.strip().splitlines()
        if len(lines) != 4:
            return None

        floats = tuple(tuple(float(item) for item in line.split()) for line in lines)
        return Matrix(floats)

    def execute(self, context: Context) -> Set[str]:
        clipboard = context.window_manager.clipboard
        if clipboard.startswith("Matrix"):
            mat = eval(clipboard, {}, {"Matrix": Matrix})
        else:
            mat = self.parse_print_m4(clipboard)

        if mat is None:
            self.report({"ERROR"}, "Clipboard does not contain a valid matrix.")
            return {"CANCELLED"}

        set_matrix(context, mat)

        return {"FINISHED"}


class VIEW3D_PT_copy_visual_transform(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_label = "Visual Transform"

    def draw(self, context: Context) -> None:
        layout = self.layout

        col = layout.column(align=True)
        col.operator("object.copy_visual_transform")
        col.operator("object.paste_transform")


classes = (
    OBJECT_OT_copy_visual_transform,
    OBJECT_OT_paste_transform,
    VIEW3D_PT_copy_visual_transform,
)
register, unregister = bpy.utils.register_classes_factory(classes)
