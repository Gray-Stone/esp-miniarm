from machine import I2C, Pin
import time

# -------- User I2C pins/rate --------
SCL_PIN = 4
SDA_PIN = 5
CSN_PIN = 6
I2C_FREQ = 400_000

# MT6701 addresses (7-bit). Default is 0x06; some units may be 0x46.
ADDRS = [0x06, 0x46]

# Key register addresses from datasheet
REG_ANGLE_H = 0x03   # Angle[13:6]
REG_ANGLE_L = 0x04   # Angle[5:0]
# EEPROM / Config map (subset)
REG_UVW_MUX  = 0x25
REG_ABZ_MUX  = 0x29
REG_ABZ_RES_HL = 0x30  # [7:4] UVW_RES, [1:0] ABZ_RES[9:8]
REG_ABZ_RES_L  = 0x31  # [7:0] ABZ_RES[7:0]
REG_ZERO_H   = 0x32    # [3:0] ZERO[11:8]; also HYST[2], Z_PULSE_WIDTH[2:0]
REG_ZERO_L   = 0x33    # ZERO[7:0]
REG_HYST_L   = 0x34    # HYST[1:0]
REG_OUTMODE  = 0x38    # [7] PWM_FREQ, [6] PWM_POL, [5] OUT_MODE
REG_A_STARTH = 0x3F
REG_A_STARTH = 0x3E    # [3:0] A_START[11:8]; [7:4] A_STOP[11:8]
REG_A_STARTL = 0x3F    # A_START[7:0]
REG_A_STOPL  = 0x40    # A_STOP[7:0]

csn = Pin(CSN_PIN, Pin.OUT, value=1)  # keep high

def find_mt6701(i2c):
    found = i2c.scan()
    print(f"i2c scan out {found}")
    for addr in ADDRS:
        if addr in found:
            return addr
    return None

def r8(i2c, addr, reg):
    # Single-byte register read
    return i2c.readfrom_mem(addr, reg, 1)[0]

def read_angle_counts(i2c, addr):
    # Datasheet: read 0x03 first, then 0x04
    hi = r8(i2c, addr, REG_ANGLE_H)
    lo = r8(i2c, addr, REG_ANGLE_L)
    angle14 = ((hi << 6) | (lo >> 2)) & 0x3FFF
    return angle14

def decode_config(i2c, addr):
    cfg = {}

    uvw_mux = r8(i2c, addr, REG_UVW_MUX)
    abz_mux = r8(i2c, addr, REG_ABZ_MUX)
    cfg["UVW_MUX_bit7"] = (uvw_mux >> 7) & 1       # 0:UVW, 1:-A -B -Z (QFN)  [doc labels]
    cfg["ABZ_MUX_bit6"] = (abz_mux >> 6) & 1       # 0:ABZ, 1:UVW
    cfg["DIR_bit1"]     = (abz_mux >> 1) & 1       # 0:CCW, 1:CW

    r30 = r8(i2c, addr, REG_ABZ_RES_HL)
    r31 = r8(i2c, addr, REG_ABZ_RES_L)
    uvw_res = (r30 >> 4) & 0x0F                    # UVW pole-pairs
    abz_res = ((r30 & 0x03) << 8) | r31            # ABZ PPR (1..1024)
    cfg["UVW_RES_pole_pairs"] = uvw_res
    cfg["ABZ_RES_ppr"] = abz_res

    r32 = r8(i2c, addr, REG_ZERO_H)
    r33 = r8(i2c, addr, REG_ZERO_L)
    r34 = r8(i2c, addr, REG_HYST_L)

    hyst2 = (r32 >> 7) & 1
    z_pw  = (r32 >> 4) & 0x07                      # 0..6 valid per table
    zero  = ((r32 & 0x0F) << 8) | r33              # 12-bit ZERO
    hyst10 = (r34 >> 6) & 0x03
    cfg["HYST_code"] = (hyst2 << 2) | hyst10       # map to table in datasheet
    cfg["Z_PULSE_WIDTH_code"] = z_pw               # see table for 1,2,4,8,12,16 LSB or 180°
    cfg["ZERO_code"] = zero                        # 0..4095 (0..360°)

    r38 = r8(i2c, addr, REG_OUTMODE)
    cfg["PWM_FREQ_bit7"] = (r38 >> 7) & 1          # 0:~994Hz, 1:~497Hz
    cfg["PWM_POL_bit6"]  = (r38 >> 6) & 1          # 0:active-high, 1:active-low
    cfg["OUT_MODE_bit5"] = (r38 >> 5) & 1          # 0:Analog OUT, 1:PWM OUT

    # helpful human-readable fields
    cfg["Direction"] = "CW" if cfg["DIR_bit1"] else "CCW"
    cfg["OUT_PIN_MODE"] = "PWM" if cfg["OUT_MODE_bit5"] else "Analog"
    cfg["Z_PULSE_WIDTH_desc"] = {
        0: "1 LSB", 1: "2 LSB", 2: "4 LSB", 3: "8 LSB",
        4: "12 LSB", 5: "16 LSB", 6: "180°", 7: "1 LSB (dup)"
    }.get(z_pw, "unknown")

    cfg["ZERO_degrees"] = zero * (360.0/4096.0)    # 12-bit zero offset
    return cfg

# ---- demo ----
i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
addr = find_mt6701(i2c)
if addr is None:
    raise RuntimeError("MT6701 not found on I2C bus (tried 0x06, 0x46)")

ang = read_angle_counts(i2c, addr)  # quick sanity
deg = ang * (360.0/16384.0)
print("Angle counts:", ang, "Angle deg:", deg)

cfg = decode_config(i2c, addr)
for k, v in cfg.items():
    print(f"{k}: {v}")
