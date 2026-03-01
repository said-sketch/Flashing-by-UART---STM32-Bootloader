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

def listen_for_app(timeout=8):
    print("Listening for APP...")
    time.sleep(2)
    start = time.time()
    buffer = b""
    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            buffer += data
            print(f"[APP MSG]: {data.decode('utf-8', errors='ignore')}")
        time.sleep(0.05)
    if not buffer:
        print("No message from APP")

def sync_bootloader(timeout=10):
    """Send F or J repeatedly until bootloader responds with ACK"""
    print("Syncing with bootloader... Press RESET on board now!")
    start = time.time()
    while time.time() - start < timeout:
        ser.reset_input_buffer()
        ser.write(current_cmd)
        ser.flush()
        time.sleep(0.2)
        if ser.in_waiting:
            b = ser.read(1)
            if b == ACK:
                print("Bootloader synced!")
                return True
    print("Bootloader not responding!")
    return False

# ================= FLASH =================
def flash_firmware():
    print("Waiting erase ACK...")
    if not wait_byte(ACK, timeout=10):
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
            print(f"[Chunk {chunk_id}] Size: {size}")

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

# ================= BOOTLOADER MODE =================
def bootloader_mode():
    print("\nBOOTLOADER MODE")
    print("Commands: F = flash, J = jump to app\n")

    while True:
        cmd = input(">> ").lower()

        if cmd == 'f':
            ser.reset_input_buffer()
            send_command(b'F')
            if wait_byte(ACK, timeout=5):
                if flash_firmware():
                    print("Flash done!")
                    listen_for_app(timeout=8)
                    application_mode()
                    return
            else:
                print("No response — press RESET and try again")

        elif cmd == 'j':
            ser.reset_input_buffer()
            send_command(b'J')
            if wait_byte(ACK, timeout=5):
                print("Jumping to APP...")
                listen_for_app(timeout=8)
                application_mode()
                return
            else:
                print("No response — press RESET and try again")

# ================= APPLICATION MODE =================
def application_mode():
    print("\nAPPLICATION MODE")
    print("Commands: T = toggle LED, R = reset to bootloader\n")

    try:
        while True:
            try:
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    print(f"[APP RX]: {data.decode('utf-8', errors='ignore')}")
            except Exception:
                pass

            user = input("> ").upper()

            if user == 'T':
                send_command(b'T')

            elif user == 'R':
                send_command(b'R')
                print("Jumping back to bootloader...")
                time.sleep(1)
                ser.reset_input_buffer()
                bootloader_mode()
                return

    except KeyboardInterrupt:
        print("\nExit")

# ================= MAIN =================
def main():
    print(f"Connected to {PORT}")
    print("Press RESET on board, then choose command")
    print("Commands: F = flash, J = jump\n")

    while True:
        cmd = input(">> ").lower()

        if cmd == 'f':
            ser.reset_input_buffer()
            send_command(b'F')
            if wait_byte(ACK, timeout=5):
                if flash_firmware():
                    print("Flash done!")
                    listen_for_app(timeout=8)
                    application_mode()
                    return
            else:
                print("No response — press RESET and try again")

        elif cmd == 'j':
            ser.reset_input_buffer()
            send_command(b'J')
            if wait_byte(ACK, timeout=5):
                print("Jumping to APP...")
                listen_for_app(timeout=8)
                application_mode()
                return
            else:
                print("No response — press RESET and try again")

if __name__ == "__main__":
    try:
        main()
    finally:
        ser.close()