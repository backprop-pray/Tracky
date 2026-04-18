import time, sys
sys.path.insert(0, "/home/yasen/patatnik/embedded")
from drivers.sensors.mpu9150 import MPU9150

imu = MPU9150(bus=1, address=0x68)

print("MPU9150 demo -- press Ctrl+C to stop")
print("-" * 50)

try:
    while True:
        d = imu.read_all()
        a = d["accel"]
        g = d["gyro"]
        o = d["orientation"]
        mag = d.get("mag")
        ax, ay, az = a["x"], a["y"], a["z"]
        gx, gy, gz = g["x"], g["y"], g["z"]
        print("Accel  (g)    x=%+7.4f  y=%+7.4f  z=%+7.4f" % (ax, ay, az))
        print("Gyro   (d/s)  x=%+8.3f  y=%+8.3f  z=%+8.3f" % (gx, gy, gz))
        print("Temp   (C)    %.2f" % d["temp_c"])
        print("Orient        roll=%+7.2f  pitch=%+7.2f" % (o["roll"], o["pitch"]))
        if mag:
            print("Mag    (uT)   x=%+8.3f  y=%+8.3f  z=%+8.3f" % (mag["x"], mag["y"], mag["z"]))
        print("-" * 50)
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    imu.close()
    print("closed.")
