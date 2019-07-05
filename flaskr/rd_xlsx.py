#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xlrd, re
from . import mysql_tools
import time, json

# 返回 ( info, sheets_data )
# 	info - { 'res':'OK', 'uid':uid, 'auth':文件中作者名 } 或 { 'res':'NO', 'reason':'xxxxx' }
#			uid - 录入用户uid， auth - 录入用户登录名称
# 	sheets_data = [ {sheet1_data}, {sheet2_data},.... ]
# 	sheet1_data = { 'name':xx, 'main_id':xx, 'data':[sheet1_rows,...] }
# 如果解析失败，返回 ( {'res':'NO','reason':"xxxxx"}, [] )
def read_orders( file_name ):
	sheets = xlrd.open_workbook( file_name )
	sh_1 = sheets.sheet_by_index( 0 )
	uid, auth = sh_1.row_values( 0 )[1:3]
	
	uid = '%d' %uid
	#uid = str( uid )
	info = { 'res':'OK', 'uid':uid, 'auth':auth }
	
	############
	# 获取合并的单元格
	merged = merge_cell(sh_1)
	###############
	
	sheets_data = []
	for sh in sheets.sheets():
		try:	
			main_id = sh.cell(0,0).value
		except:
			return { 'res':'NO', 'reason':'文件格式错误！' }, sheets_data
		main_id = '%d' %main_id
		#main_id = str( main_id )
		sh_data = { 'main_id':main_id, 'name':sh.name, 'data':[] }
		mid = []
		try:
			mid = read_order_one_sheet( sh, merged, info )
		except:
			return { 'res':'NO', 'reason':'文件格式错误！' }, sheets_data
		if mid == []:
			r_str = '表 %s 中订单id重复' %( sh.name )
			info = { 'res':'NO', 'reason':r_str }
			sheets_data = []
			break
		else:
			for r in mid:
				r['id'] = main_id + '_' + uid + '_' + r['id']
			sh_data['data'].extend( mid )
		sheets_data.append( sh_data )
	return ( info, sheets_data )
	
	
def merge_cell(sheet):
	rt = {}
	if sheet.merged_cells:
		for item in sheet.merged_cells:
			for row in range(item[0], item[1]):
				for col in range(item[2], item[3]):
					rt.update({(row, col): (item[0], item[2])})
	return rt

	
# 返回 [ row_0, row_1, ... ]
# row_x = { 'id':xx, 'good':xx, 'c_d_name':xx,  'num':xx, 'backup':xx, 'p_note':xx, 
#  			't_note':xx, 'r_t':xx }
# row 中每个 key 都是数据库中的字段名称
# 进行id 重复性检查
def read_order_one_sheet( sheet, merged, info ):
	order_main_id = str(sheet.row_values( 0 )[0])
	uid = str(info['uid'])
	res, ids = [], []
	num = 0
	for row_id in range( 3, sheet.nrows ):
		rd = sheet.row_values( row_id )
		num += 0
		
		mid = {}
		if isinstance( rd[0], str ):
			mid['id'] = rd[0]
		else:
			mid['id'] = '%d' %rd[0]
		
		if mid['id']=='':
			continue
			
		ids.append( rd[0] )
		
		mid['type'] = (rd[1]).strip()
		mid['sub_type'] = (rd[2]).strip()
		mid ['c_d_name'] = (rd[3]).strip()
		mid['good'] = (rd[4]).strip()
		mid['standar'] = rd[5].strip()
		mid['num'] = rd[6]
		if rd[7] == '':
			mid['backup'] = 0
		else:
			mid['backup'] = rd[7]
		mid['price'] = rd[8]
		mid['p_note'] = rd[9]
		mid['r_t'] = rd[10]
		mid['t_note'] = (rd[11]).strip()
		mid['pack_note'] = ''
		res.append( mid )
		for index, content in enumerate(rd):
			if merged.get((row_id, index)):
				note = order_main_id[0:4] + '-' + order_main_id[4:6] + '-' + order_main_id[6:8] + '-' + uid + '-' + str(merged.get((row_id, index))[0])
				res[-1]['pack_note'] = note

	# 订单 id 重复性检查
	if len(ids) != len(set(ids)):
		res = []
	return res


