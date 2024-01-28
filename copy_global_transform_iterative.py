#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

# To do:
#
# - [x] Separate functionality from operator
# - [ ] Split execution into preparation and single step functions
# - [ ] Rework operator so it's modal and shows the movement
# - [ ] Support for bones
# - [ ] Support for quaternion rotation
# - [ ] Support for axis angle
# - [ ] Support for euler wrapping
# - [ ] Support for axis angle/quaternion flipping


"""
Copy Global Transform

Simple add-on for copying world-space transforms.

It's called "global" to avoid confusion with the Blender World data-block.
"""

import ast
import time
from typing import Optional, Protocol, TypeAlias

import bpy
from bpy.types import Context, Operator, Object
from mathutils import Vector, Matrix


bl_info = {
    "name": "Copy Global Transform (iterative prototype)",
    "author": "Sybren A. Stüvel",
    "version": (0, 1),
    "blender": (4, 0, 0),
    "location": "N-panel in the 3D Viewport",
    "category": "Animation",
    "support": 'OFFICIAL',
    "doc_url": "{BLENDER_MANUAL_URL}/addons/animation/copy_global_transform.html",
    "tracker_url": "https://projects.blender.org/blender/blender-addons/issues",
}


DoFs: TypeAlias = Vector
"""Degrees of Freedom."""


class Transformable(Protocol):
    """Interface for a bone or an object."""

    def calc_dofs(self) -> DoFs:
        pass

    def apply_dofs(self, dofs: DoFs) -> None:
        pass

    def matrix_world(self) -> Matrix:
        pass


class TransformableObject:
    object: Object
    view_layer: bpy.types.ViewLayer

    def __init__(self, context: Context, object: Object) -> None:
        self.view_layer = context.view_layer
        self.object = object

    def calc_dofs(self) -> DoFs:
        dofs = Vector(list(self.object.location) + list(self.object.rotation_euler))
        return dofs

    def apply_dofs(self, dofs: DoFs) -> None:
        assert len(dofs) == 6
        self.object.location = dofs[0:3]
        self.object.rotation_euler = dofs[3:6]
        self.view_layer.update()

    def matrix_world(self) -> Matrix:
        return self.object.matrix_world


class TransformSolver:
    subjecet: Transformable
    dofs_target: DoFs

    def __init__(self, subject: Transformable, dofs_target: DoFs) -> None:
        self.subject = subject
        self.dofs_target = dofs_target

    def execute(self) -> None:
        dofs = self.subject.calc_dofs()
        num_dofs = len(dofs)

        delta = 0.1
        step_count = 10000

        last_error = self.calc_error()

        time_start = time.monotonic()
        step_num = 0  # The for-loop won't assign if step_count = 0.
        for step_num in range(step_count):
            # dof_index = step_num % num_dofs
            new_dofs = dofs.copy()
            for dof_index in range(num_dofs):
                dof_step = self.optimisation_step(dofs, dof_index, delta, last_error)
                new_dofs[dof_index] += dof_step

            dofs = new_dofs
            self.subject.apply_dofs(dofs)

            error = self.calc_error()

            if error < 0.0001:
                print('Done, error is small enough.')
                break

            if error > last_error:
                diff = error - last_error
                print(
                    f'Step {step_num}: error is getting bigger, '
                    f'from {last_error:.7f} to {error:.7f} '
                    f'(difference of {diff:5.03g})'
                )

                if delta > 1e-6:
                    print(f'\033[91mDecreasing delta\033[0m from {delta} ', end='')
                    delta *= 0.95
                    print(f'to {delta}')

            last_error = error

        time_end = time.monotonic()
        duration = time_end - time_start
        per_step = duration / (step_num + 1)

        print(f'Steps   : {step_num+1}')
        print(f'Duration: {duration:.1f} sec')
        print(f'per step: {1000*per_step:.1f} msec')
        print(f'last delta: {delta}')

        error_vec = self.calc_error_vec()
        print(f'error dofs : {self.fmt_dofs(error_vec)}')

        error = self.calc_error()
        print(f'final error: {error}')

    def optimisation_step(self, last_dofs: DoFs, dof_index: int, delta: float, last_error: float) -> float:
        """Return the delta to be applied to the given DoF."""
        dofs = last_dofs.copy()
        dofs[dof_index] += delta

        self.subject.apply_dofs(dofs)
        error = self.calc_error()

        # Clean up after ourselves.
        self.subject.apply_dofs(last_dofs)

        if error < last_error:
            # This was going in the right direction.
            step = delta
        else:
            # It made things worse, so go the opposite direction.
            step = -delta

        return step

    @staticmethod
    def fmt_dofs(dofs: Vector) -> str:
        comma_sep = ', '.join('%-.5f' % s for s in dofs)
        return f'[{comma_sep}]'

    @staticmethod
    def dofs_from_matrix(mat: Matrix) -> Vector:
        # Returns Vector of DoFs in world space.
        return Vector(list(mat.to_translation()) + list(mat.to_euler()))

    def calc_error_vec(self) -> Vector:
        mat = self.subject.matrix_world()
        dofs_subject = self.dofs_from_matrix(mat)
        # TODO: handle wrapping of eulers.
        return dofs_subject - self.dofs_target

    def calc_error(self) -> float:
        error_vec = self.calc_error_vec()
        return float(error_vec.length)


