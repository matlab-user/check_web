# 支持多 sheet 导入
# 支持 错误输出

import xlrd, time
from . import mysql_tools
from . import rd_xlsx, wt_xlsx
import json, copy


# 返回 ( info, sheets_data )
# 	info - { 'res':'OK', 'uid':uid, 'auth':文件中作者名 } 或 { 'res':'NO', 'reason':'xxxxx' }
#			uid - 录入用户uid， auth - 录入用户登录名称
# 	sheets_data = [ {sheet1_data}, {sheet2_data},.... ]
# 	sheet1_data = { 'name':xx, 'main_id':xx, 'data':[sheet1_Rows,...] }
# 如果解析失败，返回 ( {'res':'NO','reason':"xxxxx"}, [] )
def read_orders( sh ):
	uid, auth = sh.row_values( 0 )[1:3]
	
	try:
		uid = '%d' % uid
	except:
		return { 'res':'NO', 'reason':'%s uid错误' %sh.name }, []
		
	info = { 'res':'OK', 'uid':uid, 'auth':auth }

	sheets_data = []
	# 获取合并的单元格
	merged = rd_xlsx.merge_cell( sh )
	try:	
		main_id = sh.cell(0,0).value
	except:
		return { 'res':'NO', 'reason':'%s 文件 main_id 格式错误' %sh.name }, sheets_data

	if isinstance(main_id, float) or isinstance(main_id, int):
		main_id = int( main_id )
	
	main_id = str( main_id )
	sh_data = { 'main_id':main_id, 'name':sh.name, 'uid':uid, 'auth':auth, 'data':[] }
	mid = []
	try:
		mid = rd_xlsx.read_order_one_sheet( sh, merged, info )
	except:
		return { 'res':'NO', 'reason':'%s 文件格式错误' %sh.name }, sheets_data

	if mid == []:
		r_str = '表 %s 中订单id重复' %( sh.name )
		info = { 'res':'NO', 'reason':r_str }
		sheets_data = []
	else:
		for r in mid:
			r['id'] = main_id + '_' + uid + '_' + r['id']
		sh_data['data'].extend( mid )
	return info, sh_data

	
def get_sheets_data( file_name ):
	book = xlrd.open_workbook( file_name )
	all_err, sheets_data = { 'res':'OK', 'reason':[] }, []
	for sh in book.sheets():
		info, mid_sheets_data = read_orders( sh )
		if info['res']!='OK':
			all_err['res'] = 'NO'
			all_err['reason'].append( info['reason'] )
		else:
			sheets_data.append( mid_sheets_data )
	
	if all_err['res']=='NO':
		return all_err, {}
	else:
		return all_err, sheets_data


# 判断给定产品名称是否存在于数据库中
# goods_names - [ n1, n2, n3,... ]
# 返回 failed - [ n1, n2...]
def if_in_goods_table( sql_conn, goods_names ):
	if goods_names==[]:
		return []
		
	sql_cmd = 'SELECT name FROM ord_goods WHERE state<>2 and '
	for n in goods_names:
		sql_cmd += 'name=%s or '
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd, goods_names )
	# data - (('徐福记梳打饼干20g',), ('御食园蜜麻花12g',))
	data = cur.fetchall()
	
	failed, succ_n_set = [], []
	for i in data:
		succ_n_set.append( i[0] )

	failed = list( set(goods_names)-set(succ_n_set) )
	cur.close()
	return failed


# 返回数据库中所有指定产品的信息( 非果切类 )
# sheet_data = { 'name':xx, 'main_id':xx, 'data':[sheet1_Rows,...] }
# 返回 ( res, failed )
# succ = {'n1':{good_info_1}, 'n2':{good_info_2},... }
def get_the_goods_info( sql_conn, goods_names ):
	if goods_names==[]:
		return {}

	sql_cmd = 'SELECT name, type, val, unit, d_unit, info, price, origin FROM ord_goods WHERE state<>2 and '
	for n in goods_names:
		sql_cmd += 'name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	data = cur.fetchall()
	
	succ = {}
	for d in data:	
		mid = {}
		mid['name'], mid['type'], mid['val'], mid['unit'], mid['d_unit'], mid['info'], mid['price'], mid['origin'] = d
		
		mid['good_type'] = mid['type']
		mid['good'] = mid['name']
		succ[ mid['good'] ] = mid
	cur.close()
	return succ
	

