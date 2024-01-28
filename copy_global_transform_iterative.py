#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

# To do:
#
# - [x] Separate functionality from operator
# - [ ] Split execution into preparation and single step functions
# - [ ] Rework operator so it's modal and shows the movement
# - [x] Support for bones
# - [x] Support for quaternion rotation
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
from dataclasses import dataclass
from typing import Optional, Protocol, TypeAlias, Optional

import bpy
from bpy.types import Context, Operator, Object, PoseBone, Event
from mathutils import Vector, Matrix, Quaternion, Euler


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
        """Return the current DoFs.

        This is typically the list of local location & rotation values.
        """
        pass

    def apply_dofs(self, dofs: DoFs) -> None:
        """Apply the given DoFs."""
        pass

    def matrix_world(self) -> Matrix:
        pass


class TransformableObject:
    object: Object
    view_layer: bpy.types.ViewLayer
    rotation_prop_name: str

    def __init__(self, context: Context, object: Object) -> None:
        self.view_layer = context.view_layer
        self.object = object

        match object.rotation_mode:
            case "AXIS_ANGLE":
                raise TypeError("Axis/Angle not yet supported")
            case "QUATERNION":
                self.rotation_prop_name = "rotation_quaternion"
            case _:
                self.rotation_prop_name = "rotation_euler"

    def calc_dofs(self) -> DoFs:
        loc_dofs = list(self.object.location)
        rot_dofs = list(getattr(self.object, self.rotation_prop_name))
        return Vector(loc_dofs + rot_dofs)

    def apply_dofs(self, dofs: DoFs) -> None:
        self.object.location = dofs[0:3]
        setattr(self.object, self.rotation_prop_name, dofs[3:])
        self.view_layer.update()

    def matrix_world(self) -> Matrix:
        return self.object.matrix_world


class TransformableBone:
    arm_object: Object
    pose_bone: PoseBone
    view_layer: bpy.types.ViewLayer
    rotation_prop_name: str

    def __init__(self, context: Context, arm_object: Object, pose_bone: PoseBone) -> None:
        self.view_layer = context.view_layer
        self.arm_object = arm_object
        self.pose_bone = pose_bone

        match pose_bone.rotation_mode:
            case "AXIS_ANGLE":
                raise TypeError("Axis/Angle not yet supported")
            case "QUATERNION":
                self.rotation_prop_name = "rotation_quaternion"
            case _:
                self.rotation_prop_name = "rotation_euler"

    def calc_dofs(self) -> DoFs:
        loc_dofs = list(self.pose_bone.location)
        rot_dofs = list(getattr(self.pose_bone, self.rotation_prop_name))
        return Vector(loc_dofs + rot_dofs)

    def apply_dofs(self, dofs: DoFs) -> None:
        self.pose_bone.location = dofs[0:3]
        setattr(self.pose_bone, self.rotation_prop_name, dofs[3:])
        self.view_layer.update()

    def matrix_world(self) -> Matrix:
        mat = self.arm_object.matrix_world @ self.pose_bone.matrix
        return mat


@dataclass
class ExecutionState:
    dofs: DoFs
    last_error: DoFs
    delta: float = 0.1
    step_num: int = 0