class OBJECT_OT_paste_transform_iterative(Operator):
    bl_idname = "object.paste_transform_iterative"
    bl_label = "Iterative Paste"
    bl_description = (
        "Pastes the matrix from the clipboard to the currently active pose bone or object. Uses world-space matrices"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        mat = self.get_matrix_from_clipboard(context)
        if mat is None:
            self.report({'ERROR'}, "Clipboard does not contain a valid matrix")
            return {'CANCELLED'}

        subject = TransformableObject(context, context.active_object)
        dofs_target = TransformSolver.dofs_from_matrix(mat)
        solver = TransformSolver(subject, dofs_target)
        solver.execute()

        return {'FINISHED'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if not context.active_pose_bone and not context.active_object:
            cls.poll_message_set("Select an object or pose bone")
            return False

        clipboard = context.window_manager.clipboard.strip()
        if not (clipboard.startswith("Matrix(") or clipboard.startswith("<Matrix 4x4")):
            cls.poll_message_set("Clipboard does not contain a valid matrix")
            return False
        return True

    @classmethod
    def get_matrix_from_clipboard(cls, context: Context) -> Optional[Matrix]:
        clipboard = context.window_manager.clipboard.strip()
        if clipboard.startswith("Matrix"):
            return Matrix(ast.literal_eval(clipboard[6:]))
        if clipboard.startswith("<Matrix 4x4"):
            return cls.parse_repr_m4(clipboard[12:-1])
        return cls.parse_print_m4(clipboard)

    @staticmethod
    def parse_print_m4(value: str) -> Optional[Matrix]:
        """Parse output from Blender's print_m4() function.

        Expects four lines of space-separated floats.
        """

        lines = value.strip().splitlines()
        if len(lines) != 4:
            return None

        floats = tuple(tuple(float(item) for item in line.split()) for line in lines)
        return Matrix(floats)

    @staticmethod
    def parse_repr_m4(value: str) -> Optional[Matrix]:
        """Four lines of (a, b, c, d) floats."""

        lines = value.strip().splitlines()
        if len(lines) != 4:
            return None

        floats = tuple(tuple(float(item.strip()) for item in line.strip()[1:-1].split(',')) for line in lines)
        return Matrix(floats)


def _draw_button(panel: bpy.types.Panel, context: Context) -> None:
    layout = panel.layout
    layout.operator(OBJECT_OT_paste_transform_iterative.bl_idname)


classes = (OBJECT_OT_paste_transform_iterative,)
_register, _unregister = bpy.utils.register_classes_factory(classes)


def register() -> None:
    _register()
    bpy.types.VIEW3D_PT_copy_global_transform.append(_draw_button)


def unregister() -> None:
    _unregister()

    try:
        bpy.types.VIEW3D_PT_copy_global_transform.remove(_draw_button)
    except AttributeError:
        pass
