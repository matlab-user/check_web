import os

basedir = os.path.abspath( os.path.dirname(__file__) )

SECRET_KEY = os.getenv( 'SECRET_KEY', 'ry728599uhmsmmm!kkg }Pooiuyffhjk*j|' )
ITEMS_PER_PAGE = 10
DEBUG = True
REDIS_URL = 'redis://:password@localhost:6379/0'

UPLOAD_FOLDER = './uploads'
TEMP_FOLDER = './temp'

# 禁止普通权限更改订单的时间, 小时
# 以订单当天0点为基准点, 其之前 ban_t 时间内,无专门权限人就不能随意更改订单了。
BAN_T = 3


DB_IP = '127.0.0.1'
DB_USER = 'blue'
DB_PASSWD = 'blue'
DB_NAME = 'orders_db'
DB_PORT = 3306
DB_CHARSET = 'utf8'

'''
DB_IP = '101.200.233.199'
DB_USER = 'guocool'
DB_PASSWD = 'aZuL2H58CcrzhTdt'
DB_PORT = 3306
DB_CHARSET = 'utf8'
DB_NAME = 'orders_db'
'''