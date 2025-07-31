import machine
import time

from machine import Pin


# ========== Global State ==========
i2c = None
pwm_fwd = None
pwm_rev = None
PWM_FREQUENCEY=2000
# AS5600 config
AS5600_ADDR = 0x36

# Motor control pins (adjust as needed)
PWM_PIN_FWD = 2
PWM_PIN_REV = 3
SCL_PIN = 4
SDA_PIN = 5

# PID state

class PIDParam:
    kp = 1.5
    ki = 5.0
    kd = 0.1
    def __str__(self):
        return f"kp:{self.kp} , ki:{self.ki} , kd:{self.kd}"

pid_param = PIDParam()


# ========== Setup Functions ==========

def print_vars():
    print(f"pwm fwd pin{PWM_PIN_FWD} , rev pin {PWM_PIN_REV}")
    print(f"I2C SCL {SCL_PIN} , SDA {SDA_PIN}")
    print(f"PID param {pid_param}")
    

def setup():
    global pwm_fwd, pwm_rev, i2c

    pwm_fwd = machine.PWM(machine.Pin(PWM_PIN_FWD), freq=PWM_FREQUENCEY)
    pwm_rev = machine.PWM(machine.Pin(PWM_PIN_REV), freq=PWM_FREQUENCEY)
    pwm_fwd.duty(0)
    pwm_rev.duty(0)

    i2c = machine.I2C(0, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN))
    print("Hardware initialized.")

# ========== Encoder and Motor Utilities ==========

def read_encoder():
    raw = i2c.readfrom_mem(AS5600_ADDR, 0x0C, 2)
    return ((raw[0] << 8) | raw[1]) & 0x0FFF

def round_angle(encoder_raw):
    return (encoder_raw + 2048) % 4096 - 2048

def angle_diff(a, b):
    return (a - b + 2048) % 4096 - 2048

def set_motor(power):
    power = max(min(int(power), 1023), -1023)
    if power > 0:
        pwm_fwd.duty(power)
        pwm_rev.duty(0)
    elif power < 0:
        pwm_fwd.duty(0)
        pwm_rev.duty(-power)
    else:
        pwm_fwd.duty(0)
        pwm_rev.duty(0)

# ========== Test Utilities ==========

def print_encoder_while_powering(motor_val , duration_ms = 1000 , interval_ms = 10):
    set_motor(motor_val)
    start_time = time.ticks_ms()
    while (time.ticks_ms() - start_time) < duration_ms:
        print("Encoder:", read_encoder())
        time.sleep_ms(interval_ms)
    set_motor(0)

def test_encoder():
    print("Encoder:", read_encoder())

def test_motor(pwm_value):
    print("Setting motor to:", pwm_value)
    set_motor(pwm_value)

def is_motor_positive_encoder_increment():
    # Do 2 encoder reading while moving the motor a tiny bit.
    # Base on if the encoder reading is increasing or decreasing,
    # We know if the positive motor power is encoder increment or not.
    set_motor(500)
    encoder_1 = read_encoder()
    time.sleep_ms(100)
    encoder_2 = read_encoder()
    set_motor(0)
    print(f"e1 {encoder_1} e2 {encoder_2}")
    if angle_diff(encoder_2 , encoder_1) > 0:
        return True
    else:
        return False

def auto_flip_motor():
    if not is_motor_positive_encoder_increment():
        print("Motor direction is wrong, flipping Pins.")
        global pwm_fwd, pwm_rev
        pwm_fwd = machine.PWM(machine.Pin(PWM_PIN_REV), freq=PWM_FREQUENCEY)
        pwm_rev = machine.PWM(machine.Pin(PWM_PIN_FWD), freq=PWM_FREQUENCEY)

# ========== PID Control Loop ==========

def pid_run(target_position ,duration_ms=2000, interval_us = 10000):
    # Local state variables
    last_pos = read_encoder()
    integral = 0.0
    last_error = 0.0
    last_time = time.ticks_us()
    start_time = time.ticks_ms()
    
    # PID safety limits
    MAX_I_TERM = 1000.0  # Prevent integral windup
    MAX_OUTPUT = 1023.0    # Match motor limits
    
    
    while time.ticks_diff( time.ticks_ms() , start_time) < duration_ms  :
        # PID step calculation
        now = time.ticks_us()
        pos = read_encoder()
        
        # dt in second with safety limits
        dt = time.ticks_diff(now, last_time) / 1000000.0
        err = angle_diff(target_position , pos)
        velocity = angle_diff(pos , last_pos)

        # Integral with anti-windup
        integral += err * dt

        # Calculate PID terms
        pterm = pid_param.kp * err

        derivative = (err - last_error) / dt

        if dt > ( (interval_us/1e6) * 0.3):
            dterm = pid_param.kd * derivative

        else:
            # Too small a dt, 
            print("dt too small, snapping to zero.")
            dterm = 0

        iterm = pid_param.ki * integral
        if abs(iterm) > MAX_I_TERM:
            print(f"Warning: I term saturated to {iterm}")
            iterm = MAX_I_TERM if iterm > 0 else -MAX_I_TERM

        # Combine and limit output
        output = pterm + dterm + iterm
        if abs(output) > MAX_OUTPUT:
            print(f"Warning: Output saturated to {output}")
            output = MAX_OUTPUT if output > 0 else -MAX_OUTPUT
        
        set_motor(output)

        print(f"t:{now} , dt:{dt} ,\t pos:{pos} ,\t err:{err} ,\t vel:{velocity} , pterm:{pterm:.4f} , dterm:{dterm:.4f} , iterm:{iterm:.4f} , output:{output:.2f}")

        last_time = now
        last_pos = pos
        last_error = err

        time.sleep_us(interval_us)
        
    # set motor back.
    set_motor(0)

def test_pid(increment_angle = 400 , duration_ms=2000, interval_us = 10000):
    current_pos = read_encoder()
    target_position = round_angle(current_pos + increment_angle)
    pid_run(target_position , duration_ms , interval_us)

# ========== Helpers ==========

def get_pid():
    return pid_param

def set_pid(kp, ki, kd):
    pid_param.kp = kp
    pid_param.ki = ki
    pid_param.kd = kd
    print(f"PID updated to {pid_param}")

