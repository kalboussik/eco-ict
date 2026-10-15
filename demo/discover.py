# discover.py - trouve l'adresse du PC sur le reseau (le PC diffuse "RODENT_PC" sur UDP 5008 toutes les 2 s)
import socket, time, pycom
import config

def find():
    if config.PC_IP:
        return config.PC_IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", config.DISCOVERY_PORT))
    s.settimeout(1)
    on, n = False, 0
    while True:                                   # attend le PC (LED orange clignotante)
        on = not on
        n += 1
        if n % 5 == 1:
            print("en attente de l'annonce du PC (server.py doit tourner, PC sur le meme WiFi)... ou fixez PC_IP dans config.py")
        pycom.rgbled(0x302000 if on else 0)
        try:
            d, a = s.recvfrom(32)
        except OSError:
            continue
        if d.startswith(b"RODENT_PC"):
            s.close(); pycom.rgbled(0)
            return a[0]
