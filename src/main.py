import pid_control as pc
import time


import network
import time

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    if not wlan.isconnected():
        print(f'Connecting to WiFi SSID="{ssid}"...')
        wlan.connect(ssid, password)

        timeout = 10  # seconds
        for _ in range(timeout * 10):
            if wlan.isconnected():
                break
            time.sleep(0.1)
        else:
            print('❌ WiFi connection failed.')
            return None

    print('✅ Connected:', wlan.ifconfig())
    return wlan

# import os

# if 'config.py' in os.listdir():
#     import config
#     connect_wifi(config.SSID , config.PASSWORD)
# else:
#     print("⚠️ config.py not found.")

# if __name__ == "__main__":

# pc.setup()
# pc.set_motor(200)
# time.sleep_ms(50)
# pc.set_motor(0)
# time.sleep_ms(50)
# pc.set_motor(200)
# time.sleep_ms(50)
# pc.set_motor(0)
# time.sleep_ms(50)
# pc.set_motor(200)
# time.sleep_ms(50)
# pc.set_motor(0)
# time.sleep_ms(500)
# pc.auto_flip_motor()

# pc.test_pid(increment_angle=800)



# import chain_uart

# print("Starting Main Loop")
# chain_uart.main_loop()