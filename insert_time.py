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

import bpy
bl_info = {
    'name': 'Insert Time',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (2, 82, 0),
    'location': 'Graph Editor and Dope Sheet, Channel menu',
    'category': 'Animation',
    'support': 'COMMUNITY',
}


def insert_time(context: bpy.types.Context, frame_count: int):
    """Insert time by moving frames to the right."""

    playhead = context.scene.frame_current
    for fcurve in context.selected_editable_fcurves:
        for kp in reversed(fcurve.keyframe_points):
            if kp.co.x < playhead:
                break
            kp.co.x += frame_count
            kp.handle_left.x += frame_count
            kp.handle_right.x += frame_count
        fcurve.update()


class GRAPH_OT_insert_time(bpy.types.Operator):
    """Insert time into selected channels, by pushing keys after the playhead to the right"""
    bl_idname = "graph.insert_time"
    bl_label = "Insert Time"
    bl_options = {'REGISTER', 'UNDO'}

    frame_count: bpy.props.IntProperty(
        name='Number of Frames', default=1, min=0)

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'selected_editable_fcurves') and len(context.selected_editable_fcurves)

    def execute(self, context):
        insert_time(context, self.frame_count)
        return {'FINISHED'}


def draw_menu(self, context):
    self.layout.operator(GRAPH_OT_insert_time.bl_idname)


def register():
    bpy.utils.register_class(GRAPH_OT_insert_time)
    bpy.types.GRAPH_MT_channel.append(draw_menu)


def unregister():
    bpy.types.GRAPH_MT_channel.remove(draw_menu)
    bpy.utils.unregister_class(GRAPH_OT_insert_time)


if __name__ == "__main__":
    register()