# 返回数据库中所有指定产品的信息( 果切类 )
# sheet_data = { 'name':xx, 'main_id':xx, 'data':[sheet1_Rows,...] }
# 返回 ( res, failed )
# succ = {'n1':{good_info_1}, 'n2':{good_info_2},... }
def get_the_goods_info_fruit_cut( sql_conn, goods_names ):
	if goods_names==[]:
		return {}
	
	st_names, names_m = [], {}
	for name in goods_names:
		n, m_list = rd_xlsx.get_name_and_materials( name )
		st_names.append( n )
		names_m[name] = { 'n':n, 'm':m_list }
		
	st_name = list( set(st_names) )
	sql_cmd = 'SELECT name, type, val, unit, d_unit, info, price, origin, note FROM ord_goods WHERE state<>2 and '
	for n in st_names:
		sql_cmd += 'name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	data = cur.fetchall()
	
	mid_d, succ = {}, {}
	for d in data:	
		mid = {}
		mid['name'], mid['type'], mid['val'], mid['unit'], mid['d_unit'], mid['info'], mid['price'], mid['origin'], mid['note'] = d
		mid['info'] = json.loads( mid['info'] )
		mid_d[ mid['name'] ] = mid

	for k, v in names_m.items():
		mid = copy.deepcopy( mid_d[ v['n'] ] )
		mid['info'], full_m = {}, mid_d[ v['n'] ]['info']

		mid['good_type'] = mid['type']
		mid['good'] = k
		
		w, n = mid['note'].split( '-' )
		goods_info = { 'w':float(w), 'n':n, 'm':{} }
		for m in v['m']:
			goods_info['m'][m] = full_m[ m ]
		mid['goods_info'] = json.dumps( goods_info )
		succ[mid['good']] = mid
	
	cur.close()	
	return succ
	
	
# 判断 订单产品名称是否存在（果切、非果切都进行判断）
# 返回 cut_list, other_list, failed_list - [ n1, n2...]
def check_goods_name( sql_conn, sheet_data ):
	goods_names = []
	for order in sheet_data['data']:
		goods_names.append( order['good'] )
	goods_names = list( set(goods_names) )
	
	fruits_cut_goods_name = mysql_tools.get_all_goods_fruits_cut( sql_conn, '果切' )
	# guoqie_dict - [ {'name':xx, 'm':xxx}, {}.... ]
	guoqie_dict = rd_xlsx.guoqie_database_2_dict( fruits_cut_goods_name )

	cut_list, other_list, failed_list = [], [], []
	for name in goods_names:
		if '(' in name or '（' in name:
			n, m_list = rd_xlsx.get_name_and_materials( name )
			if len(m_list)>0:		# 很可能是果切
				if n in guoqie_dict:		# 判断原料是否正确
					sig, M = True, guoqie_dict[n]['m']
					for m in m_list:
						if m not in M:
							sig = False
							break
					if not sig:
						failed_list.append( name )
					else:
						cut_list.append( name )
				else:
					other_list.append( name )
			else:					# 一定不是果切
				other_list.append( name )
		else:						# 一定不是果切
			other_list.append( name )
		
	# 果切已经判断完毕，开始判别 other_list
	mid_failed = if_in_goods_table( sql_conn, other_list )
	failed_list.extend( mid_failed )
	
	return cut_list, other_list, failed_list

	
# 公司名称检查
# 产品名称检查
# 通过后，写入数据库; 同时生成完整信息的生产计划excel文件
# 返回 ( {'res':'OK'}, sheets_data )  或  ( {'res':'NO', 'reason':xxxxx}, {} )
# orders_info - [ order_1_info, order_2_info... ]
# order_info = { 'm_id':xxxx(主id), 't':订单日期(当地时间0点对应的UTC时间), 'auth':xx, 'data':[ {order_1}, {order_2} ] }
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
def orders_check_and_save( file_name, sql_conn ):
	res, orders_info = orders_read_and_check( file_name, sql_conn )
	if res['res']=='NO':
		return res, {}
	
	for order_info in orders_info:
		mysql_tools.insert_orders( sql_conn, order_info )

	return {'res':'OK'}, orders_info


