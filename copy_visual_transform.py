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
Disable constraints without moving.

Really simple add-on for disabling constraints without moving the constrained object.
"""

bl_info = {
    "name": "Copy Visual Transform",
    "author": "Sybren A. Stüvel",
    "version": (1, 3),
    "blender": (2, 81, 0),
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


class OBJECT_OT_copy_matrix(Operator):
    bl_idname = "object.copy_matrix"
    bl_label = "Copy matrix"
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


class OBJECT_OT_paste_matrix(Operator):
    bl_idname = "object.paste_matrix"
    bl_label = "Paste matrix"
    bl_description = (
        "Pastes the matrix of the clipboard to the currently active pose bone "
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


class POSE_OT_matrix_to_matrix_basis(Operator):
    bl_idname = "pose.matrix_to_matrix_basis"
    bl_label = "Bake Selected Bones"
    bl_description = "Copy the evaluated transform to the local transform of selected pose bones, and disable constraints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return bool(context.selected_pose_bones)

    def execute(self, context: Context) -> Set[str]:
        matrices = self.matrices_to_bake(context.selected_pose_bones)
        self.disable_constraints(context.selected_pose_bones)
        self.set_matrices(context.pose_object, matrices)
        return {"FINISHED"}

    def matrices_to_bake(
        self, selected_pose_bones: Iterable[PoseBone]
    ) -> Dict[str, Matrix]:
        matrices: Dict[str, Matrix] = {}

        print("\033[95mGetting matrices\033[0m")
        for pbone in selected_pose_bones:
            print(f"    {pbone.name}")
            print(f"{pbone.matrix!r}")

            if pbone.parent:
                world_to_parent = pbone.parent.matrix.inverted_safe()
            else:
                world_to_parent = Matrix.Rotation(-math.radians(90), 4, "X")
            matrices[pbone.name] = world_to_parent @ pbone.matrix

        return matrices

    def disable_constraints(self, selected_pose_bones: Iterable[PoseBone]) -> None:
        print("Disabling constraints")
        for pbone in selected_pose_bones:
            for constraint in pbone.constraints:
                print(f"    {pbone.name}: {constraint.name}")
                constraint.mute = True

    def set_matrices(self, pose_object: Object, matrices: Dict[str, Matrix]) -> None:
        print("Setting mone matrices")
        for bone_name, matrix in matrices.items():
            print(f"    {bone_name}")
            pose_object.pose.bones[bone_name].matrix_basis = matrix


class VIEW3D_PT_copy_matrix(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Clipboard"
    bl_label = "Copy Matrix"

    def draw(self, context: Context) -> None:
        layout = self.layout

        col = layout.column(align=True)
        col.operator("object.copy_matrix", text="Copy Transform")
        col.operator("object.paste_matrix", text="Paste Transform")
        col.operator("pose.matrix_to_matrix_basis")

        if context.object:
            self.draw_evaluated_transform(context)
            self.draw_rotations(context)

    @staticmethod
    def nicenum(num: float) -> str:
        if abs(num) < 1e-3:
            return "-"
        return f"{num:.3f}"

    @staticmethod
    def nicescale(num: float) -> str:
        if abs(1.0 - num) < 1e-3:
            return "-"
        return f"{num:.3f}"

    def draw_decomposed_matrix(self, label: str, matrix: Matrix) -> None:
        (trans, rot, scale) = matrix.decompose()

        col = self.layout.column(align=False)
        col.label(text=label)

        grid = col.grid_flow(row_major=True, columns=4, align=True)
        grid.label(text="T")
        grid.label(text=self.nicenum(trans.x))
        grid.label(text=self.nicenum(trans.y))
        grid.label(text=self.nicenum(trans.z))
        grid.label(text="R")
        grid.label(text=self.nicenum(rot.x))
        grid.label(text=self.nicenum(rot.y))
        grid.label(text=self.nicenum(rot.z))
        grid.label(text="S")
        grid.label(text=self.nicescale(scale.x))
        grid.label(text=self.nicescale(scale.y))
        grid.label(text=self.nicescale(scale.z))

    def draw_evaluated_transform(self, context: Context) -> None:
        depsgraph = context.evaluated_depsgraph_get()
        ob_eval = context.object.evaluated_get(depsgraph)

        if ob_eval.mode == "OBJECT":
            self.draw_decomposed_matrix("Evaluated Transform:", ob_eval.matrix_world)
            self.draw_decomposed_matrix(
                "Parent Inverse:", ob_eval.matrix_parent_inverse
            )

        if context.active_pose_bone:
            bone = context.active_pose_bone
            self.draw_decomposed_matrix(f"{bone.name} matrix:", bone.matrix)
            self.draw_decomposed_matrix(f"{bone.name} matrix_basis:", bone.matrix_basis)

    def draw_rotations(self, context: Context) -> None:
        ob = context.object

        col = self.layout.column(align=False)
        col.label(text="Rotation")

        grid = col.grid_flow(row_major=True, columns=5, align=True)
        grid.label(text="E")
        grid.label(text="")
        grid.label(text=self.nicenum(ob.rotation_euler.x))
        grid.label(text=self.nicenum(ob.rotation_euler.y))
        grid.label(text=self.nicenum(ob.rotation_euler.z))

        q = ob.rotation_euler.to_quaternion()
        grid.label(text="Q")
        grid.label(text=self.nicenum(q.w))
        grid.label(text=self.nicenum(q.x))
        grid.label(text=self.nicenum(q.y))
        grid.label(text=self.nicenum(q.z))

        axis, angle = q.to_axis_angle()
        grid.label(text="AA")
        grid.label(text=self.nicenum(math.degrees(angle)))
        grid.label(text=self.nicenum(axis.x))
        grid.label(text=self.nicenum(axis.y))
        grid.label(text=self.nicenum(axis.z))


classes = (
    OBJECT_OT_copy_matrix,
    OBJECT_OT_paste_matrix,
    POSE_OT_matrix_to_matrix_basis,
    VIEW3D_PT_copy_matrix,
)
register, unregister = bpy.utils.register_classes_factory(classes)