# 公司名称检查
# 产品名称检查
# 通过后，写入数据库; 同时生成完整信息的生产计划excel文件
# 返回 ( {'res':'OK'}, order_info )  或  ( {'res':'NO', 'reason':xxxxx}, {} )
# order_info = { 'm_id':xxxx(主id), 'auth':xxx(作者), 't':订单日期(当地时间0点对应的UTC时间), 'orders':[ {order_1}, {order_2} ] }
#	order_x - dict
#		id: 		订单序号，		复制信息
#		type: 		订单类型，		复制信息
#		c_d_name:	公司显示名称，	复制信息
#		company:	公司开票名称						数据库查询补全
#		good_type:	产品类型
#		good:		产品名称，		复制信息
#		num:		数量，			复制信息
#		backup:		备份数量，		复制信息
#		unit:		规格								数据库查询补全，d_unit
#		price:		单价								数据库查询补全
#		p_note:		生产备注		复制信息
#		r_t:		要求送达时间	复制信息
#		t_note:		物流备注		复制信息
#		addr:		公司地址							数据库查询补全
#		contact:	联系人。格式：联系人名称，手机号	数据库查询补全
def orders_check_and_save( info, sheets_data, sql_conn ):
	for sh in sheets_data:
		c_d_names = get_company_d_name_from_the_sheet( sh )
		company_infos, failed = mysql_tools.match_companies_info( sql_conn, c_d_names )
		out_res, reason = { 'res':'OK' }, []
		if failed!=[]:
			reason.append( ','.join(failed)+' 不是标准公司名称' )
			out_res = { 'res':'NO' }
			
		contacts_info = mysql_tools.match_contacts( sql_conn, c_d_names )
		
		# 生成 order_info
		order_info = { 'm_id':sh['main_id'], 'auth':info['auth'], 'orders':[] }
		lt_str = sh['main_id'][0:4] + '-' + sh['main_id'][4:6] + '-' + sh['main_id'][6:8]
		s_t = time.strptime( lt_str, '%Y-%m-%d' )
		order_info['t'] = time.mktime( s_t )

		res, fruits_ary, failed, array_cat, array_fruits = get_goods_names_fruits( sql_conn, sh )
		if len(failed) > 0:
			reason.append( ','.join(failed)+' 不是标准产品名称' )
			out_res = { 'res':'NO' }	
		elif len(fruits_ary) > 0:
			#果切产品处理
			for ary in array_cat:
				mid = ary		
				mid['company'] = company_infos[ mid['c_d_name'] ]['company']
				mid['addr'] = company_infos[ mid['c_d_name'] ]['addr']
				mid['contact'] = contacts_info[mid['c_d_name']]['n'] + ',' + contacts_info[mid['c_d_name']]['phone']
				mid['good_type'] = '果切'
				unit_json = {'u':'','info':json.dumps(ary['good']),'d_unit':''}
				mid['unit'] = json.dumps( unit_json )
				mid['good'] = ary['good']
				mid['goods_info'] = json.dumps(ary['goods_info'])
				order_info['orders'].append( mid )	
									
		fruits_info, failed = mysql_tools.get_the_goods_info_good_name( sql_conn, res )
		if failed!=[]:
			reason.append( ','.join(failed)+' 不是标准产品名称' )
			out_res = { 'res':'NO' }
			
		if out_res['res']=='NO':
			return { 'res':'NO', 'reason':'\r'.join(reason) }, {}
			
		for rd in array_fruits:
			mid = rd
			mid['company'] = company_infos[ mid['c_d_name'] ]['company']
			mid['addr'] = company_infos[ mid['c_d_name'] ]['addr']

			unit_json = {'u':fruits_info[mid['good']]['unit'], 'info':fruits_info[mid['good']]['info'],'d_unit':fruits_info[mid['good']]['d_unit']}
			mid['unit'] = json.dumps( unit_json )
			
			mid['good_type'] = fruits_info[mid['good']]['type']
			
			mid['contact'] = contacts_info[mid['c_d_name']]['n'] + ',' + contacts_info[mid['c_d_name']]['phone']
			mid['goods_info'] = json.dumps({"m":{},"n":'',"w":'',"price":fruits_info[mid['good']]['price']})
			order_info['orders'].append( mid )
		# 写入数据库
		mysql_tools.insert_orders( sql_conn, order_info )
		
		return {'res':'OK'}, order_info
	
	