# { 'res':'NO', 'reason':XXX }, [] 或 {'res':'OK'}, orders_info
# orders_info - [ order_1_info, order_2_info... ]
def orders_read_and_check( file_name, sql_conn ):
	res, sheets_data = get_sheets_data( file_name )
	if res['res']=='NO':
		return { 'res':'NO', 'reason':'订单文件读取失败，可能格式有问题' }, []
	
	orders_info = []
	for sh in sheets_data:		
		c_d_names = rd_xlsx.get_company_d_name_from_the_sheet( sh )
		company_infos, failed = mysql_tools.match_companies_info( sql_conn, c_d_names )
		out_res, reason = { 'res':'OK' }, []

		if failed!=[]:
			reason.append( ','.join(failed)+' 不是标准公司名称' )
			out_res = { 'res':'NO' }
		
		contacts_info, failed = mysql_tools.match_contacts( sql_conn, c_d_names )
		if len(failed)>0:
			reason.append( ','.join(failed)+' 无此联系人' )
			out_res = { 'res':'NO' }
		
		# 对产品名称进行判断
		cut_list, other_list, failed_list = check_goods_name( sql_conn, sh )
		if len(failed_list)>0:
			failed_list = list( set(failed_list) )
			reason.append( ','.join(failed_list)+' 不是标准产品名称' )
			out_res = { 'res':'NO' }

		if out_res['res']=='NO':
			return { 'res':'NO', 'reason':'\r\n'.join(reason) }, []
		
		other_goods_info = get_the_goods_info( sql_conn, other_list )
		fruits_cut_info = get_the_goods_info_fruit_cut( sql_conn, cut_list )
		goods_info = dict( other_goods_info, **fruits_cut_info )

		# 生成 order_info
		order_info = { 'm_id':sh['main_id'], 'uid':sh['uid'], 'auth':sh['auth'], 'orders':[] }
		lt_str = sh['main_id'][0:4] + '-' + sh['main_id'][4:6] + '-' + sh['main_id'][6:8]
		s_t = time.strptime( lt_str, '%Y-%m-%d' )
		order_info['t'] = time.mktime( s_t )

		for rd in sh['data']:
			mid = rd
			if mid['price']=='':
				mid['price'] = 0
			mid['company'] = company_infos[ mid['c_d_name'] ]['company']
			mid['addr'] = company_infos[ mid['c_d_name'] ]['addr']

			mid['unit'] = json.dumps( {'u':mid['standar'], 'd_unit':goods_info[mid['good']]['d_unit']} )
			mid['good_type'] = goods_info[ mid['good'] ]['type']
			mid['contact'] = contacts_info[mid['c_d_name']]['n'] + ',' + contacts_info[mid['c_d_name']]['phone']
			
			if 'goods_info' in goods_info[mid['good']] and goods_info[mid['good']]['goods_info']!='':
				mid['goods_info'] = json.loads( goods_info[mid['good']]['goods_info'] )
				mid['goods_info'] = json.dumps( mid['goods_info'] )
			else:
				mid['goods_info'] = ''
		
			order_info['orders'].append( mid )
			
		orders_info.append( order_info )
		
	return {'res':'OK'}, orders_info
	
	
def read_orders_date( file_name ):
	t_list = []
	book = xlrd.open_workbook( file_name )
	for sh in book.sheets():
		mid = sh.row_values(0)[0]
		if isinstance( mid, float ):
			mid = str( int(mid) )		
		try:
			lt_str = '%s-%s-%s 00:00:00' %( mid[0:4], mid[4:6], mid[6:8] )
			res = wt_xlsx.localtime_str_to_utc( lt_str )
			t_list.append( res )
		except:
			return []
	return t_list
	
	
