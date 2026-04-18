import os
import lgpio
import time

_HW_PWM_MAP = {
    18: ('pwmchip0', 2),
    19: ('pwmchip0', 3),
}


class _SysfsPWM:
    def __init__(self, gpio, freq_hz):
        if gpio not in _HW_PWM_MAP:
            raise ValueError(f'GPIO {gpio} has no hardware PWM on Pi 5')
        chip, self._chan = _HW_PWM_MAP[gpio]
        self._base = f'/sys/class/pwm/{chip}/pwm{self._chan}'
        self._freq_hz = freq_hz
        self._period_ns = int(1e9 / freq_hz)

        export_path = f'/sys/class/pwm/{chip}/export'
        if not os.path.exists(self._base):
            with open(export_path, 'w') as f:
                f.write(str(self._chan))

            for _ in range(50):
                if os.path.exists(self._base):
                    break
                time.sleep(0.02)

        self._write('enable', 0)
        self._write('period', self._period_ns)
        self._write('duty_cycle', 0)
        self._write('enable', 1)

    def _write(self, attr, value):
        path = f'{self._base}/{attr}'
        for _ in range(10):
            try:
                with open(path, 'w') as f:
                    f.write(str(value))
                return
            except OSError:
                time.sleep(0.01)

    def set_duty(self, percent):
        duty_ns = int(self._period_ns * max(0.0, min(100.0, percent)) / 100.0)
        self._write('duty_cycle', duty_ns)

    def close(self):
        try:
            self._write('duty_cycle', 0)
            self._write('enable', 0)
        except Exception:
            pass


class DualHBridgeMotorDriver:
    _FORWARD = (1, 0)
    _REVERSE = (0, 1)
    _STOP    = (0, 0)

    def __init__(
        self,
        left_in1=20,
        left_in2=21,
        right_in1=16,
        right_in2=1,
        left_pwm_pin=18,
        right_pwm_pin=19,
        pwm_frequency_hz=100,
        left_speed_factor=0.85,
        right_speed_factor=1.0,
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

        self.left_in1         = left_in1
        self.left_in2         = left_in2
        self.right_in1        = right_in1
        self.right_in2        = right_in2
        self.left_pwm_pin     = left_pwm_pin
        self.right_pwm_pin    = right_pwm_pin
        self.pwm_frequency_hz = pwm_frequency_hz
        self._left_speed_factor  = float(left_speed_factor)
        self._right_speed_factor = float(right_speed_factor)

        if self.left_pwm_pin == self.right_pwm_pin:
            raise ValueError(f'PWM pins must be different')

        self.control_pins = (self.left_in1, self.left_in2, self.right_in1, self.right_in2)

        self._h = lgpio.gpiochip_open(0)
        for pin in self.control_pins:
            lgpio.gpio_claim_output(self._h, pin, 0)

        self._left_pwm  = _SysfsPWM(self.left_pwm_pin,  self.pwm_frequency_hz)
        self._right_pwm = _SysfsPWM(self.right_pwm_pin, self.pwm_frequency_hz)
        self._left_speed  = 0.0
        self._right_speed = 0.0

    # ------------------------------------------------------------------
    def _normalize_direction(self, direction):
        v = str(direction).strip().lower()
        if v in ('forward', 'f', '1', '+1'):
            return self._FORWARD, 'forward'
        if v in ('backward', 'reverse', 'back', 'b', 'r', '-1'):
            return self._REVERSE, 'backward'
        if v in ('stop', 's', '0', 'brake'):
            return self._STOP, 'stop'
        raise ValueError(f'Invalid direction: {direction}')

    def _normalize_side(self, side):
        v = str(side).strip().lower()
        if v in ('left', 'l', 'm1', 'left_motor'):
            return 'left'
        if v in ('right', 'r', 'm2', 'right_motor'):
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
            raise ValueError(f'Speed must be 0-100, got {speed}')
        return duty

    # ------------------------------------------------------------------
    def _set_left_tuple(self, state):
        lgpio.gpio_write(self._h, self.left_in1, state[0])
        lgpio.gpio_write(self._h, self.left_in2, state[1])

    def _set_right_tuple(self, state):
        lgpio.gpio_write(self._h, self.right_in1, state[0])
        lgpio.gpio_write(self._h, self.right_in2, state[1])

    def _apply_left_speed(self, speed):
        duty = self._normalize_speed(speed) * self._left_speed_factor
        self._left_pwm.set_duty(duty)
        self._left_speed = duty
        return duty

    def _apply_right_speed(self, speed):
        duty = self._normalize_speed(speed) * self._right_speed_factor
        self._right_pwm.set_duty(duty)
        self._right_speed = duty
        return duty

    # ------------------------------------------------------------------
    def set_motor(self, side, direction, speed=100):
        side_name = self._normalize_side(side)
        state, norm_dir = self._normalize_direction(direction)
        duty = 0.0 if norm_dir == 'stop' else self._normalize_speed(speed)
        if side_name == 'left':
            self._set_left_tuple(state)
            applied = self._apply_left_speed(duty)
        else:
            self._set_right_tuple(state)
            applied = self._apply_right_speed(duty)
        return {'side': side_name, 'direction': norm_dir, 'speed': applied}

    def drive(self, left_direction, right_direction, left_speed=100, right_speed=100):
        left_state,  left_norm  = self._normalize_direction(left_direction)
        right_state, right_norm = self._normalize_direction(right_direction)
        left_duty  = 0.0 if left_norm  == 'stop' else self._normalize_speed(left_speed)
        right_duty = 0.0 if right_norm == 'stop' else self._normalize_speed(right_speed)
        self._set_left_tuple(left_state)
        self._set_right_tuple(right_state)
        al = self._apply_left_speed(left_duty)
        ar = self._apply_right_speed(right_duty)
        return {'left': left_norm, 'right': right_norm, 'left_speed': al, 'right_speed': ar}

    def set_speed(self, side, speed):
        side_name = self._normalize_side(side)
        if side_name == 'left':
            applied = self._apply_left_speed(speed)
        else:
            applied = self._apply_right_speed(speed)
        return {'side': side_name, 'speed': applied}

    def set_speeds(self, left_speed, right_speed):
        return {'left_speed': self._apply_left_speed(left_speed),
                'right_speed': self._apply_right_speed(right_speed)}

    def set_states(self, m1_in1, m1_in2, m2_in1, m2_in2, left_speed=100, right_speed=100):
        left_state  = (1 if m1_in1 else 0, 1 if m1_in2 else 0)
        right_state = (1 if m2_in1 else 0, 1 if m2_in2 else 0)
        self._set_left_tuple(left_state)
        self._set_right_tuple(right_state)
        self._apply_left_speed(0 if left_state  == self._STOP else left_speed)
        self._apply_right_speed(0 if right_state == self._STOP else right_speed)

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
            self._left_pwm.close()
            self._right_pwm.close()
            for pin in self.control_pins:
                try:
                    lgpio.gpio_write(self._h, pin, 0)
                    lgpio.gpio_free(self._h, pin)
                except Exception:
                    pass
            try:
                lgpio.gpiochip_close(self._h)
            except Exception:
                pass