class TransformSolver:
    subjecet: Transformable
    dofs_target: DoFs
    rot_target_expmap: Vector
    max_step_count: int

    def __init__(self, subject: Transformable, dofs_target: DoFs, max_step_count: int = 10000) -> None:
        self.subject = subject
        self.dofs_target = dofs_target
        self.max_step_count = max_step_count

        # TODO: do this better.
        match len(dofs_target):
            case 6:  # Euler angles.
                quat = Euler(dofs_target[3:]).to_quaternion()
            case 7:  # Quaternions.
                quat = Quaternion(dofs_target[3:])
            case _:  # Wait, whut?
                raise ValueError(f'no idea what to with {dofs_target}')
        self.rot_target_expmap = quat.to_exponential_map()

    def setup(self) -> ExecutionState:
        err_vec = self._calc_error_vec()
        delta = self._delta_for_error(1.0, err_vec)

        state = ExecutionState(
            dofs=self.subject.calc_dofs(),
            last_error=self._calc_error(err_vec),
            delta=delta,
        )

        print(f"startup state: {state}")

        return state

    def step(self, state: ExecutionState) -> Optional[ExecutionState]:
        state.step_num += 1
        new_dofs = state.dofs.copy()

        print(f"Step {state.step_num}: iterating over {len(state.dofs)} DoFs")
        for dof_index in range(len(state.dofs)):
            dof_step = self._optimisation_step(state.dofs, dof_index, state.delta, state.last_error)
            if dof_step == 0:
                print(f"Step {state.step_num}: skipping update of dof {dof_index}, change in error too small.")
                print(f"  error={state.last_error}")
                print(f"  delta={state.delta}")
                continue
            new_dofs[dof_index] += dof_step

        state.dofs = new_dofs
        self.subject.apply_dofs(state.dofs)

        err_vec = self._calc_error_vec()
        error = self._calc_error(err_vec)

        if error < 0.0001:
            print('Done, error is small enough.')
            return None

        if error > state.last_error:
            diff = error - state.last_error
            print(
                f'Step {state.step_num}: error is getting bigger, '
                f'from {state.last_error:.7f} to {error:.7f} '
                f'(difference of {diff:5.03g})'
            )

            if state.delta > 1e-6:
                print(f'\033[91mDecreasing delta\033[0m from {state.delta} ', end='')
                state.delta = max(1e-5, state.delta * 0.90)
                print(f'to {state.delta}')
        else:
            state.delta = self._delta_for_error(state.delta, err_vec)

        state.last_error = error

        if state.step_num >= self.max_step_count:
            print(f'Ran out of steps, stopping at {state.step_num}')
            return None

        return state

    def execute(self) -> None:
        state = self.setup()

        time_start = time.monotonic()
        while True:
            # Don't assign directly to 'state' so that the last not-None state
            # is available when execution ends.
            next_state = self.step(state)
            if next_state is None:
                break
            state = next_state
        time_end = time.monotonic()

        duration = time_end - time_start
        per_step = duration / (state.step_num + 1)

        print(f'Steps   : {state.step_num+1}')
        print(f'Duration: {duration:.1f} sec')
        print(f'per step: {1000*per_step:.1f} msec')
        print(f'last delta: {state.delta}')

        error_vec = self._calc_error_vec()
        print(f'error dofs : {self.fmt_dofs(error_vec)}')

        error = self._calc_error(error_vec)
        print(f'final error: {error}')

    def _optimisation_step(self, last_dofs: DoFs, dof_index: int, delta: float, last_error: float) -> float:
        """Return the delta to be applied to the given DoF."""

        dofs = last_dofs.copy()
        dofs[dof_index] += delta

        self.subject.apply_dofs(dofs)

        error_vec = self._calc_error_vec()
        error = self._calc_error(error_vec)

        # Clean up after ourselves.
        self.subject.apply_dofs(last_dofs)

        # if abs(last_error - error) < 1e-5:
        #     # Altering this DoF doesn't change the error, don't bother stepping.
        #     # This is to avoid adjusting all DoFs when only one still has an error.
        #     return 0.0

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

    def _calc_error_vec(self) -> Vector:
        mat = self.subject.matrix_world()
        dofs_subject = self.dofs_from_matrix(mat)

        # return dofs_subject - self.dofs_target

        err_loc = dofs_subject.xyz - self.dofs_target.xyz

        # TODO: do this better.
        match len(dofs_subject):
            case 6:  # Euler angles.
                quat = Euler(dofs_subject[3:]).to_quaternion()
            case 7:  # Quaternions.
                quat = Quaternion(dofs_subject[3:])
            case _:  # Wait, whut?
                raise ValueError(f'no idea what to with {dofs_subject}')

        rot_subject_expmap = quat.to_exponential_map()
        err_rot = rot_subject_expmap - self.rot_target_expmap

        return Vector(list(err_loc) + list(err_rot))

    def _calc_error(self, error_vec: Vector) -> float:
        return float(error_vec.length)

    def _delta_for_error(self, current_delta: float, error_vec: Vector) -> float:
        average = sum(abs(x) for x in error_vec) / len(error_vec)
        delta: float = max(1e-5, current_delta * 0.75, average)
        return delta


class OBJECT_OT_paste_transform_iterative(Operator):
    bl_idname = "object.paste_transform_iterative"
    bl_label = "Iterative Paste"
    bl_description = (
        "Pastes the matrix from the clipboard to the currently active pose bone or object. Uses world-space matrices"
    )
    bl_options = {'REGISTER', 'UNDO'}

    state: ExecutionState

    def execute(self, context: Context) -> set[str]:
        solver = self._get_solver(context)
        if not solver:
            # Error has already been reported.
            return {'CANCELLED'}

        solver.execute()
        return {'FINISHED'}

    def invoke(self, context: Context, event: Event) -> set[str]:
        solver = self._get_solver(context)
        if not solver:
            return {'CANCELLED'}

        self.solver = solver
        self.state = self.solver.setup()

        # Set up the modal timer.
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def modal(self, context: Context, event: Event) -> set[str]:
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            msg = f'Aborted after {self.state.step_num} steps, error = {self.state.last_error:.4f}'
            print(msg)
            self.report({'WARNING'}, msg)
            self.cancel(context)
            return {'FINISHED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        new_state = self.solver.step(self.state)
        if new_state is None:
            self.report({'INFO'}, f'Done after {self.state.step_num} steps')
            self.cancel(context)
            return {'FINISHED'}
        self.state = new_state

        return {'RUNNING_MODAL'}

    def cancel(self, context: Context) -> None:
        wm = context.window_manager
        wm.event_timer_remove(self._timer)

    def _get_solver(self, context: Context) -> Optional[TransformSolver]:
        mat = self.get_matrix_from_clipboard(context)
        if mat is None:
            self.report({'ERROR'}, "Clipboard does not contain a valid matrix")
            return None

        subject: Transformable
        if context.active_pose_bone:
            subject = TransformableBone(context, context.active_object, context.active_pose_bone)
        else:
            subject = TransformableObject(context, context.active_object)

        dofs_target = TransformSolver.dofs_from_matrix(mat)
        solver = TransformSolver(subject, dofs_target)

        return solver

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
