# main_classic.py -> a copier sur la carte sous le nom main.py (avec rodent.py, topology.py, config.py, ev.py)
# Protocole CLASSIQUE : une seule technologie (WiFi), chemin direct vers la base WiFi, aucun plan B, aucune notion de type de message.
# Un noeud sans lien WiFi vers la base dans topology.py (N5) n'a pas de route. Le WiFi sert quand meme a la telemetrie vers le PC.
import time, socket, struct, machine, pycom
from network import WLAN
from machine import Pin
import rodent as R, ev, config, discover
from topology import *

P, NODE = "classic", config.NODE
NAME = "N%d" % NODE
HAS_WIFI = (BASE_WIFI, WIFI) in TOPOLOGY[NODE]
pycom.heartbeat(False)

def classic_pack(src, dst, data):     # net(2) src(2) dst(2) len(1) data crc(1) : pas de champs de route ni de besoins
    body = struct.pack("!HHHB", R.NET_ID, src, dst, len(data)) + data
    return body + bytes((R.crc8(body),))

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
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

btn = Pin(config.BUTTON, mode=Pin.IN, pull=Pin.PULL_UP)
alarm, last_btn, seq = False, 1, 0
def set_alarm(v):
    global alarm
    alarm = v
    ev.emit(e="alarm", n=NAME, p=P, on=alarm)

def gen(rv):
    global seq
    seq += 1
    k = R.RV_NAME[rv]
    ev.emit(e="gen", n=NAME, p=P, seq=seq, k=k)
    if not HAS_WIFI:
        ev.emit(e="drop", n=NAME, p=P, seq=seq, o=NAME, k=k, why="no WiFi path to a base"); return
    data = R.pack_payload(NODE, seq, rv, 1800 + machine.rng() % 200)
    if wlan.isconnected():
        sock.sendto(classic_pack(NODE, BASE_WIFI, data), PC)
    ev.emit(e="tx", n=NAME, p=P, seq=seq, k=k, o=NAME, tech="wifi", to=BASE_WIFI, en=TOPOLOGY[NODE][(BASE_WIFI, WIFI)][0], relay=False)

ev.sync_wait()
ev.emit(e="hello", n=NAME, p=P)
now = time.ticks_ms()
t_surv, t_alarm, t_hello, t_sync = now + 500 + NODE * 300, now + 700 + NODE * 150, now + 5000, now + config.SYNC_PERIOD_MS
due = lambda t: time.ticks_diff(time.ticks_ms(), t) >= 0
while True:
    for c in ev.poll():
        if c == "A":
            set_alarm(not alarm)
    v = btn.value()
    if v == 0 and last_btn == 1:
        set_alarm(not alarm)
    last_btn = v
    if due(t_surv):
        gen(R.RV_SURV); t_surv = time.ticks_add(time.ticks_ms(), config.SURV_PERIOD_MS)
    if alarm and due(t_alarm):          # le mode alarme change la cadence, JAMAIS le chemin ni la techno
        gen(R.RV_ALARM); t_alarm = time.ticks_add(time.ticks_ms(), config.ALARM_PERIOD_MS)
    if due(t_hello):
        ev.emit(e="hello", n=NAME, p=P); t_hello = time.ticks_add(time.ticks_ms(), 5000)
    if due(t_sync):
        ev.sync_request(); t_sync = time.ticks_add(time.ticks_ms(), config.SYNC_PERIOD_MS)
    ev.flush()
    time.sleep_ms(5)
