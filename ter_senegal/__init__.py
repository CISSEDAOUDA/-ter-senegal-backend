# PyMySQL se fait passer pour mysqlclient (MySQLdb) - necessaire car
# mysqlclient a besoin de compiler du code C contre des bibliotheques
# systeme MySQL/MariaDB, absentes de l'environnement de build par
# defaut de Railway (Nixpacks). PyMySQL est 100% Python, aucune
# compilation requise, fonctionne partout de la meme facon.
import pymysql
pymysql.install_as_MySQLdb()