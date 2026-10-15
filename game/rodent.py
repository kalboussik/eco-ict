# rodent.py v2 - coeur du protocole RODENT (MicroPython Pycom ET CPython, aucune dependance materielle)
# Ref : B. Foubert, these Univ. Lille 2021, ch. 3-4.
import struct
import math
try:
    import utime as time
except ImportError:
    import time

NET_ID = 0x0A0A
BASE_MIN_ID = 0xB000          # ids >= : stations de base (puits)
BCAST = 0xFFFF
ROUTE_TTL_S = 14              # une route voisine non reentendue expire
LINK_TIMEOUT_S = 7            # un lien vers une station de base sans beacon depuis ce delai est considere mort
MAX_HOPS = 6
QUEUE_MAX = 10

# attributs : energie, cout theorique du message, debit, sauts. Bornes FIXES (normalisation bornee, these 4.4)
BOUNDS = ((10, False), (1, False), (255, True), (1, False))
RV_SURV, RV_ALARM = 0, 1
RV_NAME = ("surv", "alarm")
REQUIREMENTS = {RV_SURV: (0.6, 0.3, 0.1, 0.0), RV_ALARM: (0.1, 0.1, 0.8, 0.0)}

def crc8(data, poly=0x07):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

# net(2) src(2) dst(2) len(1) rv(1) | route 4 x 1 octet | data | crc8
HDR = "!HHHBB4B"
HDR_LEN = struct.calcsize(HDR)   # 12

def pack(src, dst, rv, route, data=b""):
    body = struct.pack(HDR, NET_ID, src, dst, len(data), rv, *route) + data
    return body + bytes((crc8(body),))

def unpack(raw):
    if len(raw) < HDR_LEN + 1 or crc8(raw[:-1]) != raw[-1]:
        return None
    f = struct.unpack(HDR, raw[:HDR_LEN])
    if f[0] != NET_ID or len(raw) != HDR_LEN + f[3] + 1:
        return None
    return f[1], f[2], f[4], tuple(f[5:9]), raw[HDR_LEN:HDR_LEN + f[3]]

# charge utile applicative commune aux deux protocoles : origine, numero de sequence, type, temperature (centi-degres)
PL = "!HHBh"
PL_LEN = struct.calcsize(PL)     # 7
def pack_payload(origin, seq, kind, temp):
    return struct.pack(PL, origin, seq, kind, temp)
def unpack_payload(data):
    return struct.unpack(PL, data[:PL_LEN]) if len(data) >= PL_LEN else None

def score(metrics, weights):
    """TOPSIS a normalisation bornee : coefficient de proximite dans [0,1] (grand = meilleure route)."""
    sp = sm = 0.0
    for x, w, (b, asc) in zip(metrics, weights, BOUNDS):
        x = x if x > 0 else 1
        r = x / b if asc else b / x
        if r > 1:
            r = 1.0
        v = w * r
        sp += (w - v) ** 2
        sm += v * v
    sp, sm = math.sqrt(sp), math.sqrt(sm)
    return sm / (sp + sm) if sp + sm else 0.0

class Route:
    __slots__ = ("via", "tech", "metrics", "expires")
    def __init__(self, via, tech, metrics, expires):
        self.via, self.tech, self.metrics, self.expires = via, tech, metrics, expires

def _add(rm, link):
    return (min(255, rm[0] + link[0]), min(255, rm[1] + link[1]), min(rm[2], link[2]), min(255, rm[3] + 1))

