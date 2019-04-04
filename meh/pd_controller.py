"""
PD controller.

See http://en.wikipedia.org/wiki/PID_controller

Uses the error of the derivative instead of the derivative of the error.
This prevents large peaks in the ouput when the setpoint changes significantly.
"""


from math import pi

twopi = 2 * pi


def angular_diff(a: float, b: float) -> float:
    """Returns the angular difference a - b.

    Always returns the angle the shortest way around.

    >>> angular_diff(5, 2)
    3
    >>> angular_diff(2, 5)
    -3
    >>> angular_diff(-0.02, 0.05)
    -0.07
    >>> angular_diff(twopi - 0.02, 0.05)  # doctest: +ELLIPSIS
    -0.06999999...
    >>> angular_diff(twopi + 0.02, -0.05)  # doctest: +ELLIPSIS
    0.06999999...
    >>> angular_diff(0.02, twopi + 0.05)  # doctest: +ELLIPSIS
    -0.03000000...
    """

    d1 = a - b
    d2 = d1 + twopi
    d3 = d1 - twopi

    return min(d1, d2, d3, key=abs)


class PDController:

    ZERO = 0.0

    def __init__(self, kp=1.0, kd=1.0):
        self.kp = kp  # Proportional gain
        self.kd = kd  # Derivative gain

        self._setpoint = self.ZERO   # Desired value
        self.last_error = self.ZERO  # Last seen error, for calculating derivative of error
        self.last_pv = self.ZERO     # Last seen process value, for calculating derivative of PV.
        self._last_time = None       # Last time we've seen an update

        # Only for debugging:
        self.pd = (self.ZERO, self.ZERO)
        self.unweighted = (self.ZERO, self.ZERO)

    def set_gains(self, kp, kd):
        """Sets the PD gains

        :param kp: Proportional gain
        :param kd: Derivative gain
        """

        self.kp = kp
        self.kd = kd

    @property
    def setpoint(self):
        return self._setpoint

    @setpoint.setter
    def setpoint(self, new_setpoint):
        self._setpoint = new_setpoint

    def reset(self):
        self.last_error = self.ZERO
        self._last_time = None

    def calc_error(self, process_value):
        return self.calc_diff(self._setpoint, process_value)

    def calc_diff(self, a, b):
        return a - b

    def update(self, process_value, current_time: float) -> float:
        """Calculates the new manipulated value, given the current value and time."""

        error = self.calc_error(process_value)

        if self._last_time is None:
            timediff = 0
        else:
            timediff = current_time - self._last_time

        # Calculate the derivative of the process value. Calculating this instead of
        # the derivative of the error prevents large peaks when the setpoint changes.
        if timediff > 0:
            error_diff = -self.calc_diff(process_value, self.last_pv) / timediff
        else:
            error_diff = self.ZERO

        # Remember values for next time
        self.last_error = error
        self.last_pv = process_value
        self._last_time = current_time

        # Calculate & return the result
        p = self.kp * error
        d = self.kd * error_diff

        self.pd = (p, d)
        self.unweighted = (error, error_diff)

        return p + d


class AngularPDController(PDController):

    def calc_diff(self, a, b):
        return angular_diff(a, b)

try:
    import mathutils
except ImportError:
    pass
else:
    class Vector2PDController(PDController):
        ZERO = mathutils.Vector((0, 0))


def __test():
    import matplotlib.pyplot as plt
    import numpy as np

    process_value = 0.0
    pid = PDController(5.0, 1.0)

    times = []
    values = []
    reference_values = []
    for t in np.linspace(0, 10, num=600):
        pid.setpoint = int(t >= 1)
        managed_value = pid.update(process_value, t)
        process_value += 0.1 * managed_value

        print('t=%.2f  sp=%i  pv=%7.4f  error=%7.4f' %
              (t, pid.setpoint, process_value, pid.last_error))
        times.append(t)
        values.append(process_value)
        reference_values.append(pid.setpoint)

    plt.plot(times, values, label='PV')
    plt.plot(times, reference_values, label='reference')
    plt.ylim(-3, 10)
    plt.legend()
    plt.show()


if __name__ == '__main__':
    __test()
