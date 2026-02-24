import serial
import time

# ================= CONFIG =================
PORT = "COM4"
BAUD = 115200
CHUNK_SIZE = 128   # safer than 256
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
    ser.flush()  #VERY IMPORTANT
    print(f"[TX]: {cmd}")

# ================= BOOT SYNC =================
def enter_bootloader():
    print("Trying to enter bootloader...")
    ser.reset_input_buffer()

    for _ in range(5):
        send_command(b'F')  # works for both APP & BOOT
        time.sleep(0.2)

        if wait_byte(ACK, timeout=1):
            print("Bootloader ready")
            return True

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
            size_bytes = size.to_bytes(2, 'big')  # match STM32

            print(f"\n[Chunk {chunk_id}] Size: {size}")

            # ===== SEND SIZE =====
            send_command(size_bytes)

            if not wait_byte(ACK):
                return False

            # ===== SEND DATA =====
            send_command(chunk)

            if not wait_byte(ACK):
                return False

            print(f"Chunk {chunk_id} OK")
            chunk_id += 1

    # ===== END =====
    print("Sending END...")
    send_command(END.to_bytes(2, 'big'))

    if not wait_byte(ACK):
        print("END not acknowledged")
        return False

    print("[Flash completed!]")
    return True

# ================= APPLICATION MODE =================
def application_mode():
    print("\nSwitched to APPLICATION MODE")
    print("Commands: T = toggle LED, F = flash\n")

    try:
        while True:
            # ALWAYS read incoming data
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                print(f"[APP RX]: {data}")

            # Non-blocking user input
            user = input("> ").upper()

            if user == 'T':
                send_command(b'T')

            elif user == 'F':
                print("Requesting bootloader...")
                send_command(b'F')

                time.sleep(1)
                ser.reset_input_buffer()

                if enter_bootloader():
                    flash_firmware()
                    return

    except KeyboardInterrupt:
        print("\nExit")
# ================= MAIN =================
def main():
    print(f"Connected to {PORT}")

    cmd = input("Press 'F' to flash: ").lower()

    if cmd == 'f':
        if enter_bootloader():
            if flash_firmware():
                print("Waiting for MCU to jump...")
                time.sleep(2)
                application_mode()

if __name__ == "__main__":
    try:
        main()
    finally:
        ser.close()