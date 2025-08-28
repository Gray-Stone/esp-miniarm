import machine
import time
from machine import SPI, Pin, Timer

from machine import Pin


# ========== Global State ==========
i2c = None
pwm_fwd = None
pwm_rev = None
PWM_FREQUENCEY=2000
# AS5600 config
AS5600_ADDR = 0x36

# Motor control pins (adjust as needed)
PWM_PIN_FWD = 1
PWM_PIN_REV = 3
SCL_PIN = 4
SDA_PIN = 5

# PID state

class PIDParam:
    kp = 2.0
    ki = 5.0
    kd = 0.2
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

    # i2c = machine.I2C(0, scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN))

    init_mt6701()
    print("Hardware initialized.")







# MT6701 SSI (24-bit: 14 angle + 4 status + 6 CRC) via SPI on ESP32/ESP32-C3
# - SPI provides the clock burst (uses HW, typically DMA under the hood)
# - CRC polynomial: x^6 + x + 1 (MSB-first over 18 bits: angle[13:0], status[3:0])
#   Ref: MT6701 datasheet SSI format & timing.


# ===== User config =====
SPI_ID   = 1          # ESP32/ESP32-C3: pick a usable SPI bus id
PIN_SCK  = 4          # to MT6701 CLK
PIN_MISO = 5          # from MT6701 DO
PIN_CS   = 6          # to MT6701 CSN (active low)
SPI_BAUD = 1_000_00  # 1 MHz (datasheet allows higher if wiring is good)
SPI_MODE = 1          # CPOL=0, CPHA=1: sample on falling edge (data changes on rising)

BITS_POS   = 14
BITS_STAT  = 4
BITS_CRC   = 6
FRAME_BITS = BITS_POS + BITS_STAT + BITS_CRC  # 24
DEG_PER_TURN = 360.0

# ===== Init =====

def init_mt6701():
    global cs, spi
    cs  = Pin(PIN_CS, Pin.OUT, value=1)
    spi = SPI(SPI_ID, baudrate=SPI_BAUD, polarity=0, phase=1,
            sck=Pin(PIN_SCK), mosi=None, miso=Pin(PIN_MISO))

# ===== CRC-6 (poly x^6 + x + 1) helper =====
# Polynomial (including top bit) is 0b1_000011 = 0x43; use lower 6 bits (0x03) in feedback form.
def crc6_mt6701_msb_first(value_18bits):
    rem = 0        # 6-bit remainder
    poly_lo = 0x03 # polynomial without the x^6 term
    for i in range(17, -1, -1):  # process 18 bits MSB->LSB
        bit = (value_18bits >> i) & 1
        fb = ((rem >> 5) & 1) ^ bit
        rem = ((rem << 1) & 0x3F)
        if fb:
            rem ^= poly_lo
    return rem  # 6-bit CRC

# ===== Low-level: read one 24-bit SSI frame =====
def _read_frame24():
    buf = bytearray(3)
    cs.value(0)
    # small setup/hold margins; datasheet margins are sub-µs, so 1 µs is safe
    time.sleep_us(30)
    spi.readinto(buf)   # clocks 24 SCK edges; hardware handles shifting
    time.sleep_us(1)
    cs.value(1)
    return (buf[0] << 16) | (buf[1] << 8) | buf[2]

# ===== Parse + CRC check =====
def read_mt6701():
    raw24 = _read_frame24()
    # Bits: [23:10]=angle(14), [9:6]=status(4), [5:0]=crc(6)  (MSB-first)
    angle14 = (raw24 >> 10) & 0x3FFF
    status4 = (raw24 >> 6)  & 0x000F
    crc_rx  =  raw24        & 0x003F

    # Compute CRC over the 18-bit concatenation of angle+status (MSB-first)
    data18 = (angle14 << 4) | status4
    crc_calc = crc6_mt6701_msb_first(data18)
    crc_ok = (crc_calc == crc_rx)

    # Convert to degrees (0..360)
    angle_deg = (angle14 * DEG_PER_TURN) / (1 << BITS_POS)
    return angle_deg, angle14, status4, crc_rx, crc_calc, crc_ok

# ===== Example: poll at 500 Hz and print when CRC passes =====

def loop_mt6707_read(duration_s = 1):
    start_time = time.ticks_ms()    
    while time.ticks_diff(time.ticks_ms(), start_time) < duration_s * 1000:
        ang_deg, angle14, stat, crc_rx, crc_calc, ok = read_mt6701()
        if ok:
            print("deg=%.3f  angle14=%5d  status=0x%X  CRC ok" % (ang_deg, angle14, stat))
        else:
            print("deg=%.3f  angle14=%5d  status=0x%X  CRC ok" % (ang_deg, angle14, stat))
            print("CRC FAIL: rx=%02X calc=%02X  status=0x%X" % (crc_rx, crc_calc, stat))
        time.sleep(0.002)  # 2 ms
























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
        
        dt = time.ticks_diff(now, last_time) / 1000000.0
        err = angle_diff(target_position , pos)
        velocity = angle_diff(pos , last_pos)

        pterm = pid_param.kp * err

        derivative = (err - last_error) / dt
        if dt > ( (interval_us/1e6) * 0.3):
            dterm = pid_param.kd * derivative
        else:
            # Too small a dt, 
            print("dt too small, snapping to zero.")
            dterm = 0

        # Integral with anti-windup
        integral += err * dt
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

