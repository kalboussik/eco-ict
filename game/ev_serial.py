# ev_serial.py - evenements sur le port USB (pour la carte base LoRa, seule carte branchee au PC)
import ujson
def emit(**kw):
    print("@EV " + ujson.dumps(kw))
