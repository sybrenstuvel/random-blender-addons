"""
Real pose copy addon.

Encodes the matrices of the selected bones in JSON, and places that on the
clipboard. This can be pasted as text into a text file, or, using this same
addon, pasted onto another rig in another Blend file. Bones are mapepd
by name.
"""

bl_info = {
    "name": "Real pose copy",
    "author": "Sybren A. Stüvel",
    "version": (1, 1),
    "blender": (2, 91, 0),
    "location": "3D View Numerical Panel > Pose Tools",
    "category": "Animation",
}

from collections import defaultdict, deque
import json
from typing import Dict, List, Set

import bpy
from mathutils import Matrix
from bpy.types import Menu, Panel, UIList

# Mapping {"bone_name": {"matrix": [4 lists of 4 floats]}}
ClipboardData = Dict[str, Dict[str, List[List[float]]]]


class POSE_OT_copy_as_json(bpy.types.Operator):
    bl_idname = "pose.copy_as_json"
    bl_label = "Copy pose as JSON"
    bl_description = (
        "Copies the matrices of the selected bones as JSON onto the clipboard"
    )
    bl_options = {"REGISTER"}  # No undo available for copying to the clipboard

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE" and context.selected_pose_bones

    def execute(self, context):
        bone_data: ClipboardData = defaultdict(dict)
        for bone in context.selected_pose_bones:
            # Convert matrix to list-of-tuples.
            vals = [list(v) for v in bone.matrix]
            bone_data[bone.name]["matrix"] = vals

        context.window_manager.clipboard = json.dumps(bone_data)
        self.report({"INFO"}, "Selected pose bone matrices copied.")

        return {"FINISHED"}


class POSE_OT_paste_from_json(bpy.types.Operator):
    bl_idname = "pose.paste_from_json"
    bl_label = "Paste pose from JSON"
    bl_description = (
        "Copies the matrices of the selected bones as JSON onto the clipboard"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "POSE"
            and context.active_object
            and context.active_object.type == "ARMATURE"
        )

    def execute(self, context):
        try:
            bone_data = self._parse_json(context.window_manager.clipboard)
        except ValueError as ex:
            self.report({"ERROR"}, "No valid JSON on clipboard: %s" % ex)
            return {"CANCELLED"}

        num_bones_in_json = len(bone_data)
        num_modified_bones = self._apply_matrices(bone_data, context.active_object)

        self.report(
            {"INFO"},
            "%s of %s pose bone matrices pasted."
            % (num_modified_bones, num_bones_in_json),
        )
        return {"FINISHED"}

    def _parse_json(self, the_json: str) -> ClipboardData:
        bone_data = json.loads(the_json)
        assert isinstance(bone_data, dict)
        return bone_data

    def _apply_matrices(
        self, bone_data: ClipboardData, arm_object: bpy.types.Object
    ) -> int:
        """
        Iterate over bones hierarchically, updating parents before children.

        :return: the number of modified bones.
        """

        pose: bpy.types.Pose = arm_object.pose

        # Collect all root bones.
        bones = deque(bone for bone in pose.bones if not bone.parent)

        # Walk the pose bones breadth-first.
        num_modified_bones = 0
        while bones:
            bone = bones.popleft()
            if self._apply_bone_matrix(bone_data, bone):
                num_modified_bones += 1
            bones.extend(bone.children)

        return num_modified_bones

    def _apply_bone_matrix(
        self,
        bone_data: ClipboardData,
        bone: bpy.types.PoseBone,
    ) -> bool:
        """Apply matrix from the clipboard.

        :return: True if applied, False if skipped.
        """

        try:
            matrix_components = bone_data[bone.name]["matrix"]
        except KeyError:
            return False  # This bone is not included in the pose JSON.

        bone.matrix = Matrix(matrix_components)
        return True


class VIEW3D_PT_pose_tools(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Clipboard"
    bl_label = "Copy Pose"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator("pose.copy_as_json", text="Copy as JSON")
        col.operator("pose.paste_from_json", text="Paste from JSON")


classes = (
    POSE_OT_copy_as_json,
    POSE_OT_paste_from_json,
    VIEW3D_PT_pose_tools,
)

register, unregister = bpy.utils.register_classes_factory(classes)
