# main_rodent.py -> a copier sur la carte sous le nom main.py
# Fichiers : rodent.py topology.py config.py ev.py + ce fichier. La carte n'a PAS besoin d'etre branchee au PC (alimentation seule).
import time, socket, machine, pycom
from network import WLAN, LoRa
from machine import Pin
import rodent as R, ev, config, discover, ctl
from topology import *

P, NODE = "rodent", config.NODE
NAME = "N%d" % NODE
LM = TOPOLOGY[NODE]
pycom.heartbeat(False)

# WiFi : sert a la telemetrie vers le PC pour TOUS les noeuds ; les donnees RODENT ne l'utilisent que si topology.py le prevoit
wlan = WLAN(mode=WLAN.STA)
wlan.connect(config.WIFI_SSID, auth=(WLAN.WPA2, config.WIFI_PWD), timeout=10000)
t0 = time.ticks_ms()
while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 15000:
    time.sleep_ms(200)
print("WiFi:", wlan.isconnected(), wlan.ifconfig() if wlan.isconnected() else "non connecte a " + config.WIFI_SSID)
config.PC_IP = discover.find()
print("PC:", config.PC_IP)      # adresse du PC apprise par diffusion
PC = (config.PC_IP, config.UDP_PORT)
ev.init()
usock = None
if any(t == WIFI for (_, t) in LM):
    usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    usock.bind(("0.0.0.0", config.UDP_PORT)); usock.setblocking(False)
lsock = None
if any(t == LORA for (_, t) in LM):
    lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, sf=7, bandwidth=LoRa.BW_125KHZ, tx_power=14)
    lsock = socket.socket(socket.AF_LORA, socket.SOCK_RAW); lsock.setblocking(False)

def send(tech, pkt):
    if C.blocked(tech) or C.lose(tech):       # radio coupee, noeud hors service, ou paquet perdu (antenne eloignee)
        return
    if tech == WIFI:
        if usock and wlan.isconnected():
            usock.sendto(pkt, PC)
    elif lsock:
        lsock.send(pkt)

def poll():
    out = []
    for tech, s in ((WIFI, usock), (LORA, lsock)):
        if s is None:
            continue
        try:
            raw = s.recv(256)
            raw = raw[0] if isinstance(raw, tuple) else raw
            if raw and not C.blocked(tech):      # on vide toujours le tampon, mais une radio coupee n'entend rien
                out.append((tech, bytes(raw)))
        except OSError:
            pass
    return out

def on_route(rv, b):
    ev.emit(e="route", n=NAME, p=P, k=R.RV_NAME[rv], via=(b.via if b else None), tech=(TECH_NAME[b.tech] if b else None))

node = R.RodentNode(NODE, LM, on_route)
C = ctl.Ctl(ev.emit, NAME, P, config.SURV_PERIOD_MS, lambda: machine.rng() % 100)
beacon_techs = sorted(set(t for (nb, t) in LM if nb < R.BASE_MIN_ID))
btn = Pin(config.BUTTON, mode=Pin.IN, pull=Pin.PULL_UP)
alarm, last_btn, seq = False, 1, 0

def set_alarm(v):
    global alarm
    alarm = v
    ev.emit(e="alarm", n=NAME, p=P, on=alarm)

def gen(rv):
    global seq
    if C.dead:
        return
    seq += 1
    ev.emit(e="gen", n=NAME, p=P, seq=seq, k=R.RV_NAME[rv])
    node.enqueue(rv, R.pack_payload(NODE, seq, rv, 1800 + machine.rng() % 200))

ev.sync_wait()
ev.emit(e="hello", n=NAME, p=P)
now = time.ticks_ms()
t_surv, t_alarm, t_beacon = now + 500 + NODE * 300, now + 700 + NODE * 150, now + 1000 + NODE * 400
t_hello, t_sync = now + 5000, now + config.SYNC_PERIOD_MS
due = lambda t: time.ticks_diff(time.ticks_ms(), t) >= 0

while True:
    # 1) commandes du tableau de bord (WiFi) + reponses de synchro d'horloge, bouton local
    for c in ev.poll():
        if c == "A":
            set_alarm(not alarm)
        elif C.handle(c, node):
            pycom.rgbled(0xFF0000 if C.dead else 0)
    v = btn.value()
    if v == 0 and last_btn == 1:
        set_alarm(not alarm)
    last_btn = v
    # 2) ecoute : liveness des bases, routes voisines, paquets a relayer
    for tech, raw in poll():
        if not C.dead:
            node.hear(tech, raw)
    # 3) generation de mesures
    if due(t_surv):
        gen(R.RV_SURV); t_surv = time.ticks_add(time.ticks_ms(), C.per)
    if alarm and due(t_alarm):
        gen(R.RV_ALARM); t_alarm = time.ticks_add(time.ticks_ms(), config.ALARM_PERIOD_MS)
    # 4) beacons de controle
    if beacon_techs and due(t_beacon):
        pk = node.beacons(beacon_techs)
        for tech, p in pk:
            send(tech, p)
        if pk:
            ev.emit(e="beacon", n=NAME, p=P, cnt=len(pk), en=9 * len(pk))
        t_beacon = time.ticks_add(time.ticks_ms(), config.BEACON_PERIOD_MS)
    # 5) file d'emission : la radio part AVANT la telemetrie
    while node.queue:
        rv, data = node.queue.pop(0)
        o, s, _, _ = R.unpack_payload(data)
        out = node.build(rv, data)
        if out is None:
            ev.emit(e="drop", n=NAME, p=P, seq=s, o="N%d" % o, k=R.RV_NAME[rv], why="no route"); continue
        tech, pkt = out
        b = node.best[rv]
        send(tech, pkt)
        ev.emit(e="tx", n=NAME, p=P, seq=s, k=R.RV_NAME[rv], o="N%d" % o, tech=TECH_NAME[tech], to=b.via,
                en=node.LM[(b.via, tech)][0], relay=(o != NODE))
    if due(t_hello):
        # diagnostic (visible dans le REPL Pymakr si la carte est sur USB) : age du dernier beacon de chaque base, et routes choisies
        print(NAME, "beacons (s):", {("wifi" if k[1] == WIFI else "lora"): int(node.now() - v) for k, v in node.seen.items()},
              "surv:", node.best.get(R.RV_SURV) and TECH_NAME[node.best[R.RV_SURV].tech], "alarm:", node.best.get(R.RV_ALARM) and TECH_NAME[node.best[R.RV_ALARM].tech])
        ev.emit(e="hello", n=NAME, p=P); C.echo(); t_hello = time.ticks_add(time.ticks_ms(), 5000)
        for rv in (R.RV_SURV, R.RV_ALARM):      # rappel des routes courantes : un tableau de bord lance apres les cartes les retrouve
            b = node.best.get(rv)
            ev.emit(e="route", n=NAME, p=P, k=R.RV_NAME[rv], via=(b.via if b else None), tech=(TECH_NAME[b.tech] if b else None), r=1)
    if due(t_sync):
        ev.sync_request(); t_sync = time.ticks_add(time.ticks_ms(), config.SYNC_PERIOD_MS)
    ev.flush()
    time.sleep_ms(5)