#返回 物流数据( info, sheets_data )
def logistics_orders(file_name):
	sheets = xlrd.open_workbook( file_name )
	sh_1 = sheets.sheet_by_name( u'Sheet1' )
	uid, auth = sh_1.row_values( 0 )[0], sh_1.row_values( 0 )[5]
	'''
	uid = xlrd.xldate_as_tuple(uid, 0)
	if uid[1] < 10:
		uid = str(uid[0]) + '0' + str(uid[1]) + str(uid[2])
	else:
		uid = str(uid[0])+ str(uid[1]) + str(uid[2])
	'''
	info = { 'res':'OK', 'm_id':uid, 'auth':auth}
	sheets_data = []
	for sh in sheets.sheets():
		mid = logistics_orders_sheet( sh )
		if mid == []:
			r_str = '表 %s 中订单id重复' %( sh.name )
			info = { 'res':'NO', 'reason':r_str }
			break
	return ( info, mid )
	

def logistics_orders_sheet( sheet ):
	res, ids = [], []
	for row_id in range( 3, sheet.nrows ):
		rd = sheet.row_values( row_id )
		mid = {}
		mid['id'] = rd[0]
		mid['driver'] = (rd[17]).strip()
		if rd[18] != '':
			show_time = xlrd.xldate_as_tuple(rd[18], 0)
			mid ['d_t'] = str(show_time[3]) + ':' + str(show_time[4]) + ':' + str(show_time[5])
		else:
			mid ['d_t'] = ''
		if rd[19] != '' and rd[20] != '':
			mid['actual_recv'] = rd[19]
			s_t = xlrd.xldate_as_tuple(rd[20], 0)
			mid['a_t'] = str(s_t[3]) + ':' + str(s_t[4]) + ':' + str(s_t[5])
		else:
			mid['actual_recv'] = ''
			mid['a_t'] = ''
		res.append( mid )
	# 订单 id 重复性检查
	if len(ids) != len(set(ids)):
		res = []
	return res	
	
#物流上传配送订单
#	id				订单全id
#	driver			司机信息（姓名+电话）
#	d_t				发车时间
#	actual_recv		客户实际接收数量
#	a_t				实际送达时间
def logistics_orders_edit( info, sheets_data, sql_conn ):
	for sh in sheets_data:
		result = mysql_tools.logistics_orders_sql_ids( sql_conn, sh['id'] )
		if result == False:
			return {'res':'NO', 'reason':', 订单序号异常！' }, {}
		#修改订单，添加物流信息
		count = mysql_tools.logistics_orders_edit_sql( sql_conn, sh )
		
		if count == 0:
			return {'res':'NO', 'reason':'上传物流订单失败！'}, {}
			
	return {'res':'OK'}, info	
	
	
			
def get_company_d_name_from_the_sheet( sh_data ):
	names = []
	for row in sh_data['data']:
		names.append( row['c_d_name'].strip() )
	names = list( set(names) )
	return names
'''
def get_ord_orders_detail_edit( sh_data ):
	ids = []
	print(sh_data)
	for row in sh_data:
		print(row)
		ids.append(row['id'])
	ids = list(ids)
	return ids
'''
'''
def get_goods_names_from_the_sheet( sh_data ):
	names = []
	for row in sh_data['data']:
		p = re.compile( r'[\d.]+[个g]' )
		m = p.match( row['standar'] )
		if m:
			if '个' in m.group():
				s = m.group().split('个')
				if s[-1] == '':
					unit = '个'
			elif 'g' in m.group():
				s = m.group().split('g')
				if s[-1] == '':
					unit = 'g'
			
		names.append( row['good']+'-'+unit )
	
	names = list( set(names) )
	return names
'''

