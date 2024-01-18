#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Copy Global Transform

Simple add-on for copying world-space transforms.

It's called "global" to avoid confusion with the Blender World data-block.
"""

import time
from typing import Iterable, Optional

import bpy
from bpy.types import Context, Operator, Object
from mathutils import Vector


bl_info = {
    "name": "Copy Global Transform (iterative prototype)",
    "author": "Sybren A. Stüvel",
    "version": (0, 1),
    "blender": (4, 1, 0),
    "location": "N-panel in the 3D Viewport",
    "category": "Animation",
    "support": 'OFFICIAL',
    "doc_url": "{BLENDER_MANUAL_URL}/addons/animation/copy_global_transform.html",
    "tracker_url": "https://projects.blender.org/blender/blender-addons/issues",
}


class OBJECT_OT_paste_transform_iterative(Operator):
    bl_idname = "object.paste_transform_iterative"
    bl_label = "Iterative Paste"
    bl_description = (
        "Pastes the matrix from the clipboard to the currently active pose bone or object. Uses world-space matrices"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        D = bpy.data
        T = D.objects['Target']
        S = D.objects['Suzanne']

        self.subject = S
        self.target = T

        dofs = self.calc_dofs(S)
        num_dofs = len(dofs)

        delta = 0.1
        step_count = 10000

        last_error = self.calc_error()

        time_start = time.monotonic()
        step_num = 0  # The for-loop won't assign if step_count = 0.
        for step_num in range(step_count):
            dof_index = step_num % num_dofs
            dof_step = self.optimisation_step(
                context, dofs, dof_index, delta, last_error)

            dofs[dof_index] += dof_step
            self.apply_dofs(context, dofs)

            error = self.calc_error()
        #    print(f'  Error: {error}')
        #    print(f'  Delta: {delta}')

            if error < 0.0001:
                print('Done, error is small enough.')
                break

            if error > last_error:
                diff = error - last_error
                print(
                    f'Step {step_num}: error is getting bigger, '
                    f'from {last_error:.7f} to {error:.7f} '
                    f'(difference of {diff:8.03g})'
                )

                if error < 0.2 and delta > 1e-6:
                    print(
                        f'\033[91mDecreasing delta\033[0m from {delta} ', end='')
                    delta *= 0.95
                    print(f'to {delta}')

            last_error = error
            # if error < 0.05 and delta > 0.00011:
            #     print(f'\033[91mDecreasing delta\033[0m from {delta} ', end='')
            #     delta = 0.0001
            #     print(f'to {delta}')

        #    elif error < 0.03:
        #        delta = 0.001

        time_end = time.monotonic()
        duration = time_end - time_start
        per_step = duration / (step_num+1)

        print(f'Steps   : {step_num+1}')
        print(f'Duration: {duration:.1f} sec')
        print(f'per step: {1000*per_step:.1f} msec')
        print(f'last delta: {delta}')

        error = self.calc_error()
        error_vec = self.world_space(S) - self.world_space(T)
        print(f'error dofs : {self.fmt_dofs(error_vec)}')
        print(f'final error: {error}')

        return {'FINISHED'}

    def optimisation_step(self, context: Context, last_dofs: Vector, dof_index: int, delta: float, last_error: float) -> float:
        dofs = last_dofs.copy()
        dofs[dof_index] += delta

        self.apply_dofs(context, dofs)
        error = self.calc_error()

        # Clean up after ourselves.
        self.apply_dofs(context, last_dofs)

        if error < last_error:
            # This was going in the right direction.
            step = delta
        else:
            # It made things worse, so go the opposite direction.
            step = -delta

        return step

    @staticmethod
    def calc_dofs(ob: Object) -> Vector:
        return Vector(list(ob.location) + list(ob.rotation_euler))

    def apply_dofs(self, context: Context, dofs: Vector) -> None:
        assert len(dofs) == 6
        self.subject.location = dofs[0:3]
        self.subject.rotation_euler = dofs[3:6]
        context.view_layer.update()
        # ob.update_tag(refresh={'OBJECT'})

    @staticmethod
    def fmt_dofs(dofs: Vector) -> str:
        comma_sep = ', '.join('%-.5f' % s for s in dofs)
        return f'[{comma_sep}]'

    @staticmethod
    def world_space(ob: Object) -> Vector:
        # Returns Vector of DoFs in world space.
        mat_world = ob.matrix_world
        return Vector(list(mat_world.to_translation()) + list(mat_world.to_euler()))

    def calc_error(self) -> float:
        dofs_subject = self.world_space(self.subject)
        dofs_target = self.world_space(self.target)
        # TODO: handle wrapping of eulers.
        error_vec = dofs_subject - dofs_target
        return error_vec.length


def _draw_button(panel, context: Context) -> None:
    layout = panel.layout
    layout.operator(OBJECT_OT_paste_transform_iterative.bl_idname)


classes = (
    OBJECT_OT_paste_transform_iterative,
)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
    _register()
    bpy.types.VIEW3D_PT_copy_global_transform.append(_draw_button)


def unregister():
    _unregister()

    try:
        bpy.types.VIEW3D_PT_copy_global_transform.remove(_draw_button)
    except AttributeError:
        pass
