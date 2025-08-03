import machine
import time
import select

# === CONFIGURABLE UART PINS ===
TX_PIN = 0  # Replace with your wiring
RX_PIN = 1
BAUDRATE = 9600  # Keep it low for reliability

# === INIT UART ===
uart = machine.UART(1, tx=machine.Pin(TX_PIN), rx=machine.Pin(RX_PIN), baudrate=BAUDRATE)

# === Simple framing ===
START = b'\xAA'
END = b'\xA5'

# === IDENTITY ===
NODE_ID = 2  # Give each board a different ID (1, 2, 3)

# === Message to inject (only node 1 will send) ===
def inject_message():
    payload = b'Hello from Node [%d]' % NODE_ID
    framed = START + bytes([b' ' , NODE_ID]) + payload + END
    uart.write(framed)
    print("[TX] Injected:", framed)

# === Process incoming data ===
def process_uart():
    buf = bytearray()
    poller = select.poll()
    poller.register(uart, select.POLLIN)
    byte_timeout_ms = int((10 / BAUDRATE) * 1000 * 2)  # 2x margin

    if not uart.any():
        # nothing to recv.
        return False

    while True:
        events = poller.poll(byte_timeout_ms)
        if uart.any():
            b = uart.read(1)
            if not b:
                continue
            if b == START:
                buf = bytearray()
                buf.append(b[0])
                buf.extend(b'- via [%d]' % NODE_ID)
            elif b == END:
                buf.append(b[0])
                print("[RX]", bytes(buf))
                time.sleep(0.01)
                if NODE_ID ==1 :
                    # Kill the loop
                    return True
                else:
                    uart.write(buf)  # Forward it
                    print("[TX] Forwarded content:" , buf)
                    return False
            else:
                buf.append(b[0])
        else:
            print(f"poll timeout, event state {events}")
            break
    print("buf content: ", bytes(buf))
    return False


# === Main loop ===
def main_loop():
    print("Node %d started" % NODE_ID)
    time.sleep(0.5)

    if NODE_ID == 1:
        inject_message()

    while True:
        if (process_uart()):
            break
        time.sleep(0.01)

