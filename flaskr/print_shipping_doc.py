import xlrd, re
from . import mysql_tools
import time, json
from . import wt_xlsx


# d_range_str - d_range_str = '20190518-20190519'
def get_t_list( d_range_str ):
	t1, t2 = d_range_str.split( '-' )
	t1 = wt_xlsx.localtime_str_to_utc( '%s-%s-%s 00:00:00' %(t1[0:4], t1[4:6], t1[6:8]) )
	t2 = wt_xlsx.localtime_str_to_utc( '%s-%s-%s 23:59:59' %(t2[0:4], t2[4:6], t2[6:8]) )

	t_list = [ t1 ]
	while t_list[-1]<t2:
		t_list.append( t_list[-1]+24*3600 )
	del t_list[-1]

	return t_list
	
	
if __name__=='__main__':

	db_ip = '101.200.233.199'
	db_user = 'guocool'
	db_passwd = 'aZuL2H58CcrzhTdt'
	db_port = 3306
	db_charset = 'utf8'
	db_name = 'orders_db'
	
	'''
	db_ip = '127.0.0.1'
	db_user = 'blue'
	db_passwd = 'blue'
	db_name = 'orders_db'
	db_port = 3306
	db_charset = 'utf8'
	'''
	
	#d_range_str = '20190518-20190519'
	#d_range_str = '20190527-20190528'
	d_range_str = '20190527-20190527'
	t_list = get_t_list( d_range_str )
	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name, db_port, db_charset )
	
	for t in t_list:
		date_str = wt_xlsx.utc_to_localtime_str( t, type='day' )
		date_str = ''.join( date_str.split('-') )
		save_path = date_str + '_shipping_doc.xlsx'
		orders = mysql_tools.get_day_orders_all( sql_conn, date_str, fetch_type='m_id' )
		order_info = { 'm_id':date_str, 'auth':'wangdehi', 'orders':orders }
		wt_xlsx.gen_invoice_v3( order_info, save_path )
		

	