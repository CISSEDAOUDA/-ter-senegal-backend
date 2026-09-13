# PyMySQL se fait passer pour mysqlclient (MySQLdb) - necessaire car
# mysqlclient a besoin de compiler du code C contre des bibliotheques
# systeme MySQL/MariaDB, absentes de l'environnement de build par
# defaut de Railway (Nixpacks). PyMySQL est 100% Python, aucune
# compilation requise, fonctionne partout de la meme facon.
#
# Django verifie la version rapportee par le module et exige au moins
# 2.2.1 (verification introduite pour mysqlclient). PyMySQL rapporte
# par defaut une version plus ancienne (1.4.6) qui echoue ce controle -
# on force donc la version annoncee, contournement standard et documente
# de ce probleme connu entre Django et PyMySQL.
import pymysql
pymysql.version_info = (2, 2, 4, "final", 0)
pymysql.install_as_MySQLdb()