import argparse
import struct
import time
import serial

PKT_MAGIC0 = 0xAA
PKT_MAGIC1 = 0x55
PKT_LEN = 8

FLAG_ENABLE     = 1 << 0
FLAG_ESTOP      = 1 << 1
FLAG_DOCK_START = 1 << 2
FLAG_DOCK_ABORT = 1 << 3

def crc16_ibm(data: bytes) -> int:
    """CRC16/IBM(MODBUS): init=0xFFFF poly=0xA001"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def clamp_i8(x: int) -> int:
    return -128 if x < -128 else 127 if x > 127 else x

def build_packet(seq: int, flags: int, speed: int, steer: int) -> bytes:
    speed = clamp_i8(speed)
    steer = clamp_i8(steer)
    header = struct.pack(
        "<BBBBbb",
        PKT_MAGIC0, PKT_MAGIC1,
        seq & 0xFF,
        flags & 0xFF,
        speed, steer
    )
    crc = crc16_ibm(header)
    pkt = header + struct.pack("<H", crc)  # little endian
    assert len(pkt) == PKT_LEN
    return pkt

def send_loop(ser, hz, flags_fn, speed, steer, print_rx=False, label=""):
    period = 1.0 / hz if hz > 0 else 0.05
    seq = 0
    if label:
        print(label)

    try:
        while True:
            flags = flags_fn()
            ser.write(build_packet(seq, flags, speed, steer))

            if print_rx:
                rx = ser.read(4096)
                if rx:
                    # 깨져도 무시하고 문자열로 출력
                    print(rx.decode(errors="ignore"), end="")

            seq = (seq + 1) & 0xFF
            time.sleep(period)
    except KeyboardInterrupt:
        print("\n[STOP]")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--hz", type=float, default=20.0)

    ap.add_argument("--speed", type=int, default=0)
    ap.add_argument("--steer", type=int, default=0)

    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--estop", action="store_true")
    ap.add_argument("--dock_start", action="store_true")
    ap.add_argument("--dock_abort", action="store_true")

    ap.add_argument("--dock_start_once", action="store_true")
    ap.add_argument("--dock_abort_once", action="store_true")
    ap.add_argument("--once_ms", type=int, default=200, help="once 트리거 유지 시간(ms), 기본 200ms")

    ap.add_argument("--cycle", action="store_true", help="start/abort를 번갈아 반복")
    ap.add_argument("--cycle_sec", type=float, default=10.0, help="각 상태 유지 시간(초), 기본 5초")

    ap.add_argument("--print_rx", action="store_true", help="STM printf 읽어서 출력")
    args = ap.parse_args()

    base_flags = 0
    if args.enable: base_flags |= FLAG_ENABLE
    if args.estop:  base_flags |= FLAG_ESTOP
    if args.dock_start: base_flags |= FLAG_DOCK_START
    if args.dock_abort: base_flags |= FLAG_DOCK_ABORT

    # once 모드면 base_flags에 해당 트리거를 잠깐만 얹고 내려줌
    if args.dock_start_once:
        base_flags |= FLAG_ENABLE
    if args.dock_abort_once:
        base_flags |= FLAG_ENABLE

    with serial.Serial(args.port, args.baud, timeout=0.05) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"[OPEN] port={args.port} baud={args.baud} hz={args.hz} speed={args.speed} steer={args.steer}")
        if args.print_rx:
            print("[RX] printing STM output...\n")

        # ---- cycle 모드 ----
        if args.cycle:
            start_t = time.time()
            def flags_fn():
                t = time.time() - start_t
                phase = int(t // args.cycle_sec) % 2
                if phase == 0:
                    return (FLAG_ENABLE | FLAG_DOCK_START)  # start
                else:
                    return (FLAG_ENABLE | FLAG_DOCK_ABORT)  # abort/release
            send_loop(ser, args.hz, flags_fn, args.speed, args.steer, args.print_rx,
                      label=f"[MODE] CYCLE: start/abort every {args.cycle_sec}s (Ctrl+C to stop)")
            return

        # ---- once 모드 ----
        if args.dock_start_once or args.dock_abort_once:
            t0 = time.time()
            hold_s = max(0.01, args.once_ms / 1000.0)
            def flags_fn():
                # 처음 hold_s 동안만 트리거 on, 이후에는 enable만 유지
                if (time.time() - t0) < hold_s:
                    if args.dock_start_once:
                        return FLAG_ENABLE | FLAG_DOCK_START
                    else:
                        return FLAG_ENABLE | FLAG_DOCK_ABORT
                return FLAG_ENABLE
            which = "DOCK_START_ONCE" if args.dock_start_once else "DOCK_ABORT_ONCE"
            send_loop(ser, args.hz, flags_fn, args.speed, args.steer, args.print_rx,
                      label=f"[MODE] {which}: trigger {args.once_ms}ms then keep ENABLE heartbeat")
            return

        # ---- 일반 모드(주행/정지/도킹 상시 플래그) ----
        def flags_fn():
            return base_flags

        send_loop(ser, args.hz, flags_fn, args.speed, args.steer, args.print_rx,
                  label=f"[MODE] FIXED flags=0x{base_flags:02X} (Ctrl+C to stop)")

if __name__ == "__main__":
    main()

"""
모터 구동 확인
python uart_send.py --port COM3 --baud 115200 --hz 20 --enable --speed 20 --steer -10 --print_rx

도킹 시작 확인
python stmtest.py --port COM3 --baud 115200 --hz 20 --dock_start_once --speed 0 --steer 0 --print_rx

도킹 해제 확인
python stmtest.py --port COM3 --baud 115200 --hz 20 --dock_abort_--speed 0 --steer 0 --print_rx

도킹 -> 해제 반복
python stmtest.py --port COM3 --baud 115200 --hz 50 --cycle --cycle_sec 5 --speed 0 --steer 0 --print_rx
"""