import xlrd, time
from . import mysql_tools
from . import rd_xlsx, wt_xlsx
import json, xlsxwriter
import hashlib

# order_info = { 'm_id':xxxx, 'auth':xxx, 'orders':[ {order_1}, {order_2} ] }
# order_x - dict 类型
#	id: 		订单序号，		录入信息
#	type: 		订单类型，		录入信息
#	c_d_name:	公司显示名称，	录入信息
#	company:	公司开票名称
#	good_type:	产品类型
#	good:		产品名称，		录入信息
#	num:		数量，			录入信息
#	backup:		备份数量，		录入信息
#	unit:		规格
#	price:		单价
#	p_note:		生产备注		录入信息
#	r_t:		要求送达时间	录入信息
#	t_note:		物流备注		录入信息
#	addr:		公司地址
#	contact:	联系人。格式：地址，联系人名称，手机号
def gen_production_plan( order_info, worksheet, cell_format ):
	wt_xlsx.gen_production_plan_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
		
	lt_ary = []
	for n in order_info['orders']:
		if n['pack_note'] == '':
			lt_ary.append(n)
	
	#判断是否是合并单元格
	array = []
	arr = []
	for info in order_info['orders']:
		if info['pack_note'] != '':
			array.append(info)
			arr.append(info['pack_note'])
	ary = set(arr)
	
	keys_list = [ 'id', 'type', 'sub_type', 'c_d_name', 'company', 'good_type', 'good', 'standar', 'num', 'backup', 'unit', 'price', 'p_note', 'r_t', 't_note', 'addr', 'contact' ]
	row, data = 3, ''
	
	#未合并单元格处理
	for od in lt_ary:
		for i, k in enumerate( keys_list ):
			if k == 'unit':
				u = json.loads( od[k] )
				if 'info' in u and u['info'] != '':
					#s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
					s = u['d_unit']
				else:
					#s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
					s = u['d_unit']
				worksheet.write( row, i, s )
				data += s
			else:
				worksheet.write( row, i, od[k] )
				data += str( od[k] )
		row += 1
	
	remark = ''
	#合并单元格处理
	num = row+1	#记录合并行的首行索引
	for ary_ix in ary:
		for ay in array:
			if ay['pack_note'] == ary_ix:
				#worksheet.set_row( row, 15 )
				for i, k in enumerate( keys_list ):
					if k == 'unit':
						u = json.loads( ay[k] )
						if 'info' in u and u['info'] != '':
							#s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
							s = u['d_unit']
						else:
							#s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
							s = u['d_unit']
						worksheet.write( row, i, s )
						data += s
					else:
						worksheet.write( row, i, ay[k] )
						data += str( ay[k] )
					if ay['p_note'] != '':
						remark = ay['p_note']
				row += 1
		param_str = str('M') + str(num) + ':' + str('M') + str(row)
		worksheet.merge_range( param_str, remark, cell_format )
		worksheet.write( str('M') + str(num), remark, cell_format )
		num = row + 1
		
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'U1', md5 )


# d_range_str - d_range_str = '20190518-20190519'
def get_t_list( d_range_str ):
	try:
		t1, t2 = d_range_str.split( '-' )
		t1 = wt_xlsx.localtime_str_to_utc( '%s-%s-%s 00:00:00' %(t1[0:4], t1[4:6], t1[6:8]) )
		t2 = wt_xlsx.localtime_str_to_utc( '%s-%s-%s 23:59:59' %(t2[0:4], t2[4:6], t2[6:8]) )
	except:
		return []

	t_list = [ t1 ]
	while t_list[-1]<t2:
		t_list.append( t_list[-1]+24*3600 )
	del t_list[-1]

	return t_list


def gen_production_plan_v2( sql_conn, save_path, d_range_str ):
	t_list = get_t_list( d_range_str )
	workbook = xlsxwriter.Workbook( save_path )
	property = {
			'bold':True,
			'align':'center',
			'valign': 'vcenter',
			'font_name': u'微软雅黑',
		}
	cell_format = workbook.add_format( property )
	
	for t in t_list:
		orders = mysql_tools.get_day_orders_all( sql_conn,  t, fetch_type='t' )
		order_info = { 'm_id':wt_xlsx.utc_to_localtime_str(t)[0:11], 'auth':'wangdehui', 'orders':orders }
		worksheet = workbook.add_worksheet( order_info['m_id'] )
		gen_production_plan( order_info, worksheet, cell_format )
	workbook.close()
	
	
# out_res - { type:[name1,name2....]....'果切':{name1:'xxxxxx'....} }
# com_res - [xx,xx,xx]
def gen_goods_list( save_path, out_res, com_res=None ):
	workbook = xlsxwriter.Workbook( save_path )
	property = {
			'bold':True,
			'align':'center',
			'valign': 'vcenter',
			'font_name': u'微软雅黑',
		}
	cell_format = workbook.add_format( property )
	
	for k, v in out_res.items():
		worksheet = workbook.add_worksheet( k )
		if k=='果切':
			i = 0
			for key, val in v.items():
				worksheet.write( i, 0, key )
				worksheet.write( i, 1, val )
				i += 1
		else:
			for i, n in enumerate( v ):
				worksheet.write( i, 0, n )
				
	if com_res is not None:
		worksheet = workbook.add_worksheet( '公司名称' )
		for i, n in enumerate(com_res):
			worksheet.write( i, 0, n )
		
	workbook.close()
	


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
	
	d_range_str = '20190530-20190530'
	save_path = d_range_str + '_orders.xlsx'
	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name, db_port, db_charset )
	gen_production_plan_v2( sql_conn, save_path, d_range_str )
	
	
	
	