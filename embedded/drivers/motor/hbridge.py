import RPi.GPIO as GPIO


class DualHBridgeMotorDriver:
    _FORWARD = (1, 0)
    _REVERSE = (0, 1)
    _STOP = (0, 0)

    def __init__(
        self,
        left_in1=20,
        left_in2=21,
        right_in1=16,
        right_in2=12,
        left_pwm_pin=19,
        right_pwm_pin=13,
        pwm_frequency_hz=100,
        **legacy_kwargs,
    ):
        if 'm1_in1' in legacy_kwargs:
            left_in1 = legacy_kwargs['m1_in1']
        if 'm1_in2' in legacy_kwargs:
            left_in2 = legacy_kwargs['m1_in2']
        if 'm2_in1' in legacy_kwargs:
            right_in1 = legacy_kwargs['m2_in1']
        if 'm2_in2' in legacy_kwargs:
            right_in2 = legacy_kwargs['m2_in2']

        if 'm1_pwm' in legacy_kwargs:
            left_pwm_pin = legacy_kwargs['m1_pwm']
        if 'm2_pwm' in legacy_kwargs:
            right_pwm_pin = legacy_kwargs['m2_pwm']
        if 'left_enable_pin' in legacy_kwargs:
            left_pwm_pin = legacy_kwargs['left_enable_pin']
        if 'right_enable_pin' in legacy_kwargs:
            right_pwm_pin = legacy_kwargs['right_enable_pin']

        self.left_in1 = left_in1
        self.left_in2 = left_in2
        self.right_in1 = right_in1
        self.right_in2 = right_in2
        self.left_pwm_pin = left_pwm_pin
        self.right_pwm_pin = right_pwm_pin
        self.pwm_frequency_hz = pwm_frequency_hz

        if self.left_pwm_pin == self.right_pwm_pin:
            raise ValueError(
                f'PWM pins must be different; got left_pwm_pin={self.left_pwm_pin} and right_pwm_pin={self.right_pwm_pin}'
            )

        self.control_pins = (self.left_in1, self.left_in2, self.right_in1, self.right_in2)
        self.pwm_pins = (self.left_pwm_pin, self.right_pwm_pin)
        self.pins = tuple(dict.fromkeys(self.control_pins + self.pwm_pins))

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        self._left_pwm = GPIO.PWM(self.left_pwm_pin, self.pwm_frequency_hz)
        self._right_pwm = GPIO.PWM(self.right_pwm_pin, self.pwm_frequency_hz)
        self._left_pwm.start(0)
        self._right_pwm.start(0)
        self._left_speed = 0.0
        self._right_speed = 0.0

    def _normalize_direction(self, direction):
        value = str(direction).strip().lower()
        if value in ('forward', 'f', '1', '+1'):
            return self._FORWARD, 'forward'
        if value in ('backward', 'reverse', 'back', 'b', 'r', '-1'):
            return self._REVERSE, 'backward'
        if value in ('stop', 's', '0', 'brake'):
            return self._STOP, 'stop'
        raise ValueError(f'Invalid direction: {direction}')

    def _normalize_side(self, side):
        value = str(side).strip().lower()
        if value in ('left', 'l', 'm1', 'left_motor'):
            return 'left'
        if value in ('right', 'r', 'm2', 'right_motor'):
            return 'right'
        raise ValueError(f'Invalid side: {side}')

    def _normalize_speed(self, speed):
        if speed is None:
            return 100.0

        try:
            duty = float(speed)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Invalid speed: {speed}') from exc

        if duty < 0 or duty > 100:
            raise ValueError(f'Speed must be between 0 and 100, got {speed}')

        return duty

    def _set_left_tuple(self, state):
        in1, in2 = state
        GPIO.output(self.left_in1, GPIO.HIGH if in1 else GPIO.LOW)
        GPIO.output(self.left_in2, GPIO.HIGH if in2 else GPIO.LOW)

    def _set_right_tuple(self, state):
        in1, in2 = state
        GPIO.output(self.right_in1, GPIO.HIGH if in1 else GPIO.LOW)
        GPIO.output(self.right_in2, GPIO.HIGH if in2 else GPIO.LOW)

    def _apply_left_speed(self, speed):
        duty = self._normalize_speed(speed)
        self._left_pwm.ChangeDutyCycle(duty)
        self._left_speed = duty
        return duty

    def _apply_right_speed(self, speed):
        duty = self._normalize_speed(speed)
        self._right_pwm.ChangeDutyCycle(duty)
        self._right_speed = duty
        return duty

    def set_motor(self, side, direction, speed=100):
        side_name = self._normalize_side(side)
        state, normalized_direction = self._normalize_direction(direction)
        duty = 0.0 if normalized_direction == 'stop' else self._normalize_speed(speed)

        if side_name == 'left':
            self._set_left_tuple(state)
            applied_speed = self._apply_left_speed(duty)
        else:
            self._set_right_tuple(state)
            applied_speed = self._apply_right_speed(duty)

        return {'side': side_name, 'direction': normalized_direction, 'speed': applied_speed}

    def drive(self, left_direction, right_direction, left_speed=100, right_speed=100):
        left_state, left_norm = self._normalize_direction(left_direction)
        right_state, right_norm = self._normalize_direction(right_direction)

        left_duty = 0.0 if left_norm == 'stop' else self._normalize_speed(left_speed)
        right_duty = 0.0 if right_norm == 'stop' else self._normalize_speed(right_speed)

        self._set_left_tuple(left_state)
        self._set_right_tuple(right_state)
        applied_left = self._apply_left_speed(left_duty)
        applied_right = self._apply_right_speed(right_duty)

        return {
            'left': left_norm,
            'right': right_norm,
            'left_speed': applied_left,
            'right_speed': applied_right,
        }

    def set_speed(self, side, speed):
        side_name = self._normalize_side(side)
        if side_name == 'left':
            applied_speed = self._apply_left_speed(speed)
        else:
            applied_speed = self._apply_right_speed(speed)
        return {'side': side_name, 'speed': applied_speed}

    def set_speeds(self, left_speed, right_speed):
        applied_left = self._apply_left_speed(left_speed)
        applied_right = self._apply_right_speed(right_speed)
        return {'left_speed': applied_left, 'right_speed': applied_right}

    def set_states(self, m1_in1, m1_in2, m2_in1, m2_in2, left_speed=100, right_speed=100):
        left_state = (1 if m1_in1 else 0, 1 if m1_in2 else 0)
        right_state = (1 if m2_in1 else 0, 1 if m2_in2 else 0)

        self._set_left_tuple(left_state)
        self._set_right_tuple(right_state)

        if left_state == self._STOP:
            self._apply_left_speed(0)
        else:
            self._apply_left_speed(left_speed)

        if right_state == self._STOP:
            self._apply_right_speed(0)
        else:
            self._apply_right_speed(right_speed)

    def set_both_forward(self, speed=100):
        return self.drive('forward', 'forward', left_speed=speed, right_speed=speed)

    def set_both_reverse(self, speed=100):
        return self.drive('backward', 'backward', left_speed=speed, right_speed=speed)

    def stop(self):
        return self.drive('stop', 'stop', left_speed=0, right_speed=0)

    def cleanup(self):
        try:
            self.stop()
        finally:
            try:
                self._left_pwm.stop()
            except Exception:
                pass
            try:
                self._right_pwm.stop()
            except Exception:
                pass
            GPIO.cleanup(self.pins)
