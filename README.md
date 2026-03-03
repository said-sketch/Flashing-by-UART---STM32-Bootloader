# STM32F411RE — Custom UART Bootloader

Custom bare-metal UART bootloader for STM32F411RE with CRC32 firmware verification and a Python host script.

---

## How It Works

```
┌─────────────────────────────────────────────────────┐
│                  STM32F411RE Flash                  │
│                                                     │
│  0x08000000        0x08020000          0x08080000   │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  Bootloader  │  │ Application  │                 │
│  │   128 KB     │  │    64 KB     │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘

  PC (Python Script)
        │
        │  UART 115200
        │
  STM32 USART2 (PA2/PA3)
        │
        ▼
  Bootloader receives 'F' or 'J'
        │
   'F' ─┤─► Receive CRC → Erase → Flash chunks → Verify CRC → Jump to App
   'J' ─┘─► Jump directly to App
```

---

## Flash Protocol

```
Python                  Bootloader
──────────────────────────────────
  'F'          ──►
               ◄──   ACK
  CRC32 (4B)   ──►
               ◄──   ACK
                      [Erase]
               ◄──   ACK
  SIZE + DATA  ──►
               ◄──   ACK  (repeat per chunk)
  END 0xFFFF   ──►
               ◄──   ACK
                      [Verify CRC32]
               ◄──   ACK  → Jump to App
               ◄──   ERR  → Erase & wait
```

---

## Demo

![Flash completed CRC OK](test_boot_uart/Images/2.PNG)
> Firmware flashed successfully — 65 chunks transferred, CRC verified, application started and LED toggled.

---

## Project Structure

```
Flashing_by_UART/
├── bootloader_uart/       # Bootloader @ 0x08000000
│   └── Core/Src/
│       ├── main.c         # Command handler
│       └── flash_if.c     # Flash / CRC / Jump API
├── test_boot_uart/        # Application @ 0x08020000
│   └── Core/Src/
│       └── main.c         # LED toggle + reset to bootloader
└── flash_app_uart.py      # Python host script
```

---

## Usage

```bash
pip install pyserial
python flash_app_uart.py
```

| Mode        | Command | Action                  |
|-------------|---------|-------------------------|
| Bootloader  | `F`     | Flash new firmware      |
| Bootloader  | `J`     | Jump to app             |
| Application | `T`     | Toggle LED              |
| Application | `R`     | Reset to bootloader     |

---

## Future Improvements

- [ ] **UDS (ISO 14229)** — Diagnostic services over UART/CAN (0x34 RequestDownload, 0x36 TransferData, 0x37 TransferExit)
- [ ] **AUTOSAR BSW** — Abstract flash driver using AUTOSAR MemIf / Fls module interface
- [ ] **Secure Boot** — SHA-256 firmware integrity verification
- [ ] **AES-CMAC** — Firmware authenticity verification
- [ ] **XMODEM** — Standard transfer protocol support
- [ ] **CAN Bootloader** — Flash over CAN bus (automotive standard)

---

## Author

**Said** — Embedded Systems Engineer  
STM32F411RE · UART Bootloader · CRC32 · 2026
