"""
Remote debugging support.

This addon allows you to use a remote Python debugger with PyCharm, PyDev and
possibly other IDEs. As it is, without modification, it only supports PyCharm,
but that's easily fixed by changing the global EGG_PATH constant. I assume you
know how to do that, as you're a developer. If not, what are you using a
debugger for in the first place?

NOTE: Batteries not included. Copy pycharm-debug-py3k.egg from your PyCharm
installation to whatever EGG_PATH points at, or point EGG_PATH to the absolute
path of that file.
"""

bl_info = {
    'name': 'Remote debugger',
    'author': 'Sybren A. Stüvel',
    'version': (0, 1),
    'blender': (2, 75, 0),
    'location': 'Press [Space], search for "debugger"',
    'category': 'Development',
}

import bpy
import os.path

EGG_PATH = '/path/to/pycharm-debug-py3k.egg'


class DEBUG_OT_connect_debugger(bpy.types.Operator):
    bl_idname = 'debug.connect_debugger'
    bl_label = 'Connect to remote Python debugger'
    bl_description = 'Connects to a PyCharm debugger on localhost:1090'

    def execute(self, context):
        import sys

        egg_fname = os.path.abspath(bpy.path.abspath(EGG_PATH))

        if not os.path.exists(egg_fname):
            self.report({'ERROR'}, 'Unable to find debug egg at %r' % egg_fname)
            return {'CANCELLED'}

        if not any('pycharm-debug' in p for p in sys.path):
            sys.path.append(egg_fname)

        import pydevd
        pydevd.settrace('localhost', port=1090, stdoutToServer=True, stderrToServer=True)

        return {'FINISHED'}


def register():
    bpy.utils.register_class(DEBUG_OT_connect_debugger)


def unregister():
    bpy.utils.unregister_class(DEBUG_OT_connect_debugger)


if __name__ == '__main__':
    register()
