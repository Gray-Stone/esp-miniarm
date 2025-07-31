import pid_control as pc
import time


def main():
    print("Start of main")
    pc.setup()

    pc.test_pid(duration_ms=2000, interval_us = 10000)
# if __name__ == "__main__":

pc.setup()
pc.set_motor(200)
time.sleep_ms(50)
pc.set_motor(0)
time.sleep_ms(50)
pc.set_motor(200)
time.sleep_ms(50)
pc.set_motor(0)
time.sleep_ms(50)
pc.set_motor(200)
time.sleep_ms(50)
pc.set_motor(0)
time.sleep_ms(500)
pc.auto_flip_motor()
pc.test_pid(increment_angle=800)