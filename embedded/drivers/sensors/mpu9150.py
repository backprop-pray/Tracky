import smbus2
import time
import math


class MPU9150:
    # MPU-9150 I2C address
    ADDRESS_DEFAULT = 0x68
    ADDRESS_ALT     = 0x69

    # Power management
    REG_PWR_MGMT_1  = 0x6B
    REG_PWR_MGMT_2  = 0x6C

    # Gyroscope config
    REG_GYRO_CONFIG = 0x1B
    REG_GYRO_XOUT_H = 0x43

    # Accelerometer config
    REG_ACCEL_CONFIG = 0x1C
    REG_ACCEL_XOUT_H = 0x3B

    # Temperature
    REG_TEMP_OUT_H = 0x41

    # Bypass mode (expose AK8975 magnetometer on same I2C bus)
    REG_INT_PIN_CFG = 0x37

    # AK8975 magnetometer (accessible after bypass enabled)
    MAG_ADDRESS    = 0x0C
    MAG_REG_CNTL   = 0x0A
    MAG_REG_ST1    = 0x02
    MAG_REG_HXL    = 0x03
    MAG_MODE_SINGLE = 0x01

    # Full-scale range scales
    GYRO_SCALE  = {0: 131.0, 1: 65.5, 2: 32.8, 3: 16.4}   # LSB/(deg/s)
    ACCEL_SCALE = {0: 16384.0, 1: 8192.0, 2: 4096.0, 3: 2048.0}  # LSB/g

    def __init__(self, bus=1, address=ADDRESS_DEFAULT, gyro_range=0, accel_range=0):
        self._bus = smbus2.SMBus(bus)
        self._addr = address
        self._gyro_range = gyro_range
        self._accel_range = accel_range
        self._mag_available = False
        self._init()

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _init(self):
        # Wake up — clear SLEEP bit, use PLL with X-gyro reference
        self._bus.write_byte_data(self._addr, self.REG_PWR_MGMT_1, 0x01)
        time.sleep(0.1)

        # Gyro full-scale
        self._bus.write_byte_data(self._addr, self.REG_GYRO_CONFIG,
                                  self._gyro_range << 3)

        # Accel full-scale
        self._bus.write_byte_data(self._addr, self.REG_ACCEL_CONFIG,
                                  self._accel_range << 3)

        # Enable bypass so AK8975 appears directly on I2C bus
        self._bus.write_byte_data(self._addr, self.REG_INT_PIN_CFG, 0x02)
        time.sleep(0.05)

        # Probe magnetometer
        try:
            self._bus.read_byte_data(self.MAG_ADDRESS, self.MAG_REG_ST1)
            self._mag_available = True
        except OSError:
            self._mag_available = False

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _read_word_signed(self, reg):
        high = self._bus.read_byte_data(self._addr, reg)
        low  = self._bus.read_byte_data(self._addr, reg + 1)
        val  = (high << 8) | low
        return val - 65536 if val >= 32768 else val

    def _read_block(self, addr, reg, length):
        return self._bus.read_i2c_block_data(addr, reg, length)

    # ------------------------------------------------------------------
    # Accelerometer  (returns g)
    # ------------------------------------------------------------------

    def read_accel_raw(self):
        data = self._read_block(self._addr, self.REG_ACCEL_XOUT_H, 6)
        def _s16(h, l):
            v = (h << 8) | l
            return v - 65536 if v >= 32768 else v
        return (_s16(data[0], data[1]),
                _s16(data[2], data[3]),
                _s16(data[4], data[5]))

    def read_accel(self):
        scale = self.ACCEL_SCALE[self._accel_range]
        ax, ay, az = self.read_accel_raw()
        return (round(ax / scale, 5),
                round(ay / scale, 5),
                round(az / scale, 5))

    # ------------------------------------------------------------------
    # Gyroscope  (returns deg/s)
    # ------------------------------------------------------------------

    def read_gyro_raw(self):
        data = self._read_block(self._addr, self.REG_GYRO_XOUT_H, 6)
        def _s16(h, l):
            v = (h << 8) | l
            return v - 65536 if v >= 32768 else v
        return (_s16(data[0], data[1]),
                _s16(data[2], data[3]),
                _s16(data[4], data[5]))

    def read_gyro(self):
        scale = self.GYRO_SCALE[self._gyro_range]
        gx, gy, gz = self.read_gyro_raw()
        return (round(gx / scale, 4),
                round(gy / scale, 4),
                round(gz / scale, 4))

    # ------------------------------------------------------------------
    # Temperature  (returns °C)
    # ------------------------------------------------------------------

    def read_temperature(self):
        raw = self._read_word_signed(self.REG_TEMP_OUT_H)
        return round(raw / 340.0 + 36.53, 2)

    # ------------------------------------------------------------------
    # Magnetometer AK8975  (returns µT)
    # ------------------------------------------------------------------

    def read_mag(self):
        if not self._mag_available:
            return None
        # Trigger single measurement
        self._bus.write_byte_data(self.MAG_ADDRESS, self.MAG_REG_CNTL,
                                  self.MAG_MODE_SINGLE)
        time.sleep(0.01)
        # Wait for data-ready
        for _ in range(10):
            st1 = self._bus.read_byte_data(self.MAG_ADDRESS, self.MAG_REG_ST1)
            if st1 & 0x01:
                break
            time.sleep(0.002)
        data = self._read_block(self.MAG_ADDRESS, self.MAG_REG_HXL, 6)
        def _s16(l, h):
            v = (h << 8) | l
            return v - 65536 if v >= 32768 else v
        # AK8975 sensitivity: 0.3 µT/LSB
        mx = round(_s16(data[0], data[1]) * 0.3, 3)
        my = round(_s16(data[2], data[3]) * 0.3, 3)
        mz = round(_s16(data[4], data[5]) * 0.3, 3)
        return (mx, my, mz)

    # ------------------------------------------------------------------
    # Derived: roll & pitch from accelerometer (degrees)
    # ------------------------------------------------------------------

    def read_orientation(self):
        ax, ay, az = self.read_accel()
        roll  = round(math.degrees(math.atan2(ay, az)), 3)
        pitch = round(math.degrees(math.atan2(-ax, math.sqrt(ay**2 + az**2))), 3)
        return {'roll': roll, 'pitch': pitch}

    # ------------------------------------------------------------------
    # Convenience: read everything at once
    # ------------------------------------------------------------------

    def read_all(self):
        ax, ay, az = self.read_accel()
        gx, gy, gz = self.read_gyro()
        temp = self.read_temperature()
        mag  = self.read_mag()
        ori  = self.read_orientation()
        result = {
            'accel':  {'x': ax, 'y': ay, 'z': az},
            'gyro':   {'x': gx, 'y': gy, 'z': gz},
            'temp_c': temp,
            'orientation': ori,
        }
        if mag is not None:
            result['mag'] = {'x': mag[0], 'y': mag[1], 'z': mag[2]}
        return result

    # ------------------------------------------------------------------

    def close(self):
        self._bus.close()
