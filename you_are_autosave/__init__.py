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

import time

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

bl_info = {
    'name': 'You Are Autosave',
    'author': 'Sybren A. Stüvel',
    'description': "Show a warning when you haven't saved in a while",
    'version': (1, 3, 0),
    'blender': (3, 6, 0),
    'location': 'Somewhere',
    'category': 'System',
    'support': 'COMMUNITY',
}


last_save_timestamp: float = float("-inf")
check_interval_in_sec = 1
line_thickness = 4.0

draw_handle: object = None


def secs_since_last_save() -> float:
    return time.monotonic() - last_save_timestamp


def prefs() -> "YouAreAutosavePreferences":
    return bpy.context.preferences.addons[__package__].preferences


def start_nagging_in_sec() -> float:
    return float(prefs().nag_start_time * 60)


def full_problem_after_sec() -> float:
    return float(prefs().full_problem_time * 60)


def check_last_save_timestamp() -> float:
    if not prefs().include_unsaved and not bpy.data.filepath:
        clear_warning()
        return check_interval_in_sec

    secs_since_save = secs_since_last_save()
    if secs_since_save <= start_nagging_in_sec() or not bpy.data.is_dirty:
        clear_warning()
        return check_interval_in_sec

    show_warning()

    # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    for area in bpy.context.window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        area.tag_redraw()

    if secs_since_save < 300:
        return 0.1
    return 1


def show_warning():
    global draw_handle

    if draw_handle is not None:
        return

    draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (), 'WINDOW', 'POST_PIXEL')


def clear_warning():
    global draw_handle

    if draw_handle is None:
        return

    bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')
    draw_handle = None


def pluralize(count: float, singular: str) -> str:
    if count != float("inf") and round(count) == 1:
        return singular
    return singular + "s"


def draw_callback_px():
    context = bpy.context

    font_id = 0  # XXX, need to find out how best to get this.

    color = prefs().color
    width = context.region.width
    height = context.region.height

    if context.space_data.show_region_ui:
        width -= 29

    secs_since_save = secs_since_last_save()
    if secs_since_save == float("inf"):
        ago = f"a long time"
    elif secs_since_save > 3600:
        hours = round(secs_since_save / 3600, 1)
        ago = f"{hours:.0f} {pluralize(hours, 'hour')}"
    elif secs_since_save > 60:
        mins = round(secs_since_save / 60)
        ago = f"{mins:.0f} {pluralize(mins, 'min')}"
    else:
        secs = round(secs_since_save)
        ago = f"{secs:.0f} seconds"

    operation = "Last saved" if bpy.data.filepath else "Created"

    # draw some text
    text_scale = context.preferences.system.pixel_size * context.preferences.view.ui_scale
    blf.position(font_id, width * 0.3, 12, 0)
    blf.size(font_id, 11.0 * text_scale)
    blf.color(font_id, *color, 0.5)
    blf.draw(font_id, f"{operation} {ago} ago")

    # Draw a line
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(line_thickness)

    secs_before_nag = start_nagging_in_sec()
    time_in_warning = secs_since_save - secs_before_nag
    line_len_factor = time_in_warning / (full_problem_after_sec() - secs_before_nag)

    if 1.0 < line_len_factor < float("inf"):
        # Panic mode.
        positions = [
            (0, 0),
            (width, 0),
            (width, height),
            (width, height),
            (0, height),
            (0, 0),
        ]
        batch = batch_for_shader(shader, 'TRIS', {"pos": positions})
        shader.uniform_float("color", (*color, line_len_factor - 1.0))
        batch.draw(shader)

    if line_len_factor >= 1.0:
        # Full problem mode!
        positions = [
            (line_thickness, line_thickness),
            (width - line_thickness, line_thickness),
            (width - line_thickness, height - line_thickness),
            (line_thickness, height - line_thickness),
            (line_thickness, line_thickness),
        ]
        alpha = 1.0
    else:
        line_len = line_len_factor * width
        positions = [
            (0, line_thickness),
            (line_len, line_thickness),
        ]
        alpha = 0.5

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": positions})
    shader.uniform_float("color", (*color, alpha))
    batch.draw(shader)

    # restore opengl defaults
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


@bpy.app.handlers.persistent
def on_save_post(filename: str) -> None:
    _reset_timer()


@bpy.app.handlers.persistent
def on_load_post(filename: str) -> None:
    _reset_timer()


def _reset_timer() -> None:
    global last_save_timestamp
    last_save_timestamp = time.monotonic()
    clear_warning()


class YouAreAutosavePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    nag_start_time: bpy.props.IntProperty(  # type: ignore
        name="Nag Start Time (minutes)",
        description="After not saving your blend file for this long, start to nag",
        default=5,
        min=0,
        max=525600,  # Max 1 year.
        soft_max=60,  # But realisticly 1 hour max is good enough.
        subtype="TIME",
    )

    full_problem_time: bpy.props.IntProperty(  # type: ignore
        name="Full Problem Time (minutes)",
        description="After not saving your blend file for this long after nagging started, the progress bar is full",
        default=15,
        min=0,
        max=525600,  # Max 1 year.
        soft_max=60,  # But realisticly 1 hour max is good enough.
        subtype="TIME",
    )

    color: bpy.props.FloatVectorProperty(  # type: ignore
        name="Color",
        min=0,
        max=1,
        default=(1.0, 0.1, 0.03),
        subtype='COLOR',
        size=3,
    )

    include_unsaved: bpy.props.BoolProperty(  # type: ignore
        name="Also nag when never saved",
        description="Also nag when the file has never been saved. When disabled, the "
        "add-on will only start nagging after a file has been saved/loaded from disk.",
        default=True,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Preferences:")
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(self, "nag_start_time")
        col.prop(self, "full_problem_time")
        col.prop(self, "include_unsaved")
        col.prop(self, "color")


classes = (YouAreAutosavePreferences,)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register() -> None:
    _register()
    _reset_timer()

    bpy.app.handlers.save_post.append(on_save_post)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.handlers.load_factory_startup_post.append(on_load_post)

    bpy.app.timers.register(check_last_save_timestamp, first_interval=0, persistent=True)
    check_last_save_timestamp()


def unregister() -> None:
    bpy.app.timers.unregister(check_last_save_timestamp)

    try:
        bpy.app.handlers.save_post.remove(on_save_post)
    except ValueError:
        pass
    try:
        bpy.app.handlers.load_post.remove(on_load_post)
    except ValueError:
        pass
    try:
        bpy.app.handlers.load_factory_startup_post.remove(on_load_post)
    except ValueError:
        pass

    clear_warning()
    _unregister()
