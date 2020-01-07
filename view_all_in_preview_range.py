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

bl_info = {
    'name': 'View All in Preview Range',
    'author': 'Sybren A. Stüvel',
    'description': 'Similar to the View All option (the home key), except '
                   'that it only considers keyframes in the preview range.',
    'version': (1, 0),
    'blender': (2, 82, 0),
    'location': 'View menu in Graph Editor',
    'category': 'Animation',
    'support': 'COMMUNITY',
}

import math

import bpy

class GRAPH_OT_view_preview(bpy.types.Operator):
    bl_idname = 'graph.view_preview'
    bl_label = 'View All in Preview Range'

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            context.scene is not None
            and context.scene.use_preview_range
            and bool(getattr(context, 'editable_fcurves', False))
        )

    def execute(self, context: bpy.types.Context):
        min_value: float = float('inf')
        max_value: float = float('-inf')
        min_frame: float = context.scene.frame_preview_start
        max_frame: float = context.scene.frame_preview_end

        do_euler_scaling: bool = context.scene.unit_settings.system_rotation == 'DEGREES'

        for fcurve in context.editable_fcurves:
            do_scale_value: bool = do_euler_scaling and fcurve.data_path == 'rotation_euler'
            # print(f'FCurve: {fcurve.data_path}[{fcurve.array_index}] scaling: {do_scale_value}')

            for key in fcurve.keyframe_points:
                if not min_frame <= key.co.x <= max_frame:
                    continue

                if do_scale_value:
                    # World is using degrees, so the graph is drawn in degrees,
                    # but the value in the FCurve is still radians.
                    curve_value = math.degrees(key.co.y)
                else:
                    curve_value = key.co.y

                min_value = min(min_value, curve_value)
                max_value = max(max_value, curve_value)
        # print(f'Frame range: {min_frame} - {max_frame}')
        # print(f'Value range: {min_value:.2} - {max_value:.2}')

        # This is required as otherwise view_to_region() may have to deal with
        # out-of-view values, which it will return bogus values for.
        bpy.ops.graph.view_all()

        xmin, ymin = context.region.view2d.view_to_region(min_frame, min_value)
        xmax, ymax = context.region.view2d.view_to_region(max_frame, max_value)

        # Add a bit of margin.
        xmin -= 15
        xmax += 15
        ymin -= 15
        ymax += 20

        return bpy.ops.view2d.zoom_border(
            xmin=xmin, xmax=xmax,
            ymin=ymin, ymax=ymax,
            wait_for_input=False, zoom_out=False)


def draw_menu(self, context):
    self.layout.operator('graph.view_preview')

def register():
    bpy.types.GRAPH_MT_view.append(draw_menu)
    bpy.utils.register_class(GRAPH_OT_view_preview)


def unregister():
    bpy.utils.unregister_class(GRAPH_OT_view_preview)


if __name__ == "__main__":
    register()