#产品名称处理
def get_goods_names_fruits( sql_conn, sh_data ):
	res_ary = mysql_tools.get_all_goods_fruits_cut( sql_conn, '果切' )
	guoqie_dict = guoqie_database_2_dict( res_ary )
	
	result, fruits_ary, failed = [],[],[]	#不包含果切名称，果切名称，错误果切名称
	array_cut = []	#果切详情
	array_fruits = []	#不包含果切详情
	for sh in sh_data['data']:
		name, m_list = get_name_and_materials( sh['good'] )
		if len(m_list) > 0 and '果切' in sh['good']:
			res, st_name = if_valid_guoqie_name( sh['good'], guoqie_dict )
			if res == False:
				failed.append( st_name )
			else:
				fruits_ary.append( st_name )
				sh['good'] = st_name
				s_r = ''
				mid,md = {},{}
				for st in m_list:	#从果切原料中，获取当前果切需要的原料信息
					md[st] = guoqie_dict[name]['m'][st]
				mid['m'] = md
				mid['n'] = guoqie_dict[name]['n']
				mid['w'] = guoqie_dict[name]['w']
				mid['p'] = guoqie_dict[name]['price']
				sh['goods_info'] = mid
				array_cut.append( sh )
		else:
			result.append( sh['good'] )
			array_fruits.append( sh )
	fruits_ary = list( set(fruits_ary) )
	result = list( set(result) )
	
	return result, fruits_ary, failed, array_cut, array_fruits

			
# 从形如 名称（原料1+原料2） 中提取 名称 和 原料
# 返回 ( name, m_list )
#	m_list - [ 原料1, 原料2,... ]
def get_name_and_materials( goods_name ):
	pattern = re.compile( r'([\S]+)[ ]*[\(（]([\S]+)[\)）]' )
	m = pattern.match( goods_name )

	name, m_list = '', []
	if m and len(m.groups())>=2:
		name = m.group( 1 )
		name = name.replace( '＋', '+' )
		m_list = m.group( 2 ).split( '+' )
		
	return (name, m_list)


# 果切数据库信息转换为 dict 类型	
# guoqie_database - [ guoqie_0, guoqie_1, .... ]
# guoqie_x - { name:xx, info:xx, note:xxx }
#			info - json-str, { 原料1:出成率,... }
#			note - '100g-2'
# 返回转换成 dict 的果切数据，其格式为：
#		guoqie_infos[果切产品名称] = { 'm':{原料1:出成率,...}, 'w':该产品总重量（默认为g）, 'n':该产品中原料数量 }
def guoqie_database_2_dict( guoqie_database ):
	guoqie_infos = {}
	for item in guoqie_database:
		w, n = item['note'].split( '-' )
		guoqie_infos[item['name']] = { 'm':json.loads(item['info']), 'n':int(n), 'w':float(w.rstrip('g')), 'price':item['price']}
	return guoqie_infos


# 数据库中读出的果切产品信息
# in_name - 果切产品名称，字符串
# guoqie_dict - 见 guoqie_database_2_dict() 返回值
# 返回值：(True, 标准名称), (False,原名称)
def if_valid_guoqie_name( in_name, guoqie_dict ):
	res = False
	name, m_list = get_name_and_materials( in_name )
	if name=='' or m_list==[]:
		return res, in_name
	st_name = ''	
	if name in guoqie_dict and len(m_list)==guoqie_dict[name]['n']:
		res, st_name = True, in_name
		for m in m_list:
			if m not in guoqie_dict[name]['m']:
				res = False
				continue
	if res:
		m_list.sort()
		st_name = '%s（%s）' %( name, '+'.join(m_list) )
	else:
		return False, in_name
	return res, st_name	


