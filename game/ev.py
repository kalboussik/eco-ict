# ev.py - telemetrie des cartes vers le PC par WiFi (UDP), avec horodatage LOCAL synchronise sur l'horloge du PC.
# Les evenements sont mis en tampon puis envoyes par lots APRES l'emission radio : la telemetrie ne retarde pas les donnees.
import ujson, time, socket
import config

_q, _sock, _off, _c0, _best, _got = [], None, None, 0, None, False
_addr = None
_name = "N%d" % config.NODE
_last = 0

def init():
    global _sock, _addr
    _addr = (config.PC_IP, config.TELEMETRY_PORT)
    _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _sock.bind(("0.0.0.0", config.CMD_PORT))
    _sock.setblocking(False)

def emit(**kw):
    kw["t"] = time.ticks_ms()            # instant de l'evenement sur l'horloge de la carte
    _q.append(ujson.dumps(kw))
    if len(_q) > 40:
        del _q[0]

def flush(force=False):
    global _last
    if _q and _sock and (force or time.ticks_diff(time.ticks_ms(), _last) >= 30):
        try:
            _sock.sendto("\n".join(_q).encode(), _addr)
        except OSError:
            pass
        del _q[:]
        _last = time.ticks_ms()

def sync_request():
    global _c0, _got
    _got = False
    _c0 = time.ticks_ms()
    try:
        _sock.sendto(ujson.dumps({"e": "syncq", "c": _c0, "n": _name}).encode(), _addr)
    except OSError:
        pass

def poll():
    """Lit le socket de commandes : traite les reponses de synchro, retourne les commandes texte ('A', ...)."""
    global _off, _best, _got
    cmds = []
    try:
        while True:
            d = _sock.recv(128)
            if not d:
                break
            if d[:1] == b"{":
                r = ujson.loads(d)
                if r.get("e") == "syncr" and r.get("c") == _c0:
                    c1 = time.ticks_ms()
                    _got = True
                    rtt = time.ticks_diff(c1, _c0)
                    if _best is None or rtt <= _best + 3:     # on garde les echantillons proches du meilleur RTT
                        _best = rtt if _best is None else min(_best, rtt)
                        _off = r["s"] - (_c0 + c1) // 2       # horloge PC (ms) - horloge carte (ms)
                        emit(e="offset", n=_name, o=_off, rtt=rtt)
            else:
                s = d.decode().strip()
                if s in ("P0", "P1"):                # changement de protocole a distance : memorise puis redemarre la carte
                    import pycom, machine
                    pycom.nvs_set("proto", int(s[1])); time.sleep_ms(100); machine.reset()
                cmds.append(s)
    except OSError:
        pass
    return cmds

def sync_wait(timeout_ms=5000):
    """Au demarrage : 10 echanges rapides ; la reponse est lue immediatement (RTT fiable) et on garde le decalage au plus petit RTT."""
    for _ in range(10):
        sync_request()
        t0 = time.ticks_ms()
        while not _got and time.ticks_diff(time.ticks_ms(), t0) < 300:
            poll(); time.sleep_ms(1)
        time.sleep_ms(30)
    flush(True)
    return _off is not None
