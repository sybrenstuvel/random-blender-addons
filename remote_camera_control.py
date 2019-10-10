"""Remote Camera Control"""

bl_info = {
    'name': 'Remote Camera Control',
    'author': 'Sybren A. Stüvel',
    'version': (0, 1),
    'blender': (2, 81, 0),
    'location': 'Press [Space], search for "remote camera"',
    'category': 'Development',
}

import math
import socket
from typing import Optional, Set

import bpy



class UASVR_OT_remote_camera_control(bpy.types.Operator):
    bl_idname = 'uasvr.remote_camera_control'
    bl_label = 'Remote Camera Control'

    timer = None
    sock: Optional[socket.socket] = None

    message_buffer: bytes = b''

    @classmethod
    def poll(cls, context) -> bool:
        return context.scene.camera is not None

    def invoke(self, context, event) -> Set[str]:
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect(('::1', 8888))
        self.report({'INFO'}, f'Connected to {self.sock.getpeername()}')

        self.sock.send(b'CAMERA ME\n')

        # After connecting, the socket should be non-blocking.
        self.sock.settimeout(0)

        wm = context.window_manager
        wm.modal_handler_add(self)
        self.timer = wm.event_timer_add(0.01, window=context.window)
        return {'RUNNING_MODAL'}

    def quit(self, context) -> None:
        context.window_manager.event_timer_remove(self.timer)

        if self.sock:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()

        self.report({'INFO'}, 'Shut down remote camera control')

    def modal(self, context, event) -> Set[str]:
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.quit(context)
            return {'FINISHED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        try:
            self.message_buffer += self.sock.recv(128)
        except BlockingIOError as ex:
            return {'PASS_THROUGH'}

        if b'\n' not in self.message_buffer:
            return {'PASS_THROUGH'}

        message, self.message_buffer = self.message_buffer.split(b'\n', 1)

        understood = self.handle_message(context, message)
        if understood:
            self.sock.send(b'ACK\n')
        else:
            self.sock.send(b'NOT UNDERSTOOD: ' + message + b'\n')

        return {'PASS_THROUGH'}

    def handle_message(self, context, message: bytes) -> bool:
        if message.startswith(b'POS'):
            coords = [float(part) for part in message[4:].split(b',')]
            context.scene.camera.location = coords
            return True

        if message.startswith(b'ROT'):
            eulers_deg = (float(part) for part in message[4:].split(b','))
            eulers_rad = [math.radians(angle) for angle in eulers_deg]
            context.scene.camera.rotation_euler = eulers_rad
            return True

        if message.startswith(b'FRAME'):
            frame_nr = int(message[6:])
            context.scene.frame_set(frame_nr)
            return True

        return False


classes = (
    UASVR_OT_remote_camera_control,
)
register, unregister = bpy.utils.register_classes_factory(classes)