# 获取产品信息内容
# 返回 (res, reason), res - [ {'type':,xx,'name':xx,'origin':xx,'unit':xx,'d_unit':xx,'price':xx,'info':xx}, {}, ]
# reason - xxxxxx.	reason为空时，res才有意义.
#
# 存入数据库的 info 要转为 json-str 的形式
# 在产品信息文件中，info 格式为 产品名称：x个, 产品名称：xg （各种标点可能为中文或英文字符）
def read_and_check_goods_info( file_path ):
	sheets = xlrd.open_workbook( file_path )
	res, reason, names = [], '', []
	for i in range( sheets.nsheets ):
		sh_1 = sheets.sheets()[i]	
		for row_id in range( 1, sh_1.nrows ):
			mid = {}
			try:
				_, mid['type'], mid['name'], mid['origin'], mid['unit'], mid['d_unit'], mid['price'], mid['info'], mid['standar'], mid['note'] = sh_1.row_values( row_id )
				mid['name'] = mid['name'].strip()
			except:
				return ( [],'产品构成内容格式错误' )
				
			if mid['name']=='':
				continue	
			
			if mid['d_unit']=='':
				mid['d_unit'] = mid['unit']
			
			if mid['price']=='':
				mid['price'] = 0.0
			
			if mid['standar'] == '':
				mid['standar'] = '1个'
				
			if mid['type'] == '果切':
				if mid['info']!='':
					p = re.compile( r'[, ，]' )
					segs = p.split( mid['info'] )
					unit_mid = {}
					p = re.compile( r'(\S+)[: ：](\d+(\.\d+)?)' )
					for s in segs:
						m = p.match( s )
						if m:
							unit_mid[ m.group(1) ] = m.group(2)
						else:
							return ( [], mid['name']+'中产品构成内容格式错误' )
					mid['info'] = json.dumps( unit_mid )
			else:
				if mid['info']!='':
					p = re.compile( r'[, ，]' )
					segs = p.split( mid['info'] )
					unit_mid = {}
					p = re.compile( r'(\S+)[: ：](\d+(\.\d+)?)' )
					for s in segs:
						m = p.match( s )
						if m:
							unit_mid[ m.group(1) ] = m.group(2)
						else:
							return ( [], mid['name']+'中产品构成内容格式错误' )
					mid['info'] = json.dumps( unit_mid )
			res.append( mid )
			names.append( mid['name']+'-'+mid['origin']+'-'+mid['unit'] )
			
		# 判断名称是否有重复
		set_names = set( names )
		if len(set_names)!=len(names):
			for sn in set_names:
				names.remove( sn )
			return ( [], ','.join(names)+'重复' )
	return res, reason

	
#获取用户信息
def rd_excel_ord_people(file_path):
	sheets = xlrd.open_workbook( file_path )
	res, reason, names = [], '', []
	for i in range( sheets.nsheets ):
		sh_1 = sheets.sheets()[i]	
		for row_id in range( 1, sh_1.nrows ):
			mid = {}
			mid['name'], mid['sex'], mid['phone'], mid['c_d_name'], mid['c_by'] = sh_1.row_values( row_id )
			if mid['c_d_name']=='':
				continue
			res.append(mid)
			names.append(mid['c_d_name'])
		set_names = set(names)
		if len(set_names) != len(names):
			for n in set_names:
				names.remove(n)
			return([], ','.join(names) + '重复')
	return res, reason

	
#获取公司信息
def rd_excel_ord_company(file_path):
	sheets = xlrd.open_workbook( file_path )
	res, reason, names = [], '', []
	for i in range( sheets.nsheets ):
		sh_1 = sheets.sheets()[i]	
		for row_id in range( 1, sh_1.nrows ):
			mid = {}
			mid['g_name'], mid['c_d_name'], mid['company'], mid['payment_days'], mid['province'], mid['city'], mid['district'], mid['addr'], mid['c_by'] = sh_1.row_values( row_id )
			if mid['c_d_name']=='':
				continue
			if '天' in mid['payment_days']:
				day = mid['payment_days'].split('天')
				mid['payment_days'] = day[0]
			elif '预付款' in mid['payment_days']:
				mid['payment_days'] = -1
			else:	#现结
				mid['payment_days'] = 0
			res.append(mid)
			names.append(mid['c_d_name'])
		set_names = set(names)
		if len(set_names) != len(names):
			for n in set_names:
				names.remove(n)
			return([], ','.join(names) + '重复')
	return res, reason

	
