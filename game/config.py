# config.py - A ADAPTER SUR CHAQUE CARTE (NODE = 1 a 5)
NODE = 2
WIFI_SSID = "MON_TELEPHONE"   # nom du partage de connexion du telephone (en 2.4 GHz : le FiPy ne gere pas le 5 GHz)
WIFI_PWD = "motdepasse"
PC_IP = None                 # None = le PC est trouve automatiquement (il s'annonce sur UDP 5008). Ou fixez-le : "192.168.43.50"
DISCOVERY_PORT = 5008
UDP_PORT = 5005              # donnees RODENT / classique + beacons de la base WiFi
TELEMETRY_PORT = 5006        # evenements vers le collecteur (PC)
CMD_PORT = 5007              # commandes du tableau de bord vers la carte (ex. "A" = bascule alarme) + reponses de synchro
BUTTON = "P14"               # bouton du shield Pytrack/Pysense (facultatif)
SURV_PERIOD_MS = 3000
ALARM_PERIOD_MS = 1200
BEACON_PERIOD_MS = 8000      # beacons de controle RODENT (LoRa : duty-cycle 1 % non applique, banc d'essai uniquement)
SYNC_PERIOD_MS = 10000       # resynchronisation d'horloge avec le PC
