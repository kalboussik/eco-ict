# base_lora.py -> LA SEULE carte branchee au PC par USB (copier sous le nom main.py + rodent.py, ev_serial.py, topology.py).
# Recoit les paquets LoRa destines a la base, emet un beacon toutes les 2 s (liveness), obeit a "M1"/"M0" (panne simulee).
import time, socket, sys, pycom
from network import LoRa
import rodent as R, ev_serial as ev
from topology import BASE_LORA
pycom.heartbeat(False)
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, sf=7, bandwidth=LoRa.BW_125KHZ, tx_power=14)
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW); s.setblocking(False)
try:
    import uselect
    _p = uselect.poll(); _p.register(sys.stdin, uselect.POLLIN)
except Exception:
    _p = None
muted = False
t_beacon = t_hello = time.ticks_ms()
beacon = R.pack(BASE_LORA, R.BCAST, 0, (0, 0, 0, 0), b"")
while True:
    try:
        if _p and _p.poll(0):
            c = sys.stdin.readline().strip()
            if c in ("M0", "M1"):
                muted = (c == "M1")
    except Exception:
        pass
    try:
        raw = s.recv(256)
    except OSError:
        raw = b""
    if raw and not muted:
        p = R.unpack(bytes(raw))
        if p and p[1] == BASE_LORA and p[4]:
            pl = R.unpack_payload(p[4])
            if pl:
                ev.emit(e="rx", b="lora", p="rodent", o=pl[0], seq=pl[1], k=R.RV_NAME[pl[2]], src=p[0])
    if not muted and time.ticks_diff(time.ticks_ms(), t_beacon) >= 2000:
        s.send(beacon); t_beacon = time.ticks_ms()
    if time.ticks_diff(time.ticks_ms(), t_hello) >= 5000:
        ev.emit(e="hello", n="SL", muted=muted); t_hello = time.ticks_ms()
    time.sleep_ms(2)