#上传申请发票处理
def rd_excel_apply_invoice( file_path ):
	sheets = xlrd.open_workbook( file_path )
	sh_1 = sheets.sheet_by_index(0)
	
	sn_time = sh_1.row_values( 0 )[0]
	m_mail, _, u_mail = sh_1.row_values( 0 )[5:8]
	info = { 'res':'OK', 'm_mail':m_mail, 'u_mail':u_mail, 'sn_time':sn_time, 'sheet':[] }
	
	res = []
	#for sh in sheets.sheets():
	sh_state = { 'apply_by':m_mail, 'apply_t':time.time(), 'invoice_by':u_mail, 'invoice_t':'' }
	state = json.dumps(sh_state)
	shr = []
	for row_id in range( 3, sh_1.nrows ):
		rd = sh_1.row_values( row_id )
		mid = {}
		if rd[13] == '申请开票':
			mid['id'] = rd[0]
			mid['state'] = 7
			mid['o_note'] = state
			res.append( mid )
			
	try:
		sh_2 = sheets.sheet_by_index(1)
	except:
		return [],''
	
	ary = []
	for row2 in range( 0, sh_2.nrows ):
		rd = sh_2.row_values( row2 )
		mid = {}
		mid['company'] = rd[0]
		mid['price'] = rd[1]
		ary.append(mid)
	info['sheet'].append(ary)
		
	return 	res, info
	
	
#财务开票处理
def rd_excel_finance_invoice( file_path ):
	sheets = xlrd.open_workbook( file_path )
	sh_1 = sheets.sheet_by_index(0)
	
	m_mail, _, u_mail = sh_1.row_values( 0 )[5:8]
	info = { 'res':'OK', 'm_mail':m_mail, 'u_mail':u_mail }
	sh_state = { 'apply_by':m_mail, 'apply_t':'', 'invoice_by':u_mail, 'invoice_t':time.time() }
	#state = json.dumps(sh_state)
	
	res = []
	for row in range( 3, sh_1.nrows ):
		rd = sh_1.row_values( row )
		mid = {}
		mid['id'] = rd[0]
		if rd[13] == '申请开票':
			mid['state'] = 6
		elif rd[13] == '已开票':
			mid['state'] = 8
		elif rd[13] == '':
			mid['state'] = 6
		if rd[14] == '':
			mid['o_note'] = sh_state
		else:
			s_t = json.loads( rd[14] )
			s_t['invoice_t'] = time.time()
			mid['o_note'] = json.dumps(s_t)
			
		res.append( mid )
	return res, info
			
	
	
	
if __name__=="__main__":
	
	db_ip = '127.0.0.1'
	db_user = 'root'
	db_passwd = ''
	'''
	db_ip = '101.200.233.199'
	db_user = 'root'
	db_passwd = 'aZuL2H58CcrzhTdt'
	'''
	db_name = 'orders_db'

	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name )

	info, sheets_data = read_orders( '2222订单.xlsx' )
	#print(info,'===========',sheets_data)
	
	orders_check_and_save( info, sheets_data, sql_conn )
	#mysql_tools.get_the_goods_info( '', ['wdh','xzm'] )
	
	#res, reason = read_and_check_goods_info( 'F:\python_xls\产品目录-04-29-顺达版.xlsx' )
	#print(res,'=====',reason)
	
	
	'''
	host = '127.0.0.1'
	port = 3306
	user = 'root'
	password = ''
	dbName = 'orders_db'
	charsets = 'utf8'
	
	conn = mysql_tools.conn_mysql(host, user, password, dbName)
	
	print(mysql_tools.check_and_save_goods_info(conn, res, ''))
	'''
	
	
	
	