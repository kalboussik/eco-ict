# topology.py - topologie LOGIQUE du banc d'essai (fig. 5.4 de la these, BLE remplace par LoRa).
# Les cartes sont physiquement dans la meme piece : chaque noeud ignore par logiciel tout paquet d'un non-voisin.
WIFI, LORA = 0, 1
TECH_NAME = ("wifi", "lora")
BASE_WIFI, BASE_LORA = 0xB001, 0xB002
# TOPOLOGY[noeud][(voisin, techno)] = (cout energetique, cout theorique du message, debit)  -- 1 octet chacun
TOPOLOGY = {
    1: {(BASE_WIFI, WIFI): (60, 5, 200), (3, LORA): (15, 1, 20)},
    2: {(BASE_WIFI, WIFI): (60, 5, 200), (BASE_LORA, LORA): (15, 1, 20)},
    3: {(BASE_WIFI, WIFI): (140, 5, 120), (1, LORA): (15, 1, 20)},   # WiFi faible : beaucoup de retransmissions
    4: {(BASE_WIFI, WIFI): (60, 5, 200), (BASE_LORA, LORA): (15, 1, 20), (5, LORA): (15, 1, 20)},
    5: {(4, LORA): (15, 1, 20), (6, LORA): (15, 1, 20)},             # hors de portee WiFi ; relaie N6
    6: {(5, LORA): (15, 1, 20)},                                     # 3 sauts de la base : N6 -> N5 -> N4 -> base
}
