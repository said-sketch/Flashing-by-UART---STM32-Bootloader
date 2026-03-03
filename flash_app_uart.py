import serial
import time
import struct

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
            print(f"[RX RAW]: {b}")  # ← print everything
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
    print("Listening for APP...")
    time.sleep(0.2)
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
# ================= Synchronyze fun =================
def sync_and_flash():
    """Send F repeatedly until bootloader responds"""
    print("Syncing with bootloader...")
    start = time.time()
    while time.time() - start < 10:
        ser.reset_input_buffer()
        ser.write(b'F')
        ser.flush()
        time.sleep(0.2)
        if ser.in_waiting:
            b = ser.read(1)
            if b == ACK:
                print("Bootloader ready!")
                return True
    print("No response — press RESET and try again")
    return False
# ================= CRC32 =================
def stm32_crc32(data):
    crc = 0xFFFFFFFF
    poly = 0x04C11DB7

    for i in range(0, len(data), 4):
        # Read 32-bit word little endian (like STM32 memory)
        word = int.from_bytes(data[i:i+4], 'little')

        # Feed MSB first (important!)
        for bit in range(32):
            bit_val = (word >> (31 - bit)) & 1
            c31 = (crc >> 31) & 1

            crc <<= 1
            if c31 ^ bit_val:
                crc ^= poly

            crc &= 0xFFFFFFFF

    return crc

def calculate_crc32(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    while len(data) % 4 != 0:
        data += b'\xFF'
    crc = stm32_crc32(data)
    return crc, len(data)

# ================= FLASH =================
def flash_firmware():
    # Step 1: Calculate CRC
    crc, file_size = calculate_crc32(APP_BIN)
    print(f"CRC32: 0x{crc:08X} Size: {file_size} bytes")

    # Step 2: Send CRC — bootloader is waiting for this right after F ACK
    crc_bytes = struct.pack('<I', crc)
    send_command(crc_bytes)
    if not wait_byte(ACK, timeout=5):
        print("CRC send failed")
        return False
    print("CRC sent OK")

    # Step 3: Wait erase ACK
    print("Waiting erase ACK...")
    if not wait_byte(ACK, timeout=10):
        print("Erase failed")
        return False
    print("Erase OK")

    # Step 4: Send chunks
    chunk_id = 0
    with open(APP_BIN, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunk_size = len(chunk)
            send_command(chunk_size.to_bytes(2, 'little'))
            if not wait_byte(ACK):
                return False
            send_command(chunk)
            if not wait_byte(ACK):
                return False
            print(f"Chunk {chunk_id} OK")
            chunk_id += 1

    # Step 5: Send END
    print("Sending END...")
    send_command(END.to_bytes(2, 'little'))
    if not wait_byte(ACK):
        return False

    # Step 6: Wait CRC verification
    print("Waiting CRC verification...")
    if not wait_byte(ACK, timeout=5):
        print("CRC FAILED — bad firmware erased!")
        return False

    print("[Flash completed! CRC OK]")
    return True

# ================= BOOTLOADER MODE =================
def bootloader_mode():
    print("\nBOOTLOADER MODE")
    print("Commands: F = flash, J = jump to app\n")

    while True:
        cmd = input(">> ").lower()

        if cmd == 'f':
            send_command(b'F')
            if wait_byte(ACK, timeout=3):
                if flash_firmware():
                    print("Flash done!")
                    listen_for_app(timeout=8)
                    application_mode()
                    return
            else:
                print("No response!")

        elif cmd == 'j':
            send_command(b'J')
            if wait_byte(ACK, timeout=3):
                print("Jumping to APP...")
                listen_for_app(timeout=3)
                application_mode()
                return
            else:
                print("No response!")
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
                print("Resetting to bootloader...")

                start = time.time()
                synced = False

                while time.time() - start < 5:
                    ser.write(b'F')
                    ser.flush()
                    time.sleep(0.05)

                    if ser.in_waiting:
                        b = ser.read(1)
                        print(f"[RX]: {b}")
                        if b == ACK:
                            print("Bootloader ACK received!")
                            synced = True
                            break

                if synced:
                    bootloader_mode()
                else:
                    print("Bootloader not responding!")
                    bootloader_mode()
                return

    except KeyboardInterrupt:
        print("\nExit")

# ================= MAIN =================
def main():
    print(f"Connected to {PORT}")
    print("Press RESET on board, then choose command")
    print("Commands: F = flash, J = jump\n")
    time.sleep(0.5)
    while True:
        cmd = input(">> ").lower()

        if cmd == 'f':
            print("Syncing with bootloader...")
            start = time.time()
            synced = False
            while time.time() - start < 10:
                ser.reset_input_buffer()
                ser.write(b'F')
                ser.flush()
                time.sleep(0.2)
                if ser.in_waiting:
                    b = ser.read(1)
                    if b == ACK:
                        print("Bootloader ready!")
                        synced = True
                        break
            if synced:
                if flash_firmware():
                    print("Flash done!")
                    listen_for_app(timeout=8)
                    application_mode()
                    return
            else:
                print("No response — press RESET and try again")

        elif cmd == 'j':
            print("Syncing with bootloader...")
            start = time.time()
            synced = False
            while time.time() - start < 10:
                ser.reset_input_buffer()
                ser.write(b'J')
                ser.flush()
                time.sleep(0.2)
                if ser.in_waiting:
                    b = ser.read(1)
                    if b == ACK:
                        print("Bootloader ready!")
                        synced = True
                        break
            if synced:
                print("Jumping to APP...")
                listen_for_app(timeout=3)
                application_mode()
                return
            else:
                print("No response — press RESET and try again")

if __name__ == "__main__":
    try:
        main()
    finally:
        ser.close()