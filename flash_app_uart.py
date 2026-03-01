import serial
import time

# ================= CONFIG =================
PORT = "COM4"
BAUD = 115200
CHUNK_SIZE = 128
APP_BIN = r"C:\Users\HP\Documents\work_space\Flashing_by_UART\test_boot_uart\Debug\test_boot_uart.bin"
ACK = b'\x79'
ERR = b'\x1F'
END = 0xFFFF

ser = serial.Serial(PORT, BAUD, timeout=5)

# ================= UTILS =================
def wait_byte(expected, timeout=5):
    start = time.time()
    while True:
        if ser.in_waiting:
            b = ser.read(1)
            print(f"[RX]: {b}")
            if b == expected:
                return True
            if b == ERR:
                print("STM32 ERROR")
                return False
        if time.time() - start > timeout:
            print("TIMEOUT")
            return False

def send_command(cmd):
    ser.write(cmd)
    ser.flush()
    print(f"[TX]: {cmd}")

def listen_for_app(timeout=5):
    """Listen for any message from app after jump"""
    print("Listening for APP startup message...")
    start = time.time()
    buffer = b""
    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            buffer += data
            print(f"[APP MSG]: {data.decode('utf-8', errors='ignore')}")
        time.sleep(0.05)  # fast polling
    if not buffer:
        print("No message received from APP")

# ================= BOOT SYNC =================
def enter_bootloader():
    print("Trying to enter bootloader...")
    ser.reset_input_buffer()
    for _ in range(5):
        send_command(b'F')
        time.sleep(0.2)
        if wait_byte(ACK, timeout=1):
            print("Bootloader ready")
            return True
    print("Failed to enter bootloader")
    return False

# ================= FLASH =================
def flash_firmware():
    print("Waiting erase ACK...")
    if not wait_byte(ACK, timeout=5):
        print("Erase failed")
        return False
    print("Erase OK")

    chunk_id = 0
    with open(APP_BIN, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            size = len(chunk)
            size_bytes = size.to_bytes(2, 'little')
            print(f"\n[Chunk {chunk_id}] Size: {size}")

            send_command(size_bytes)
            if not wait_byte(ACK):
                return False

            send_command(chunk)
            if not wait_byte(ACK):
                return False

            print(f"Chunk {chunk_id} OK")
            chunk_id += 1

    print("Sending END...")
    send_command(END.to_bytes(2, 'little'))
    if not wait_byte(ACK):
        print("END not acknowledged")
        return False

    print("[Flash completed!]")
    return True

# ================= APPLICATION MODE =================
def application_mode():
    print("\nSwitched to APPLICATION MODE")
    print("Commands: T = toggle LED, F = flash, J = jump\n")

    try:
        while True:
            # ALWAYS read incoming data first
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                print(f"[APP RX]: {data.decode('utf-8', errors='ignore')}")

            user = input("> ").upper()

            if user == 'T':
                send_command(b'T')

            elif user == 'F':
                print("Requesting bootloader...")
                send_command(b'F')
                time.sleep(1)
                ser.reset_input_buffer()
                if enter_bootloader():
                    if flash_firmware():
                        print("Waiting for MCU to auto-jump...")
                        listen_for_app(timeout=5)  # no sleep, listen immediately
                return

            elif user == 'J':
                print("Jumping to APP...")
                send_command(b'J')
                if wait_byte(ACK, timeout=2):
                    print("Bootloader confirmed jump")
                    listen_for_app(timeout=5)  # no sleep, listen immediately
                else:
                    print("Jump failed or no ACK")

    except KeyboardInterrupt:
        print("\nExit")

# ================= MAIN =================
def main():
    print(f"Connected to {PORT}")
    cmd = input("Press 'F' to flash or J to jump: ").lower()
    if cmd == 'f':
        if enter_bootloader():
            if flash_firmware():
                print("Flash done, listening for app...")
                listen_for_app(timeout=5)  # no sleep, listen immediately
                application_mode()
    elif cmd == 'j':
        print("Jumping to APP...")
        send_command(b'J')
        if wait_byte(ACK, timeout=2):
            print("Bootloader confirmed jump")
            listen_for_app(timeout=5)  # no sleep, listen immediately
            application_mode()

if __name__ == "__main__":
    try:
        main()
    finally:
        ser.close()