# 加单和修改订单功能
# 支持多 sheet 录入
# 新增订单功能, 订单 id 命名规则为: YYYYMMDD_uid_LA序号		例:20190531_1_LA12
# 返回 {'res':'NO', 'reason':xxx}  或  {'res':'OK'}
def add_new_orders( file_name, sql_conn ):
	res, orders_info = orders_read_and_check( file_name, sql_conn )
	if res['res']=='NO':
		return res
	
	for order_info in orders_info:
		order_ids = mysql_tools.get_day_orders_id_with_m_id( sql_conn, order_info['m_id'] )
		mid_o_id = '%s_%s_LA' %( order_info['m_id'], order_info['uid'] )
		for one in order_info['orders']:	
			for i in range( 10**2 ):
				if mid_o_id+str(i) not in order_ids:
					new_id = mid_o_id + str(i)
					order_ids.append( new_id )
					break
			one['id'] = new_id
			
		mysql_tools.insert_orders( sql_conn, order_info )

	return {'res':'OK'}
	

# 对原有订单进行修改
# 如待修改订单 为 20190531_1_12，则修改后的订单编号为 20190531_1_12C
# 同时将被修改的订单状态设为 2
def change_orders( file_name, sql_conn ):
	res, orders_info = orders_read_and_check( file_name, sql_conn )
	if res['res']=='NO':
		return res
	
	suc, err = [], []
	for order_info in orders_info:
		order_ids = mysql_tools.get_day_orders_id_with_m_id( sql_conn, order_info['m_id'] )
		# 此时从excle文件中读取数据后, 每个订单id 变为 mainid_uid_文件中的id订单
		# 对于该函数, 文件中的订单id为 YYYYMMDD_uid_序号
		for one in order_info['orders']:
			suc.append( one['id'][0:-1] )	
			one['id'] += 'C'
			
		# 修改订单应已经存在于数据库中	
		for s in suc:
			if s not in order_ids:
				err.append( s )
	
		# 全部正确才能进行更改处理
		if err==[]:	
			mid_one_info = order_info
			for i, s in enumerate( suc ):
				mid_one_info['orders'] = [order_info['orders'][i]]
				mysql_tools.change_the_order( sql_conn, s, mid_one_info )
		
	if err!=[]:
		return {'res':'NO', 'reason':','.join(err)+'不是标准的订单编号'}

		
