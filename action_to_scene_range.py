# SPDX-FileCopyrightText: 2024 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Action to Scene Range

When any Action is assigned to an object, update the Scene frame range to match
its length.
"""

bl_info = {
    "name": "Action to Scene Range",
    "author": "Sybren A. Stüvel",
    "version": (1, 1),
    "blender": (4, 1, 0),
    "location": "Automatic, no interface available",
    "category": "Animation",
    "support": 'COMMUNITY',
    "doc_url": "",
    "tracker_url": "",
}

from typing import Any

import bpy


class ACTION_OT_to_scene_range(bpy.types.Operator):
    bl_idname = "action.to_scene_range"
    bl_label = "Action to Scene Range"
    bl_description = "Set the Scene (preview) range to the Action's frame range"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.space_data.mode == 'ACTION' and bool(context.space_data.action)

    def execute(self, context: bpy.types.Context) -> set[str]:
        action = context.space_data.action
        scene = context.scene
        start, end = _action_to_scene_range(action, scene)

        self.report({'INFO'}, f"Changed scene range to {start}-{end}")

        return {'FINISHED'}


classes = (ACTION_OT_to_scene_range,)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def _action_to_scene_range(action: bpy.types.Action, scene: bpy.types.Scene) -> tuple[float, float]:
    action_range = tuple(action.frame_range)
    frame_start = int(action_range[0])
    frame_end = int(action_range[1])

    if scene.use_preview_range:
        scene.frame_preview_start = frame_start
        scene.frame_preview_end = frame_end
    else:
        scene.frame_start = frame_start
        scene.frame_end = frame_end

    return (frame_start, frame_end)


def _on_action_change() -> None:
    ob = bpy.context.object
    if not ob or not ob.animation_data:
        return
    action = ob.animation_data.action
    if not action:
        return

    frame_start, frame_end = _action_to_scene_range(action, bpy.context.scene)
    print(f"{ob.name} changed to action {action.name} with range {frame_start}-{frame_end}")


### Messagebus subscription to monitor changes & refresh panels.
_msgbus_owner = object()


def _register_message_bus() -> None:
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.SpaceDopeSheetEditor, "action"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_action_change,
        options={'PERSISTENT'},
    )


def _unregister_message_bus() -> None:
    bpy.msgbus.clear_by_owner(_msgbus_owner)


@bpy.app.handlers.persistent  # type: ignore
def _on_blendfile_load_post(none: Any, other_none: Any) -> None:
    # The parameters are required, but both are None.
    _register_message_bus()


def _draw_header_button(self, context) -> None:
    if context.space_data.mode != 'ACTION':
        return
    self.layout.operator("action.to_scene_range", text="", icon='PREVIEW_RANGE')


def _draw_panel_button(self, context) -> None:
    if context.space_data.mode != 'ACTION':
        return
    range_name = {
        False: 'Scene',
        True: 'Preview',
    }[context.scene.use_preview_range]
    self.layout.operator("action.to_scene_range", text=f"Action → {range_name} Range", icon='PREVIEW_RANGE')


def register():
    _register()
    _register_message_bus()
    bpy.app.handlers.load_post.append(_on_blendfile_load_post)
    bpy.types.DOPESHEET_HT_header.append(_draw_header_button)
    bpy.types.DOPESHEET_PT_action.append(_draw_panel_button)


def unregister():
    _unregister()
    _unregister_message_bus()
    bpy.app.handlers.load_post.remove(_on_blendfile_load_post)
    bpy.types.DOPESHEET_HT_header.remove(_draw_header_button)
    bpy.types.DOPESHEET_PT_action.remove(_draw_panel_button)
