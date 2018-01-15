# ##### BEGIN GPL LICENSE BLOCK #####
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
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

bl_info = {
    "name": "Kwiq Video Editor",
    "author": "Sybren A. Stüvel",
    "version": (0, 2, 0),
    "blender": (2, 79, 0),
    "location": "Video Sequence Editor",
    "description":
        "Easily edit videos based on highlights in your source material.",
    "category": "Videos",
    "support": "COMMUNITY"
}

import contextlib
import functools
import logging
import typing

import bpy
import idprop
from bpy.types import Operator, Panel, AddonPreferences, Sequence

log = logging.getLogger(__name__)
cb_handle = None


def active_strip(context) -> typing.Optional[Sequence]:
    try:
        return context.scene.sequence_editor.active_strip
    except AttributeError:
        return None


def shown_strips(context) -> bpy.types.Sequences:
    """Returns the strips from the current meta-strip-stack, or top-level strips.

    What is returned depends on what the user is currently editing.
    """

    if context.scene.sequence_editor.meta_stack:
        return context.scene.sequence_editor.meta_stack[-1].sequences

    return context.scene.sequence_editor.sequences


def highlights(strip: Sequence) -> typing.Union[idprop.types.IDPropertyArray, list]:
    """Get the highlights for the given sequencer strip."""
    try:
        return strip["kwiq_highlights"]
    except KeyError:
        return []


def add_highlight(strip: Sequence, abs_frame: int):
    """Compute the frame relative to the start of the strip and store it."""

    rel_frame = abs_to_rel(strip, abs_frame)

    hl = set(highlights(strip))
    hl.add(rel_frame)
    strip["kwiq_highlights"] = sorted(hl)
    tag_redraw_all_sequencer_editors()


def abs_to_rel(strip: Sequence, abs_frame: int) -> int:
    """Convert absolute frame to strip-source-relative frame number."""

    return abs_frame - strip.frame_start


def rel_to_abs(strip: Sequence, rel_frame: int) -> int:
    """Convert strip-source-relative frame number to absolute frame."""

    return rel_frame + strip.frame_start


class KWIQ_PT_tools(Panel):
    bl_idname = 'kwiq.tools'
    bl_label = 'Kwiq'
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Kwiq'

    @classmethod
    def poll(cls, context):
        return context.space_data.view_type in {'SEQUENCER', 'SEQUENCER_PREVIEW'}

    def draw(self, context):
        strip = active_strip(context)
        layout = self.layout

        if not strip:
            layout.label('No active strip')
            return

        if "kwiq_highlights" in strip and strip["kwiq_highlights"]:
            layout.label("%d highlights." % len(strip["kwiq_highlights"]))
        else:
            layout.label("No highlights defined yet.")
        layout.operator('kwiq.add_highlight')


class KwiqOperatorMixin:
    """Mix-in class for all Kwiq operators."""

    @classmethod
    def poll(cls, context):
        return bool(active_strip(context))


class KWIQ_OT_add_highlight(KwiqOperatorMixin, Operator):
    bl_idname = "kwiq.add_highlight"
    bl_label = "Add Highlight"
    bl_description = 'Mark the current frame as highlight for this strip'

    def execute(self, context):
        strip = active_strip(context)
        frame = context.scene.frame_current
        add_highlight(strip, frame)
        return {'FINISHED'}


def tag_redraw_all_sequencer_editors():
    context = bpy.context

    # Py cant access notifiers
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'SEQUENCE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()


def get_strip_rectf(strip) -> (float, float, float, float):
    """Get x and y in terms of the grid's frames and channels."""
    x1 = strip.frame_final_start
    x2 = strip.frame_final_end
    y1 = strip.channel + 0.2
    y2 = strip.channel - 0.2 + 1

    return x1, y1, x2, y2


def draw_callback_px():
    import bgl

    context = bpy.context

    if not context.scene.sequence_editor:
        return

    strips = shown_strips(context)
    if not strips:
        return

    region = context.region
    xwin1, ywin1 = region.view2d.region_to_view(0, 0)
    xwin2, ywin2 = region.view2d.region_to_view(region.width, region.height)
    one_pixel_further_x, one_pixel_further_y = region.view2d.region_to_view(1, 1)
    pixel_size_x = one_pixel_further_x - xwin1

    bgl.glPushAttrib(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_LINE_BIT)
    bgl.glColor4f(1.0, 1.0, 0.0, 1.0)
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glLineWidth(2)

    bgl.glBegin(bgl.GL_LINES)
    for strip in strips:
        hl = highlights(strip)
        if not hl:
            continue

        # Get corners (x1, y1), (x2, y2) of the strip rectangle in px region coords
        strip_coords = get_strip_rectf(strip)

        # check if any of the coordinates are out of bounds
        if strip_coords[0] > xwin2 or strip_coords[2] < xwin1 or strip_coords[1] > ywin2 or \
                        strip_coords[3] < ywin1:
            continue

        # Draw
        for rel_frame in hl:
            abs_frame = rel_to_abs(strip, rel_frame)
            bgl.glVertex2f(abs_frame, strip_coords[1])
            bgl.glVertex2f(abs_frame, strip_coords[3])
    bgl.glEnd()
    bgl.glPopAttrib()


def draw_callback_enable():
    global cb_handle

    if cb_handle is not None:
        return

    cb_handle = bpy.types.SpaceSequenceEditor.draw_handler_add(
        draw_callback_px, (), 'WINDOW', 'POST_VIEW')
    tag_redraw_all_sequencer_editors()


def draw_callback_disable():
    global cb_handle

    if cb_handle is None:
        return

    try:
        bpy.types.SpaceSequenceEditor.draw_handler_remove(cb_handle, 'WINDOW')
    except ValueError:
        # Thrown when already removed.
        pass
    cb_handle = None
    tag_redraw_all_sequencer_editors()


def register():
    bpy.utils.register_class(KWIQ_PT_tools)
    bpy.utils.register_class(KWIQ_OT_add_highlight)
    draw_callback_enable()


def unregister():
    draw_callback_disable()
    bpy.utils.unregister_module(__name__)
