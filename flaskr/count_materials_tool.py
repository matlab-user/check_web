import xlrd, time
from . import mysql_tools
from . import rd_xlsx, wt_xlsx
import json, xlsxwriter
import hashlib


def gen_purchase_sum( order_info, out_file_name ):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet( '零食糕点整果饮品' )
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	wt_xlsx.get_purchase_sum_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
	row = 3
	
	# 除了果切外的产品数量
	worksheet.set_column( 1, 1, 40 )
	for name, v in order_info['orders'].items():
		worksheet.set_row( row, 20 )
		worksheet.write( row, 0, v['good_type'] )
		worksheet.write( row, 1, name )
		if v['unit'] in ['g','克']:
			worksheet.write( row, 2, v['sum']/1000 )
			worksheet.write( row, 3, '千克' )
		else:
			worksheet.write( row, 2, v['sum'] )
			worksheet.write( row, 3, v['unit'] )
		row += 1
	
	worksheet = workbook.add_worksheet('果切')
	cell_format = workbook.add_format( property )
	wt_xlsx.get_purchase_sum_header2( worksheet, order_info['m_id'], order_info['auth'], cell_format )
	row = 2
	for name, v in order_info['order_cut'].items():
		worksheet.set_row( row, 20 )
		
		worksheet.write( row, 0, v['good_type'] )
		worksheet.write( row, 1, name )
		if v['unit'] in ['g','克']:
			worksheet.write( row, 2, v['sum']/1000 )
			worksheet.write( row, 3, '千克' )
		else:
			worksheet.write( row, 2, v['sum'] )
			worksheet.write( row, 3, v['unit'] )
		row += 1

	return workbook
	

# 采购汇总
# failed - [ {'m_id': '20190527', 'id': '20190527_22_28', 'good':xxxx} ]
def get_marterials_data( sql_conn, d_range_str, save_path ):
	order_sum, failed_1 = mysql_tools.gen_purchase_table_except_fruit_cutting( sql_conn, d_range_str )
	order_sum_cut, failed_2 = mysql_tools.gen_purchase_table_fruit_cutting( sql_conn, d_range_str )
	order_info = { 'm_id':d_range_str, 'auth':'aida', 'orders':order_sum, 'order_cut': order_sum_cut}
	workbook = gen_purchase_sum( order_info, save_path )
	
	failed_1.extend( failed_2 )
	if len(failed_1)>0:
		write_faild_goods( failed_1, workbook )
		
	workbook.close()


def write_faild_goods( failed, workbook ):
	sh = workbook.add_worksheet( u'统计失败的产品' )
	sh.set_column( 0, 1, 30 )
	sh.set_column( 2, 2, 90 )
	row = 0
	for f in failed:
		sh.write( row, 0, f['m_id'] )
		sh.write( row, 1, f['id'] )
		sh.write( row, 2, f['good'] )
		row += 1
	
	
if __name__=='__main__':
	'''
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
	
	#d_range_str = '20190518-20190519'
	d_range_str = '20190602-20190602'
	save_path = d_range_str + '_materials.xlsx'
	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name, db_port, db_charset )
	get_marterials_data( sql_conn, d_range_str, save_path )
	
	
	