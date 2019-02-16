bl_info = {
    'name': 'Play Sound after Render Completes',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (2, 80, 0),
    'location': 'It just works after enabling the add-on.',
    'category': 'Render',
    'website': 'https://github.com/sybrenstuvel/random-blender-addons',
}

import bpy


@bpy.app.handlers.persistent
def play_sound(*args):
    import pathlib
    import aud

    ping_path = pathlib.Path(__file__).with_name('ping.ogg')

    aud_dev = aud.Device()
    aud_sound = aud.Sound(str(ping_path))
    aud_dev.play(aud_sound)


def register():
    bpy.app.handlers.render_complete.append(play_sound)


def unregister():
    try:
        bpy.app.handlers.render_complete.remove(play_sound)
    except ValueError:
        pass