# order_info - { 'name':sheet_name, 'main_id':xx, 'data':[Row] }						
# Row - { id, type, sub_type, c_d_name, good, unit, num, backup, price, p_note, r_t, t_note, pack_note, tools(way), auth }
# 此时 id 为 uid
def add_change_order_from_web( sql_conn, order_info ):
	Row = order_info['data'][0]
	c_d_names = [ Row['c_d_name'] ]
	company_infos, failed = mysql_tools.match_companies_info( sql_conn, c_d_names )
	out_res, reason = { 'res':'OK' }, []
	if failed!=[]:
		reason.append( ','.join(failed)+' 不是标准公司名称' )
		out_res = { 'res':'NO' }
		
	contacts_info, failed = mysql_tools.match_contacts( sql_conn, c_d_names )
	if len(failed)>0:
		reason.append( ','.join(failed)+' 无此联系人' )
		out_res = { 'res':'NO' }
			
	# 对产品名称进行判断
	cut_list, other_list, failed_list = check_goods_name( sql_conn, order_info )
	if len(failed_list)>0:
		failed_list = list( set(failed_list) )
		reason.append( ','.join(failed_list)+' 不是标准产品名称' )
		out_res = { 'res':'NO' }

	if out_res['res']=='NO':
		return { 'res':'NO', 'reason':'\r\n'.join(reason) }
		
	other_goods_info = get_the_goods_info( sql_conn, other_list )
	fruits_cut_info = get_the_goods_info_fruit_cut( sql_conn, cut_list )
	goods_info = dict( other_goods_info, **fruits_cut_info )
	
	# 生成 o_info
	o_info = { 'm_id':order_info['main_id'], 'uid':Row['id'], 'auth':order_info['auth'], 'orders':[] }
	lt_str = order_info['main_id'][0:4] + '-' + order_info['main_id'][4:6] + '-' + order_info['main_id'][6:8]
	s_t = time.strptime( lt_str, '%Y-%m-%d' )
	o_info['t'] = time.mktime( s_t )
	
	if Row['price']=='':
		Row['price'] = 0
	Row['company'] = company_infos[ Row['c_d_name'] ]['company']
	Row['addr'] = company_infos[ Row['c_d_name'] ]['addr']
	Row['unit'] = json.dumps( {'u':Row['unit'], 'd_unit':goods_info[Row['good']]['d_unit']} )
	Row['good_type'] = goods_info[ Row['good'] ]['type']
	Row['contact'] = contacts_info[Row['c_d_name']]['n'] + ',' + contacts_info[Row['c_d_name']]['phone']
	
	if 'goods_info' in goods_info[Row['good']] and goods_info[Row['good']]['goods_info']!='':
		Row['goods_info'] = json.loads( goods_info[Row['good']]['goods_info'] )
		Row['goods_info'] = json.dumps( Row['goods_info'] )
	else:
		Row['goods_info'] = ''
	o_info['orders'].append( Row )

	way = Row['tools']
	del Row['tools'], Row['n'], Row['auth'], Row['m_id']
	
	o_info['order'] = o_info['orders'][0]
	del o_info['orders']
		
	if way=='new':
		order_ids = mysql_tools.get_day_orders_id_with_m_id( sql_conn, o_info['m_id'] )
		mid_o_id = '%s_%s_LA' %( o_info['m_id'], o_info['uid'] )
		for i in range( 10**2 ):
			if mid_o_id+str(i) not in order_ids:
				new_id = mid_o_id + str(i)
				order_ids.append( new_id )
				break
		o_info['order']['id'] = new_id		
		mysql_tools.insert_one_order( sql_conn, o_info['order'], o_info )
		
	elif way=='change':
		order_ids = mysql_tools.get_day_orders_id_with_m_id( sql_conn, o_info['m_id'] )
		orig_id = o_info['order']['id']
		orig_order = mysql_tools.get_the_order_with_id( sql_conn, orig_id )
		if orig_order==[]:
			return { 'res':'NO', 'reason':'%s订单不存在' % orig_id }
		
		changed = []
		fields = ['type', 'sub_type', 'c_d_name', 'good', 'unit', 'num', 'backup', 'p_note', 'r_t', 't_note']
		f_names = {'type':'类型', 'sub_type':'子类型', 'c_d_name':'公司', 'good':'产品', 'unit':'单位', 'num':'数量',
					'backup':'备份数量', 'p_note':'生产说明', 'r_t':'达到时间', 't_note':'运输要求'}
		for f in fields:
			if orig_order[f]!=o_info['order'][f]:
				changed.append( f_names[f] )
				
		o_info['order']['o_note'] = ','.join( changed ) + ' 变更'
		o_info['order']['id'] += 'C'
		
		mysql_tools.change_the_order( sql_conn, orig_id, o_info )
	
	return {'res':'OK'}		
	
	
	
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
	
	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name, db_port, db_charset )
	#file_name = 'test3.xlsx'
	#file_name = 'multi_sheets_orders.xlsx'
	#add_new_orders( file_name, sql_conn )
	#change_orders( file_name, sql_conn )
	#order_ids = mysql_tools.get_day_orders_with_m_id_uid( sql_conn, '20190530' )
	#res, _ = orders_check_and_save( file_name, sql_conn )
	#print( res )
	#t_list = read_orders_date( 'temp_yangli@guocool.com.xlsx' )
	#print( t_list )
	
	Row = { 'id':1, 'type':'w1', 'sub_type':'w2', 'c_d_name':'网易', 'good':'进口柠檬', 'unit':'个', 'num':3,
			'backup':1, 'price':2.0, 'p_note':'wangdehui', 'r_t':'11:00-12:00', 't_note':'xiezhimei', 'pack_note':'p1', 'tools':'new' }


	
	