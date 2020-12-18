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
Transform Helper

Simple add-on for help developing transform-related stuff.
"""

bl_info = {
    "name": "Transform Helper",
    "author": "Sybren A. Stüvel",
    "version": (1, 3),
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


class VIEW3D_PT_transform_helper(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_label = "Transform Helper"

    def draw(self, context: Context) -> None:
        layout = self.layout

        col = layout.column(align=True)
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
    POSE_OT_matrix_to_matrix_basis,
    VIEW3D_PT_transform_helper,
)
register, unregister = bpy.utils.register_classes_factory(classes)
