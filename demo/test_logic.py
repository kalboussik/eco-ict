# Test logiciel sur PC du vrai rodent.py + topology.py : 5 noeuds, beacons, relais, panne de la base WiFi.
import rodent as R
from topology import *
clock = [1000]
R.time.time = lambda: clock[0]
nodes = {n: R.RodentNode(n, TOPOLOGY[n]) for n in TOPOLOGY}
def deliver(src, tech, pkt):                      # medium : tout noeud ayant (src,tech) dans sa LM entend
    for n, nd in nodes.items():
        if (src, tech) in nd.LM:
            nd.hear(tech, pkt)
def base_beacons(wifi=True, lora=True):
    if wifi: deliver(BASE_WIFI, WIFI, R.pack(BASE_WIFI, R.BCAST, 0, (0,0,0,0)))
    if lora: deliver(BASE_LORA, LORA, R.pack(BASE_LORA, R.BCAST, 0, (0,0,0,0)))
def round_(wifi=True, lora=True):
    base_beacons(wifi, lora)
    for _ in range(3):                            # quelques tours pour la convergence multi-sauts
        for n, nd in nodes.items():
            techs = sorted(set(t for (nb, t) in nd.LM if nb < R.BASE_MIN_ID))
            for tech, pkt in nd.beacons(techs):
                deliver(n, tech, pkt)
def show(tag):
    print(tag)
    for n, nd in nodes.items():
        nd.select()
        f = lambda rv: ("%s/%s" % (hex(nd.best[rv].via), TECH_NAME[nd.best[rv].tech])) if rv in nd.best else "none"
        print("  N%d surv=%-14s alarm=%s" % (n, f(R.RV_SURV), f(R.RV_ALARM)))
round_(); show("convergence")
b = lambda n, rv: nodes[n].best.get(rv)
assert (b(2, R.RV_SURV).via, b(2, R.RV_ALARM).via) == (BASE_LORA, BASE_WIFI)
assert (b(3, R.RV_SURV).via, b(3, R.RV_ALARM).via) == (1, BASE_WIFI)
assert b(5, R.RV_SURV).via == 4 and b(5, R.RV_ALARM).via == 4
assert b(6, R.RV_SURV).via == 5 and b(6, R.RV_ALARM).via == 5 and b(6, R.RV_ALARM).metrics[3] == 3   # 3 sauts
# relais : N5 envoie une alarme, N4 la relaie via sa meilleure route d'alarme (WiFi)
pk = nodes[5].build(R.RV_ALARM, R.pack_payload(5, 1, 1, 1850))[1]
nodes[4].hear(LORA, pk); rv, data = nodes[4].queue.pop(0)
assert nodes[4].build(rv, data)[0] == WIFI
# panne de la base WiFi : plus de beacon -> liveness expire -> tout bascule sur LoRa (N1 et N3 perdent leur route)
for _ in range(7):
    clock[0] += 3; round_(wifi=False)   # 21 s > ROUTE_TTL : les routes perimees (N1<->N3) disparaissent
show("apres panne base WiFi")
assert b(2, R.RV_ALARM).via == BASE_LORA and b(4, R.RV_ALARM).via == BASE_LORA
assert b(1, R.RV_SURV) is None and b(1, R.RV_ALARM) is None
print("OK")
