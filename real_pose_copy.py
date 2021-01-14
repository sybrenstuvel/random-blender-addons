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

import base64
import bz2
import json
from collections import defaultdict, deque
from typing import Any, Dict, List, Set, Tuple, Union, cast

import bpy
from mathutils import Matrix
from bpy.props import EnumProperty
from bpy.types import Menu, Panel, UIList

# Matrix as 4 tuples of 4 floats, or as string 'I' for identity.
JSONMatrix = Union[Tuple[Tuple[float]], str]
# {"matrix": JSONMatrix, "matrix_basis": JSONMatrix}
BoneData = Dict[str, JSONMatrix]
# Mapping {"bone_name": BoneData}
ClipboardData = Dict[str, BoneData]


class JSONEncoder(json.encoder.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Matrix):
            return self.encode_matrix(o)
        return super().default(o)

    def encode_matrix(self, matrix: Matrix) -> JSONMatrix:
        if matrix == Matrix.Identity(4):
            return "I"
        json_matrix = tuple(tuple(row) for row in matrix)
        return cast(JSONMatrix, json_matrix)

    @staticmethod
    def decode_matrix(json_value: JSONMatrix) -> Matrix:
        if json_value == "I":
            return Matrix.Identity(4)
        return Matrix(json_value)

    @staticmethod
    def compress(json_data: str) -> str:
        """Compress the JSON data to roughly 1/2 or 1/3 the original size."""
        data = base64.b64encode(bz2.compress(json_data.encode(), 9))
        return "POSE-" + data.decode("ASCII") + "-POSE"

    @staticmethod
    def decompress(clipboard_data: str) -> str:
        """Decompress the clipboard to a JSON string."""

        # Strip off the "POSE-" prefix and suffix. The poll() function already
        # checks the prefix, and the suffix is just assumed to be there.
        compressed = clipboard_data[5:-5]
        decompressed = bz2.decompress(base64.b64decode(compressed))
        return decompressed.decode()


class POSE_OT_copy_as_json(bpy.types.Operator):
    bl_idname = "pose.copy_as_json"
    bl_label = "Copy Pose"
    bl_description = "Copies the matrices of the selected bones as compressed JSON onto the clipboard"
    bl_options = {"REGISTER"}  # No undo available for copying to the clipboard

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE" and context.selected_pose_bones

    def execute(self, context):
        bone_data: ClipboardData = defaultdict(dict)
        for bone in context.selected_pose_bones:
            bone_data[bone.name]["matrix"] = bone.matrix
            bone_data[bone.name]["matrix_basis"] = bone.matrix_basis

        json_data = json.dumps(bone_data, cls=JSONEncoder)
        context.window_manager.clipboard = JSONEncoder.compress(json_data)
        self.report({"INFO"}, "Selected pose bone matrices copied.")

        return {"FINISHED"}


class POSE_OT_paste_from_json(bpy.types.Operator):
    bl_idname = "pose.paste_from_json"
    bl_label = "Paste Pose"
    bl_description = "Copies the matrices of the selected bones as compressed JSON onto the clipboard"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(  # type: ignore
        name="Target",
        items=[
            ("LOCAL", "Local Matrix", "Copy the local rot/loc/scale as matrix"),
            (
                "WORLD",
                "World Matrix",
                "Copy-pasting can still change the pose when constraints are in use",
            ),
        ],
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "POSE"
            and context.active_object
            and context.active_object.type == "ARMATURE"
            and context.window_manager.clipboard.startswith("POSE-")
        )

    def execute(self, context):
        try:
            json_data = JSONEncoder.decompress(context.window_manager.clipboard)
            bone_data = self._parse_json(json_data)
        except ValueError as ex:
            self.report({"ERROR"}, "No valid JSON on clipboard: %s" % ex)
            return {"CANCELLED"}

        num_bones_in_json = len(bone_data)
        num_modified_bones = self._apply_matrices(
            bone_data, context.active_object, context.active_pose_bone
        )

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
        self,
        clipboard_data: ClipboardData,
        arm_object: bpy.types.Object,
        active_pose_bone: bpy.types.PoseBone,
    ) -> int:
        """
        Iterate over bones hierarchically, updating parents before children.

        :return: the number of modified bones.
        """

        apply_func = {
            "LOCAL": self._apply_bone_matrix_local,
            "WORLD": self._apply_bone_matrix_world,
        }[self.target]

        if len(clipboard_data) == 1:
            # Only one bone is pasted. Just paste it to the active pose bone, ignoring the name.
            bone_data = tuple(clipboard_data.values())[0]
            if apply_func(bone_data, active_pose_bone):
                return 1
            return 0

        # Collect all root bones.
        pose: bpy.types.Pose = arm_object.pose
        bones = deque(bone for bone in pose.bones if not bone.parent)

        # Walk the pose bones breadth-first.
        num_modified_bones = 0
        while bones:
            bone = bones.popleft()

            try:
                bone_data = clipboard_data[bone.name]
            except KeyError:
                pass
            else:
                if apply_func(bone_data, bone):
                    num_modified_bones += 1

            bones.extend(bone.children)

        return num_modified_bones

    def _apply_bone_matrix_local(
        self,
        bone_data: BoneData,
        bone: bpy.types.PoseBone,
    ) -> bool:
        """Apply matrix_basis from the clipboard.

        :return: True if applied, False if skipped.
        """

        try:
            json_value = bone_data["matrix_basis"]
        except KeyError:
            return False

        bone.matrix_basis = JSONEncoder.decode_matrix(json_value)
        return True

    def _apply_bone_matrix_world(
        self,
        bone_data: BoneData,
        bone: bpy.types.PoseBone,
    ) -> bool:
        """Apply matrix from the clipboard.

        :return: True if applied, False if skipped.
        """

        try:
            json_value = bone_data["matrix"]
        except KeyError:
            return False

        bone.matrix = JSONEncoder.decode_matrix(json_value)
        return True


class VIEW3D_PT_pose_tools(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_label = "Copy Pose"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator("pose.copy_as_json", text="Copy as JSON", icon="COPYDOWN")
        col.operator(
            "pose.paste_from_json", text="Paste Local", icon="PASTEDOWN"
        ).target = "LOCAL"
        col.operator(
            "pose.paste_from_json", text="Paste World", icon="PASTEDOWN"
        ).target = "WORLD"


classes = (
    POSE_OT_copy_as_json,
    POSE_OT_paste_from_json,
    VIEW3D_PT_pose_tools,
)

register, unregister = bpy.utils.register_classes_factory(classes)
