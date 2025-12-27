import time
from machine import SPI, Pin, Timer
# hard-coded degree (1..7) to frequency in Hz
# 1=C, 2=D, 3=E, 4=F, 5=G, 6=A, 7=B
_DEGREE_FREQ = {
    1: 261,
    2: 294,
    3: 329,
    4: 349,
    5: 392,
    6: 440,
    7: 494,  # octave 4
    11: 523,
    12: 587,
    13: 659,
    14: 698,
    15: 784,
    16: 880,
    17: 988,  # octave 5
}


def _duty_set(pwm, frac):
    if hasattr(pwm, "duty_u16"):
        pwm.duty_u16(int(frac * 65535))
    else:
        pwm.duty(int(frac * 1023))


def play_sequence(pwm, sequence, duty=0.08, gap_s=0.02):
    """
    sequence: list of (degree, duration_s), degree in 1..7
    """
    _duty_set(pwm, 0)
    for degree, dur in sequence:
        freq = _DEGREE_FREQ.get(degree, 0)
        if freq:
            pwm.freq(freq)
            _duty_set(pwm, duty)
            time.sleep(dur)
            _duty_set(pwm, 0)
        else:
            # invalid degree = rest
            time.sleep(dur)
        if gap_s:
            time.sleep(gap_s)
    _duty_set(pwm, 0)


p1.duty(500)
time.sleep(0.5)
p1.duty(0)
time.sleep(0.5)

motor_on = [(7, 0.2), (13, 0.2), (17, 0.2)]
play_sequence(p1, motor_on)
time.sleep(0.3)
motor_on2 = [(17, 0.15), (17, 0.15)]
play_sequence(p1, motor_on2)

time.sleep(1)
example_song = [
    (3, 0.3),
    (2, 0.3),
    (1, 0.3),
    (2, 0.3),
    (3, 0.3),
    (4, 0.3),
    (3, 0.3),
    (2, 0.3),
]

play_sequence(p1, example_song)
