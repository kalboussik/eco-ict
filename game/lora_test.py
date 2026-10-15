# lora_test.py - test radio LoRa isole (sans RODENT). A lancer depuis Pymakr (Ctrl+C d'abord pour arreter main.py).
# Carte 1 : ROLE = "tx"   Carte 2 : ROLE = "rx"   (mettre les antennes LoRa !)
ROLE = "rx"
import time, socket, pycom
from network import LoRa
pycom.heartbeat(False)
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, sf=7, bandwidth=LoRa.BW_125KHZ, tx_power=14)
print("LoRa mac:", lora.mac(), "frequence:", lora.frequency())
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
s.setblocking(False)
n = 0
while True:
    if ROLE == "tx":
        n += 1
        s.send(b"ping%d" % n)
        print("envoye", n)
        time.sleep(1)
    else:
        try:
            d = s.recv(64)
        except OSError:
            d = b""
        if d:
            print("RECU", d, "rssi:", lora.stats().rssi)
        time.sleep_ms(20)
