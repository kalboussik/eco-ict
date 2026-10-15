# ctl.py - leviers de jeu : commandes texte recues du PC, etat local de la carte, echo "cfg" vers le tableau de bord.
# Pur Python, sans dependance materielle : meme code sur la carte (MicroPython) et dans le simulateur du PC.
#   L<tech>,<0|1>   radio de DONNEES coupee/allumee  (tech 0 = WiFi, 1 = LoRa). La telemetrie WiFi vers le PC n'est jamais coupee.
#   D<tech>,<0..2>  eloignement de l'antenne : couts du lien x1/x2/x3 et pertes 0/15/40 %
#   T<ms>           periode des mesures de surveillance
#   X<0|1>          noeud hors service (batterie vide) : plus rien ne part, plus rien n'est ecoute
#   W<rv>,<e>,<c>,<v>  poids energie / cout theorique / vitesse du cas d'utilisation rv (0 surveillance, 1 alarme), RODENT seulement
LOSS = (0, 15, 40)      # % de paquets perdus par niveau d'eloignement
KMUL = (1, 2, 3)        # multiplicateur des couts du lien par niveau d'eloignement

class Ctl:
    def __init__(self, emit, name, proto, per_ms, rnd):
        self.emit, self.name, self.p, self.rnd = emit, name, proto, rnd      # rnd() -> entier 0..99
        self.off = [False, False]
        self.dist = [0, 0]
        self.per = per_ms
        self.dead = False
        self.w = {0: (60, 30, 10), 1: (10, 10, 80)}

    def echo(self):
        self.emit(e="cfg", n=self.name, p=self.p, off=[int(x) for x in self.off], dist=list(self.dist), per=self.per,
                  dead=int(self.dead), w0=list(self.w[0]), w1=list(self.w[1]))

    def k(self, tech):
        return KMUL[self.dist[tech]]

    def lose(self, tech):
        return self.rnd() < LOSS[self.dist[tech]]

    def blocked(self, tech):
        return self.dead or self.off[tech]

    def handle(self, c, node=None):
        """-> True si c est une commande de jeu (valide ou non), False sinon."""
        if not c or c[0] not in "LDTXW":
            return False
        op = c[0]
        try:
            a = [int(x) for x in c[1:].split(",")]
        except ValueError:
            return True
        if op == "L" and len(a) == 2 and a[0] in (0, 1):
            self.off[a[0]] = not a[1]
        elif op == "D" and len(a) == 2 and a[0] in (0, 1) and 0 <= a[1] <= 2:
            self.dist[a[0]] = a[1]
        elif op == "T" and len(a) == 1 and 500 <= a[0] <= 30000:
            self.per = a[0]
        elif op == "X" and len(a) == 1:
            self.dead = bool(a[0])
        elif op == "W" and len(a) == 4 and a[0] in (0, 1) and min(a[1:]) >= 0 and sum(a[1:]) > 0:
            self.w[a[0]] = (a[1], a[2], a[3])
        else:
            return True
        if node is not None:
            node.configure(self.off, self.dist, self.dead, self.w)
        self.echo()
        return True
