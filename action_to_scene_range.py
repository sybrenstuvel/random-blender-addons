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
    "version": (1, 0),
    "blender": (4, 1, 0),
    "location": "Automatic, no interface available",
    "category": "Animation",
    "support": 'COMMUNITY',
    "doc_url": "",
    "tracker_url": "",
}

from typing import Any

import bpy


# classes = (
# )
# _register, _unregister = bpy.utils.register_classes_factory(classes)


def _action_to_scene_range():
    ob = bpy.context.object
    if not ob or not ob.animation_data:
        return
    action = ob.animation_data.action
    if not action:
        return

    if action.use_frame_range:
        frame_start = int(action.frame_start)
        frame_end = int(action.frame_end)
    else:
        action_range = tuple(action.frame_range)
        frame_start = int(action_range[0])
        frame_end = int(action_range[1])

    print(f"{ob.name} changed to action {action.name} with range {frame_start}-{frame_end}")

    scene = bpy.context.scene
    if scene.use_preview_range:
        scene.frame_preview_start = frame_start
        scene.frame_preview_end = frame_end
    else:
        scene.frame_start = frame_start
        scene.frame_end = frame_end


### Messagebus subscription to monitor changes & refresh panels.
_msgbus_owner = object()


def _register_message_bus() -> None:
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.SpaceDopeSheetEditor, "action"),
        owner=_msgbus_owner,
        args=(),
        notify=_action_to_scene_range,
        options={'PERSISTENT'},
    )


def _unregister_message_bus() -> None:
    bpy.msgbus.clear_by_owner(_msgbus_owner)


@bpy.app.handlers.persistent  # type: ignore
def _on_blendfile_load_post(none: Any, other_none: Any) -> None:
    # The parameters are required, but both are None.
    _register_message_bus()


def register():
    # _register()
    _register_message_bus()
    bpy.app.handlers.load_post.append(_on_blendfile_load_post)


def unregister():
    # _unregister()
    _unregister_message_bus()
    bpy.app.handlers.load_post.remove(_on_blendfile_load_post)