class RodentNode:
    def __init__(self, node_id, links, on_route=None):
        """links = {(voisin, techno): (energie, cout theorique, debit)}  (matrice de lien LM, statique comme dans la these)"""
        self.id, self.LM0, self.on_route = node_id, links, on_route
        self.LM = links         # matrice de lien courante (LM0 mise a l'echelle par l'eloignement choisi)
        self.off = set()        # technologies de donnees coupees (jeu)
        self.req = dict(REQUIREMENTS)
        self.RM = {}        # (rv, via, tech) -> Route : routes apprises des voisins, par cas d'utilisation
        self.direct = {}    # (base, tech) -> Route    : routes unisaut vers une station de base
        self.seen = {}      # (base, tech) -> dernier beacon entendu (detection de panne de lien)
        self.best, self._key, self.queue = {}, {}, []
        t = self.now()
        for (nid, tech), (e, m, d) in links.items():
            if nid >= BASE_MIN_ID:
                self.direct[(nid, tech)] = Route(nid, tech, (e, m, d, 1), None)
                self.seen[(nid, tech)] = t      # periode de grace au demarrage
        self.select()

    def now(self):
        return time.time()

    def configure(self, off, dist, dead, w):
        """Leviers de jeu : radios coupees, eloignement des antennes (couts des liens x1/x2/x3), poids des besoins."""
        self.off = set(t for t in (0, 1) if off[t] or dead)
        self.LM = {}
        for (nid, tech), (e, m, d) in self.LM0.items():
            k = (1, 2, 3)[dist[tech]]
            self.LM[(nid, tech)] = (min(255, e * k), min(255, m * k), max(1, d // k))
        for (nid, tech) in list(self.direct):
            e, m, d = self.LM[(nid, tech)]
            self.direct[(nid, tech)] = Route(nid, tech, (e, m, d, 1), None)
        for rv in (RV_SURV, RV_ALARM):
            tot = float(sum(w[rv]))
            self.req[rv] = (w[rv][0] / tot, w[rv][1] / tot, w[rv][2] / tot, 0.0)
        self.select()

    def select(self):
        t = self.now()
        for k in [k for k, r in self.RM.items() if r.expires < t]:
            del self.RM[k]
        for rv, w in self.req.items():
            cands = [r for k, r in self.direct.items() if t - self.seen.get(k, 0) <= LINK_TIMEOUT_S and r.tech not in self.off]
            cands += [r for k, r in self.RM.items() if k[0] == rv and r.tech not in self.off]
            best, bs = None, -1.0
            for r in cands:
                if r.metrics[3] > MAX_HOPS:
                    continue
                s = score(r.metrics, w)
                if s > bs:
                    best, bs = r, s
            key = (best.via, best.tech) if best else None
            if self._key.get(rv, "init") != key:
                self._key[rv] = key
                if self.on_route:
                    self.on_route(rv, best)
            if best is None:
                self.best.pop(rv, None)
            else:
                self.best[rv] = best
        return self.best

    def hear(self, tech, raw):
        """Tout paquet entendu (meme non destine a ce noeud) : beacons de base = liveness,
        routes voisines = piggybacking. Retourne (rv, data) si le paquet est a relayer."""
        if tech in self.off:
            return None
        p = unpack(raw)
        if p is None:
            return None
        src, dst, rv, route, data = p
        link = self.LM.get((src, tech))
        if src == self.id or link is None:      # topologie logique : un non-voisin est ignore
            return None
        if src >= BASE_MIN_ID:
            self.seen[(src, tech)] = self.now()
            return None
        if dst != self.id and route[3] < MAX_HOPS:      # split horizon
            self.RM[(rv, src, tech)] = Route(src, tech, _add(route, link), self.now() + ROUTE_TTL_S)
        if dst == self.id and data and len(self.queue) < QUEUE_MAX:
            self.queue.append((rv, data))
            return rv, data
        return None

    def enqueue(self, rv, data):
        if len(self.queue) < QUEUE_MAX:
            self.queue.append((rv, data))

    def build(self, rv, data):
        """-> (tech, bytes) ou None si aucune route."""
        self.select()
        r = self.best.get(rv)
        return None if r is None else (r.tech, pack(self.id, r.via, rv, r.metrics, data))

    def beacons(self, techs):
        """Paquets de controle (donnees vides), un par cas d'utilisation et par techno partagee avec un voisin non-base."""
        self.select()
        return [(t, pack(self.id, r.via, rv, r.metrics, b"")) for rv, r in self.best.items() for t in techs if t not in self.off]
