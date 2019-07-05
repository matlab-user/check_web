#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import time, copy, json
from . import rd_xlsx, wt_xlsx
import re


def conn_mysql( ip, user, passwd, db_name, db_port, db_charset ):
	try:
		conn = pymysql.connect( host=ip, user=user, password=passwd, db=db_name, port=db_port, charset=db_charset )
	except:
		conn = []	
	return conn
	

# 将订单信息写入数据库
# 返回成功写入的记录数量
def insert_orders( sql_conn, order_info ):
	cur = sql_conn.cursor()
	sql_str = 'INSERT INTO ord_orders_detail ('
	keys = []
	for k in order_info['orders'][0].keys():
		keys.append( k )
		sql_str += '%s,' %k
	sql_str += 't, c_by, c_t, m_id ) VALUES '
	for one in order_info['orders']:
		v_str = ''
		for k in keys:
			if k in ['price','num','backup']:
				if one[k]=='':
					v_str += '0,'
				else:
					v_str += '%f,' %one[k]
			elif k == 'discount':
				if one[k]=='':
					v_str += '1,'
				else:
					v_str += '%f,' %one[k]
			elif k=='unit':
				v_str += '%s,' % sql_conn.escape( one['unit'] )
			elif k=='pack_note':
				if one[k]=='':
					v_str += '"",'
				else:
					v_str += '"%s",' %one[k]
			elif k=='goods_info':
				if one[k]=='':
					v_str += '"",'
				else:
					v_str += '%s,' %sql_conn.escape( one['goods_info'] )	#%one[k]
			else:
				if one[k]=='':
					v_str += '"",'
				else:
					v_str += '"%s",' %one[k]
					
		sql_str += '(%s,%f,"%s",%f,"%s"),' %( v_str[0:-1], order_info['t'], order_info['auth'], time.time(), order_info['m_id'] )
	sql_str = sql_str[0:-1]
	count = cur.execute( sql_str )
	cur.close()
	
	return count

#-----------------------------------------------------------------------------------------------------------------------------
# order_info- { t, auth, m_id }
def insert_one_order( sql_conn, one_order, order_info ):
	sql_str = 'INSERT INTO ord_orders_detail ('
	keys, v_str = [], ''
	for k in one_order.keys():
		keys.append( k )
		sql_str += '%s,' % k
	sql_str += 't, c_by, c_t, m_id ) VALUES ('
	
	data = []
	for k in keys:
		sql_str += '%s,'
		data.append( one_order[k] )
		
	sql_str += '%s, %s, %s, %s )'
	data.extend( [order_info['t'], order_info['auth'], time.time(), order_info['m_id']] )

	cur = sql_conn.cursor()
	count = cur.execute( sql_str, data )
	cur.close()
	return count


# order_info['t'], order_info['auth'], order_info['m_id'], order_info['order']
def change_the_order( sql_conn, orig_id, order_info ):
	insert_one_order( sql_conn, order_info['order'], order_info )
	del_the_order( sql_conn, orig_id, 3 )
	return {'res':'OK'}
	

# state=1 正常; =2 删除; =3 此订单被修改
def del_the_order( sql_conn, order_id, new_state ):
	sql_str = 'UPDATE ord_orders_detail SET state=%s WHERE id=%s'
	cur = sql_conn.cursor()
	cur.execute( sql_str, [new_state, order_id] )
	sql_conn.commit()
	return {'res':'OK'}


# 获取某天，删除、新增、修改后的订单
def get_one_day_changed_orders( sql_conn, m_id ):
	orders = get_one_day_all_orders( sql_conn, m_id )
	del_orders, new_orders, modified_orders = [], [], []
	
	for o in orders:
		del o['n']
		if o['state']==2:
			del_orders.append( o )
		elif o['state']==1:
			if 'C' in o['id']:		# 被修改的订单
				modified_orders.append( o )
			elif 'LA' in o['id']:
				new_orders.append( o )

	return del_orders, new_orders, modified_orders
	

# 返回 该记录的 dict 类型, 数据库中的列名为 key
# fields 为空，标识取默认列; 否则仅取指定列，list 类似
def get_one_order_with_id( sql_conn, order_id, fields='' ):
	if fields=='':
		fs = 'm_id, id, t, type, good, c_d_name, company, addr, price, num, backup, p_note, t_note, d_t, r_t, good_type, unit, contact'
	else:
		fs = ''
		for f in fields:
			fs += f + ','
		fs = fs[0:-1]
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE id="%s"' %( fs, order_id )
	
	cur = sql_conn.cursor()
	count = cur.execute( sql_cmd )
	data = cur.fetchone()
	cur.close()
	
	res = {}
	for i, f in enumerate( fields ):
		res[f] = data[i]
	
	return res


# res - [ {'id':x, 'type':x...}, {}, ]
def get_one_day_all_orders( sql_conn, m_id ):
	fs = ['id', 'type', 'sub_type', 'c_d_name', 'good', 'unit', 'num', 'backup', 'price', 'p_note', 'r_t', 't_note', 'pack_note', 'o_note', 'state']
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE m_id=%s' %( ','.join(fs), m_id )
	
	cur = sql_conn.cursor()
	count = cur.execute( sql_cmd )
	data = cur.fetchall()
	cur.close()
	
	res = []
	for i, d in enumerate( data ):
		mid = { 'n': i }
		for i, k in enumerate( fs ):
			if k=='unit':
				unit_dict = json.loads( d[i] )
				mid[k] = unit_dict['u']
			else:
				mid[k] = d[i]
		res.append( mid )
	return res
	

# 在订单已经生成锁定后执行订单修改
# order_info = { 'm_id':xxxx(主id), 'auth':xxx(作者), 't':订单日期(当地时间0点对应的UTC时间), 'orders':[ {order_1}, {order_2} ] }
# order_x['type'] - '新增'、‘减少’、‘取消’，仅处理具有该属性的订单
# 其中 减少，需要补全减少数量
# 返回修改的数量。如果为0，则应该发邮件提示。
def	insert_orders_urgent( sql_conn, order_info ):
	changed_num = 0
	for one in order_info['orders']:
		if one['type']=='新增':
			insert_one_order( sql_conn, one, order_info )
			changed_num += 1
		elif one['type']=='取消':
			sql_cmd = 'UPDATE ord_orders_detail SET state=2, type="%s" WHERE id="%s"' %( one['type'], one['id'] )
			cur = sql_conn.cursor()
			cue.execute( sql_cmd )
			changed_num += 1
		elif one['type']=='减少':
			res = get_one_order_with_id( sql_conn, one['id'], ['num'] )
			one['type'] += str( float(res['num'])-one['num'] )
			
			sql_cmd = 'UPDATE ord_orders_detail SET state=2, type="%s" WHERE id="%s"' %( one['type'], one['id'] )
			cur = sql_conn.cursor()
			cue.execute( sql_cmd )
			changed_num += 1
			
	cur.close()		
	return changed_num
	

# 根据公司开票名称统计当前所在天(截至到当天23:59:59)所有已完成订单的价格数据
# 返回 res - res['sum_with_backup'], res['real_sum'], res['sum_without_backup']
def count_all_orders_price_by_company( sql_conn, company_name ):
	now = time.time()
	end_t = (now//(24*3600) + 1) * (24*3600)
	
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = 'price, num, backup, actual_recv'
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE state=6 and company="%s" and t<%f' %( fields, m_id, end_t )
	cur.execute( sql_cmd )

	sum_with_backup, sum_without_backup, real_sum = 0.0, 0.0, 0.0
	for d_r in cur:
		price, num, backup, real_recv = d_r
		price, num, backup = float(price), float(num), float(backup)
		if real_recv=='':
			real_recv = num 
		sum_with_backup += price * ( num+backup )
		real_sum = price * real_recv
		sum_without_backup = price * num
		
	cur.close()
	return res


# 根据公司显示名称 和 m_id ，获取所有已完成订单信息
# 返回 res - [ res_0, res_1..... ]
# res_x - k:v
def count_all_orders_price_by_c_d_name( sql_conn, c_d_name, m_id ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = ['m_id', 'good', 'c_d_name', 'addr', 'price', 'num', 'backup', 'r_t', 'contact']
	fields_str = ','.join( fields )
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE state<>2 and c_d_name="%s" and m_id="%s"' %( fields, c_d_name, m_id )
	cur.execute( sql_cmd )

	res, id = [], 1
	for d_r in cur:
		mid = {}
		mid['id'] = id
		id += 1
		for i, k in enumerate(fields):
			mid[k] = d_r[i]
		mid['m_id'] = mid['m_id'][0:4] + '-' + mid['m_id'][4:6] + '-' + mid['m_id'][6:]
		mid['r_t'] = mid['m_id'] + ' ' + mid['r_t']
		res.append( mid )
	cur.close()
	return res

	
def insert_goods_info( sql_conn, goods_info, who ):
	#查询产品名称
	cur, res = sql_conn.cursor(), 0
	ary = []
	parm = []
	for goods in goods_info:
		mid = {}
		mid['name'] = goods['name']
		if goods['origin'] == '':
			mid['origin'] = ""
		else:
			mid['origin'] = goods['origin']
		mid['unit'] = goods['unit']
		ary.append(mid)
		parm.append(goods['name']+'-'+goods['origin']+'-'+goods['unit'])
	_, failed = get_the_goods_info(sql_conn, ary, parm)
	nameList = list(set(parm) - set(failed))	#两个集合的差，failed表示不存在
	
	if nameList:
		sql_str = 'delete from ord_goods where'
		for nl in nameList:
			n = nl.split('-')
			name,origin,unit = n[0:]
			sql_str += ' name="%s" and origin="%s" and unit="%s" or ' %(name,origin,unit)
		sql_str = sql_str[0:-3]
		cur.execute(sql_str)
	
	if nameList == []:
		sql_str = 'delete from ord_goods where'
		for nt in parm:
			t = nt.split('-')
			nameT,originT,unitT = t[0:]
			sql_str += ' name="%s" and origin="%s" and unit="%s" or ' %(nameT,originT,unitT)
		sql_str = sql_str[0:-3]
		cur.execute(sql_str)
	
	sql_cmd = 'INSERT INTO ord_goods ( type, name, origin, unit, d_unit, price, info, state, c_by, c_t, note, standar ) VALUES '
	if len(goods_info)>0: 	
		for o in goods_info:
			mid = '( "%s", "%s", "%s", "%s", "%s", %f, %s, 1, "%s", %f, "%s", "%s" ),' %( o['type'], o['name'], o['origin'], o['unit'], o['d_unit'], o['price'], json.dumps(o['info']), who, time.time(), o['note'], o['standar'] )
			sql_cmd += mid
		sql_cmd = sql_cmd[0:-1]
		res = cur.execute( sql_cmd )
		cur.close()
		
		if res!=len(goods_info):
			return ( res, '数据库中插入产品信息部分或全部失败' )
		else:
			return ( res, '' )
	else:
		return ( res, '' )
	


# goods_info - rd_xlsx.read_and_check_goods_info() 返回的产品信息, 已经保证不重名
# goods_info - [ {}, {}... ], k 为 数据库中的键值
# 新插入单一成分产品，再插入复合成分产品. 复合成分产品中的单一成分须已经存在于数据库中
# 返回 ( res, reason ), res 为成功插入的产品数量; reason为失败的原因，全部成功为''
def check_and_save_goods_info( sql_conn, goods_info, who ):
	single_gs, compand_gs, compand_names = [], [], []
	res = 0
	for g in goods_info:
		if g['type']!='果切':
			single_gs.append( g )
		else:
			compand_gs.append( g )
			mid = json.loads( g['info'] )
			compand_names.extend( mid.keys() )
	compand_names = list( set(compand_names) )
	
	if single_gs != []:
		res, reason = insert_goods_info( sql_conn, single_gs, who )
		if reason!='':
			return ( res, reason )
	if compand_names != []:
		gs_info, failed = get_the_goods_info_cut( sql_conn, compand_names )
	
		if len(failed)>0:
			return ( res, ','.join(failed)+'未存在于产品数据库中' )
		else:
			res, reason = insert_goods_info( sql_conn, compand_gs, who )
		
	return ( res, '' )


# unit_str - xxx个/g/克
# 			xxxx 无单位，默认为 0个
# 返回 ( val, unit )
def parse_uint( unit_str ):
	p = re.compile( r'\s*([\d.]*) *([g个克]?)' )
	m = p.match( unit_str )
	if m:
		val = m.group( 1 )
		if m.group(1)=='':
			val = 1
		else:
			val = float( val )
	
		unit = m.group(2)
		if unit=='':
			unit = '个'
			val = 0
	else:
		return ( None, None )

	return ( val, unit )


'''
# 如果是果切，original_orders[name] 中会存在 info 键值
# info - {'u':x个/xxg/xx克, 'info':xxx, 'd_unit':xx }
if 'info' in mid and mid['info']!='':
	original_orders[name]['info'] = mid['info']
original_orders[name]['d_unit'] = mid['d_unit']		
'''
				
# 汇总水果采购信息, 产生 t_range_str 中的采购数据
# t_range_str 格式 - 20190317-20190318
# st、end - UTC 时间戳，订单数据中的 t 数据
#
# 返回 - original_orders, raw_m
#	raw_m - { goods_1:{'sum':采购总数量(含备份、损耗), 'unit':采购用单位(g/个)}, goods_2:{}, ... }
#	original_orders - { goods_1:{ 'sum':(num+backup), 'd_unit':d_unit, 's_price':总价 } ... }
#
# 计算公式为:			数量×unit
# 结果按照产品成分名称进行累计
# 返回 除果切外统计失败的产品（主要可能发生在订单数据不全上）
def gen_purchase_table_except_fruit_cutting( sql_conn, t_range_str ):	
	original_orders, raw_m, failed_goods = {}, {}, []
	t_list = parse_t_range( t_range_str )
	for t in t_list:
		one_day_orders = get_day_orders_all( sql_conn, t, fetch_type='t' )
		for one in one_day_orders:
			if one['good_type']=='果切':
				continue
			try:	
				goods_unit_json = json.loads( one['unit'] )
			except:
				failed_goods.append( one )
				continue
				
			this_order_num = float(one['num']) + float(one['backup'])
			
			# 复合产品，需要对每种原料进行计数
			if 'info' in goods_unit_json and goods_unit_json['info']!='':
				mid_info = json.loads( v['info'] )
				for raw_name, num_unit in mid_info.items():
					val, unit = parse_uint( num_unit )
					st_raw_name = '%s(%s)' %( raw_name, unit )
					SUM = this_order_num * val
				
					if st_raw_name in raw_m:
						raw_m[st_raw_name]['sum'] += SUM
					else:
						raw_m[st_raw_name] = { 'sum':SUM, 'unit':unit, 'good_type':one['good_type'] }
					
			else:
				mid_val, mid_unit = parse_uint( goods_unit_json['u'] )
				if mid_val is None:
					failed_goods.append( one )
					continue
					
				name = '%s(%s)' %( one['good'], mid_unit )	
				
				# 订单信息中，同一种产品的价格可能不同
				# 价格是针对 数量定的; 每单位数量的产品，其构成可能是复合原料的，例如: 圣女果8个装
				this_order_num *= float( mid_val )
					
				if name not in raw_m:
					raw_m[name] = { 'sum':this_order_num, 'unit':mid_unit, 'good_type':one['good_type'] }		
				else:
					raw_m[name]['sum'] += this_order_num
	
	return raw_m, failed_goods
	

# 仅计算果切原料数据
# failed - [ {'m_id': '20190527', 'id': '20190527_22_28', 'good':xxxx} ]
def gen_purchase_table_fruit_cutting( sql_conn, t_range_str ):	
	original_orders, raw_m, failed = {}, {}, []
	t_list = parse_t_range( t_range_str )
	for t in t_list:
		one_day_orders = get_day_orders_all( sql_conn, t, fetch_type='t' )
		for one in one_day_orders:
			if one['good_type']!='果切':
				continue	
			
			# 订单信息中，同一种产品的价格可能不同
			this_order_num = float(one['num']) + float(one['backup'])
			name = one['good']
			
			mid = { 'sum':this_order_num, 'good_type':one['good_type'] }
			try:
				guoqie_unit = json.loads( one['unit'] )
				if guoqie_unit['u']=='':
					mid['unit'] = '个'
				else:
					mid['unit'] = guoqie_unit['u']
				mid['d_unit'] = guoqie_unit['d_unit']	
				
				# m-原料及出成绿， n-原料数量 w-产品总重量
				mid['goods_info'] = json.loads( one['goods_info'] )
			except:
				failed.append( one )
				continue
				
			if name not in original_orders:
				original_orders[name] = mid
			else:
				original_orders[name]['sum'] += this_order_num
	
	orders_list = []
	for k, v in original_orders.items():
		mid = v
		mid['good'] = k
		orders_list.append( mid )
		
	goods_sum, m_sum = guoqie_materials_summary( orders_list )
	for mk,vk in m_sum.items():
		m_d = {}
		m_d['good'] = mk
		m_d['unit'] = 'g'
		m_d['sum'] = float('%.2f' % vk)
		m_d['good_type'] = '果切'
		raw_m[mk] = m_d
		
	return raw_m, failed
	

# 数据库中读出的果切订单数据
# 保证此时订单中果切产品名称皆为合法的
# guoqie_orders - [ order_0, order_1, ... ]
# 					order_x - { 'good':xxx, 'sum':xx, 'goods_info':{'m':{原料1:出成率,...}, 'w':产品重量} }
# 		order_x 中，'good'表示的名称已经为果切标准名称了
#					'goods_info' 已经从 json-str 解析为 json 对象。（goods_info 在上传订单数据时，直接存入订单数据库中）
#					'goods_info' 中的 m 域中仅存该产品使用到的原料
#
# 返回 ( goods_sum, m_sum )
# goods_name - {果切名称1:数量, ...}, 果切产品数量汇总;		m_sum - { 原料1:重量,... },各原料需要准备的量，单位g
def guoqie_materials_summary( guoqie_orders ):
	goods_sum, m_sum = {}, {}
	for o in guoqie_orders:
		this_num = o['sum']
		if o['good'] in goods_sum:
			goods_sum[ o['good'] ] += this_num
		else:
			goods_sum[ o['good'] ] = this_num
		
		# 计算该条订单中每种原料的重量, 每种原料重量相等
		each_w = this_num * float(o['goods_info']['w']) / len(o['goods_info']['m'])
		
		mid_m = {} 
		for k, v in o['goods_info']['m'].items():
			mid_m[k] = float(each_w) / float(v)
		
		for k, v in mid_m.items():
			if k in m_sum:
				m_sum[k] += v
			else:
				m_sum[k] = v
				
	return ( goods_sum, m_sum )
	
#-----------------------------------------------------------------------------------------------------------------------------

# 根据用户登录名(email)，获取用户uid，权限
# { 'id':id, 'auth':{}, 'name':xx, 'email':xx }
def get_user_info_with_uid( sql_conn, email ):
	cur = sql_conn.cursor()
	sql_cmd = 'SELECT id, name, auth FROM WHERE email="%s"' %email
	
	res = {}
	cur.execute( sql_cmd )
	data = cur.fetchone()
	if data is not None:
		res['id'], res['name'], res['auth'] = data
		res['email'] = email
	cur.close()
	
	return res


# 返回数据库中所有指定产品的信息
# goods_names - [ n1, n2, n3,... ]
# 返回 ( res, failed )
# res = { n1:{good_info_1}, n2:{good_info_2}, n3:{good_info_3},... }
# failed = [ nx,.. ]	查询失败的名称
# lt (名称-地址-单位)
def get_the_goods_info( sql_conn, goods_names, lt ):
	sql_cmd = 'SELECT name, type, val, unit, d_unit, info, price, origin FROM ord_goods WHERE state=1 and '
	for n in goods_names:
		sql_cmd += 'name="%s" and origin="%s" and unit="%s" or ' %(n['name'],n['origin'],n['unit'])
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['name'], mid['type'], mid['val'], mid['unit'], mid['d_unit'], mid['info'], mid['price'],mid['origin'] = data
		succ_n_set.add( mid['name']+'-'+mid['origin']+'-'+mid['unit'] )
		res[ mid['name'] ] = mid 
	
	failed = list( set(lt)-succ_n_set )
	cur.close()
	return ( res, failed )	

	
# 返回数据库中所有指定产品的信息
# goods_names - [ n1, n2, n3,... ]
# 返回 ( res, failed )
# res = { n1:{good_info_1}, n2:{good_info_2}, n3:{good_info_3},... }
# failed = [ nx,.. ]	查询失败的名称
# lt (名称-单位)
def get_the_goods_info_good_name( sql_conn, goods_names ):
	if goods_names==[]:
		return {},[]
		
	sql_cmd = 'SELECT name, type, val, unit, d_unit, info, price, origin FROM ord_goods WHERE state<>2 and '
	for n in goods_names:
		sql_cmd += 'name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['name'], mid['type'], mid['val'], mid['unit'], mid['d_unit'], mid['info'], mid['price'],mid['origin'] = data
		succ_n_set.add( mid['name'] )
		res[ mid['name'] ] = mid 
	
	failed = list( set(goods_names)-succ_n_set )
	cur.close()
	return ( res, failed )	


#上传产品，果切名称校验	
# 返回数据库中所有指定产品的信息
# goods_names - [ n1, n2, n3,... ]
# 返回 ( res, failed )
# res = { n1:{good_info_1}, n2:{good_info_2}, n3:{good_info_3},... }
# failed = [ nx,.. ]	查询失败的名称
def get_the_goods_info_cut( sql_conn, goods_names ):
	sql_cmd = 'SELECT name, type, val, unit, d_unit, info, price, origin FROM ord_goods WHERE state=1 and '
	for n in goods_names:
		sql_cmd += 'name="%s" or ' %n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['name'], mid['type'], mid['val'], mid['unit'], mid['d_unit'], mid['info'], mid['price'],mid['origin'] = data
		succ_n_set.add( mid['name'] )
		res[ mid['name'] ] = mid 
	
	failed = list( set(goods_names)-succ_n_set )
	cur.close()
	return ( res, failed )	
	

# c_d_names - [ dn1, dn2,.. ], 公司显示名称
# 返回 ( res, failed )
# res = { c_d_name_1:{}, c_d_name_2:{}, c_d_name_3:{},... }
# failed = [ dnx,... ]	查询失败的名称
def match_companies_info( sql_conn, c_d_names ):
	sql_cmd = 'SELECT c_d_name, company, tax_info, province, city, district, addr FROM ord_company WHERE state=1 and '
	for n in c_d_names:
		sql_cmd += 'c_d_name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['c_d_name'], mid['company'], mid['tax_info'], mid['province'], mid['city'], mid['district'], mid['addr'] = data
		succ_n_set.add( mid['c_d_name'] )
		res[ mid['c_d_name'] ] = mid
		
	failed = list( set(c_d_names)-succ_n_set )
	cur.close()
	return ( res, failed )		


# ids - [ dn1, dn2,.. ],订单全id
# 查询id是否存在
def logistics_orders_sql_ids( sql_conn, id ):
	sql_cmd = 'select count(1) from ord_orders_detail where state=1 and m_id="%s"' %id
	cur = sql_conn.cursor()
	count = cur.execute( sql_cmd )
	if count >= 1:
		res = True
	else:
		res = False
	return res
	
	
#上传物流配送信息
#返回修改数量
def logistics_orders_edit_sql(sql_conn, data):
	cur = sql_conn.cursor()
	if data['actual_recv'] != '' and data['a_t'] != '':
		sql_cmd = 'update ord_orders_detail set driver="%s",d_t="%s",actual_recv="%s",a_t="%s",state=6 where id="%s"' %(data['driver'],data['d_t'],data['actual_recv'],data['a_t'],data['id'])
	else:
		sql_cmd = 'update ord_orders_detail set driver="%s",d_t="%s",state=5 where id="%s"' %(data['driver'],data['d_t'],data['id'])
	count = cur.execute( sql_cmd )
	sql_conn.commit()
	cur.close()
	return count
	

# 根据公司的发票名称，返回联系人、公司地址信息
# c_d_names - [ cn1, cn2,... ]
# 返回：{ cn1:{ 'n':name, 'phone':xx }, cn2:{},... }
def match_contacts( sql_conn, c_d_names ):
	cur = sql_conn.cursor()
	
	sql_cmd = 'SELECT c_d_name, name, phone FROM ord_pick_up_people WHERE state=1 AND'
	for name in c_d_names:
		sql_cmd += ' c_d_name=%s OR' 
	sql_cmd = sql_cmd[0:-3]
	
	res, get_names = {}, []
	cur.execute( sql_cmd, c_d_names )
	while True:
		data = cur.fetchone()
		if data is None:
			break
			
		mid = {}
		c_d_name, mid['n'], mid['phone'] = data
		try:
			mid['phone'] = str( int(float(mid['phone'])) )
		except:
			pass
		res[c_d_name] = mid
		get_names.append( c_d_name )

	fail = list( set(c_d_names)-set(get_names) )
	cur.close()
	return res, fail


# 删除所有的等于指定的订单主id的记录
def del_orders_with_main_id( sql_conn, main_id, mail  ):
	cur = sql_conn.cursor()
	sql_cmd = 'DELETE FROM ord_orders_detail WHERE m_id="%s" and c_by="%s"' %(main_id, mail)
	count = cur.execute( sql_cmd )
	cur.close()
	
	return count

	
#普通人员重新上传订单时,如果订单状态为正常（1），可以删除，然后重新上传
def del_orders_with_main_id_state_1( sql_conn, main_id ):
	cur = sql_conn.cursor()
	sql_cmd = 'DELETE FROM ord_orders_detail WHERE state = 1 and m_id="%s"' % main_id
	count = cur.execute( sql_cmd )
	cur.close()
	
	return count
	

# main_id - 20190314-, 20190315
# 返回删除的行数	
def del_one_day_all_orders( main_id ):
	cur = sql_conn.cursor()
	m_id = main_id.split( '-' )[0]
	lt_str = m_id[0:4] + '-' + m_id[4:6] + '-' + m_id[6:8]
	s_t = time.strptime( lt_str, '%Y-%m-%d' )
	
	sql_cmd = 'DELETE FROM ord_orders_detail WHERE t=%f' %time.mktime( s_t )
	count = cur.execute( sql_cmd )
	cur.close()
	
	return count


# 给定的订单主id是否已经存在
def if_main_id_in( sql_conn, main_id, send ):
	cur = sql_conn.cursor()	
	sql_cmd = 'SELECT m_id FROM ord_orders_detail WHERE state<>2 and m_id="%s" and c_by="%s" LIMIT 1' %(main_id,send)
	cur.execute( sql_cmd )
	data = cur.fetchall()
	cur.close()
	if len( data )==1:
		return True
	else:
		return False


# 按天和编号获取所有订单数据
# 返回 [ {}, {}, {},... ]
def get_day_orders_with_m_id_uid( sql_conn, order_id ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = 'm_id, id, t, type, good, c_d_name, company, addr, price, num, backup, p_note, t_note, d_t, r_t, good_type, unit, contact,driver,d_t,actual_recv,a_t,sub_type,pack_note,standar,goods_info'
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE state<>2 and id like "%s%%%%" ' %( fields, order_id )
	cur.execute( sql_cmd )

	for d_r in cur:
		mid = {}
		mid['m_id'], mid['id'], mid['t'], mid['type'], mid['good'] = d_r[0:5]
		mid['c_d_name'], mid['company'], mid['addr'], mid['price'], mid['num'] = d_r[5:10]
		mid['backup'], mid['p_note'], mid['t_note'], mid['d_t'], mid['r_t'] = d_r[10:15] 
		mid['good_type'], mid['unit'], mid['contact'], mid['driver'], mid['d_t'] = d_r[15:20]
		mid['actual_recv'], mid['a_t'], mid['sub_type'], mid['pack_note'], mid['standar'] = d_r[20:25]
		mid['goods_info'] = d_r[25]
		res.append( mid )
	cur.close()
	
	orders = []
	orders.extend( copy.deepcopy(res) )
	
	return orders

	
# 按天获取所有订单数据
# 返回 [ {}, {}, {},... ]
def get_day_orders_with_t( sql_conn, t, tz=8 ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = 'm_id, id, t, type, good, c_d_name, company, addr, price, num, backup, p_note, t_note, d_t, r_t, good_type, unit, contact,driver,d_t,actual_recv,a_t,sub_type,pack_note,standar,goods_info'
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE state<>2 and t=%f' %( fields, t )

	cur.execute( sql_cmd )
	for d_r in cur:
		mid = {}
		mid['m_id'], mid['id'], mid['t'], mid['type'], mid['good'] = d_r[0:5]
		mid['c_d_name'], mid['company'], mid['addr'], mid['price'], mid['num'] = d_r[5:10]
		mid['backup'], mid['p_note'], mid['t_note'], mid['d_t'], mid['r_t'] = d_r[10:15] 
		mid['good_type'], mid['unit'], mid['contact'], mid['driver'], mid['d_t'] = d_r[15:20]
		mid['actual_recv'],mid['a_t'], mid['sub_type'], mid['pack_note'], mid['standar'] = d_r[20:25]
		mid['goods_info'] = d_r[25]
		res.append( mid )
	cur.close()
	return res
	

# 按天获取所有订单数据
# 返回 [ {}, {}, {},... ]
def get_day_orders_with_m_id( sql_conn, m_id ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = 'm_id, id, t, type, good, c_d_name, company, addr, price, num, backup, p_note, t_note, d_t, r_t, good_type, unit, contact,driver,d_t,actual_recv,a_t,sub_type,pack_note,goods_info'
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE state<>2 and m_id="%s" ' %( fields, m_id )
	cur.execute( sql_cmd )

	for d_r in cur:
		mid = {}
		mid['m_id'], mid['id'], mid['t'], mid['type'], mid['good'] = d_r[0:5]
		mid['c_d_name'], mid['company'], mid['addr'], mid['price'], mid['num'] = d_r[5:10]
		mid['backup'], mid['p_note'], mid['t_note'], mid['d_t'], mid['r_t'] = d_r[10:15] 
		mid['good_type'], mid['unit'], mid['contact'], mid['driver'], mid['d_t'] = d_r[15:20]
		mid['actual_recv'], mid['a_t'], mid['sub_type'], mid['pack_note'] = d_r[20:24]
		mid['goods_info'] = d_r[24]
		res.append( mid )
	cur.close()
	
	return res


# 按天获取所有订单数据
# 返回 {}
def get_the_order_with_id( sql_conn, id ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	fields = 'm_id, id, t, type, good, c_d_name, company, addr, price, num, backup, p_note, t_note, d_t, r_t, good_type, unit, contact,driver,d_t,actual_recv,a_t,sub_type,pack_note,state,goods_info'
	sql_cmd = 'SELECT %s FROM ord_orders_detail WHERE id="%s" ' %( fields, id )
	cur.execute( sql_cmd )
	for d_r in cur:
		mid = {}
		mid['m_id'], mid['id'], mid['t'], mid['type'], mid['good'] = d_r[0:5]
		mid['c_d_name'], mid['company'], mid['addr'], mid['price'], mid['num'] = d_r[5:10]
		mid['backup'], mid['p_note'], mid['t_note'], mid['d_t'], mid['r_t'] = d_r[10:15] 
		mid['good_type'], mid['unit'], mid['contact'], mid['driver'], mid['d_t'] = d_r[15:20]
		mid['actual_recv'], mid['a_t'], mid['sub_type'], mid['pack_note'], mid['state'] = d_r[20:25]
		mid['goods_info'] = d_r[25]
		res = mid
	cur.close()
	
	return res
	
	
# 仅获取天订单的所有id号
def get_day_orders_id_with_m_id( sql_conn, m_id ):
	cur, res = sql_conn.cursor( pymysql.cursors.SSCursor ), []
	sql_cmd = 'SELECT id FROM ord_orders_detail WHERE state<>2 and m_id="%s" ' %m_id
	cur.execute( sql_cmd )
	res = []
	for d_r in cur:
		res.append( d_r[0] )
	cur.close()
	return res


# 返回 [ {}, {}, {},... ]
# fetch_type='m_id'时，val 为具体 m_id 值
# fetch_type='t'时，val 为 订单数据中的 t 值
def get_day_orders_all( sql_conn, val, fetch_type='m_id' ):
	if fetch_type=='m_id':
		fetch_fun = get_day_orders_with_m_id
	else:
		fetch_fun = get_day_orders_with_t
	
	orders = []
	res = fetch_fun( sql_conn, val )
	orders.extend( copy.deepcopy(res) )
	
	return orders


# 解析错误返回 []
# 解析成功，返回每天的零点 UTC 时间
def parse_t_range( t_range_str ):
	segs = t_range_str.split( '-' )
	st_str, end_str = segs
	try:
		st_str = st_str[0:4] + '-' + st_str[4:6] + '-' + st_str[6:8]
		st = time.mktime( time.strptime(st_str, '%Y-%m-%d') )
		
		end_str = end_str[0:4] + '-' + end_str[4:6] + '-' + end_str[6:8]
		end_t = time.mktime( time.strptime(end_str, '%Y-%m-%d') )
	except:
		return []
	
	t_list = [ st ]
	while True:
		st += 24*3600
		if st<=end_t:
			t_list.append( st )
		else:
			break
	return t_list
	

# 汇总水果采购信息, 产生 t_range_str 中的采购数据
# t_range_str 格式 - 20190317-20190318
# st、end - UTC 时间戳，订单数据中的 t 数据
#
# 返回 - { goods_1:{'n':数量, 'type':整果，零食等, 'sum':采购总数量, 'unit':采购用单位, 'val':每单位中数值部分,'s_price':总采购价, 'price':单价 }, goods_2:{}, ... }
#[{{'name':名称,'n':数量, 'type':整果，零食等, 'sum':采购总数量, 'unit':采购用单位, 'val':每单位中数值部分,'s_price':总采购价, 'price':单价 },....}]
# 计算公式为:			数量×val unit
# 结果按照产品名称进行累计1111111111
def gen_purchase_table1( sql_conn, t_range_str ):
	global fetch_rows
	cur = sql_conn.cursor()
	
	purchase_table, goods_names = {}, []
	t_list = parse_t_range( t_range_str )
	for t in t_list:
		one_day_orders = get_day_orders_all( sql_conn, t, fetch_type='t' )
		for item in one_day_orders:
			name = item['good']
			if name not in purchase_table:
				purchase_table[name] = { 'n':item['num']+item['backup'] }
				goods_names.append( name )
			else:
				purchase_table[name]['n'] += item['num'] + item['backup']
	goods_info, _ = get_the_goods_info( sql_conn, goods_names )
	for name in goods_names:
		purchase_table[name]['type'] = goods_info[name]['type']
		purchase_table[name]['val'] = float( goods_info[name]['val'] )
		purchase_table[name]['unit'] = goods_info[name]['unit']
		purchase_table[name]['price'] = float( goods_info[name]['price'] )
		
		purchase_table[name]['sum'] = purchase_table[name]['n'] * purchase_table[name]['val']
		purchase_table[name]['s_price'] = purchase_table[name]['n'] * purchase_table[name]['price']
	cur.close()
	return purchase_table

	
#保存企业对接人信息
def insert_ord_people(sql_conn, user_info):
	cur, res = sql_conn.cursor(), 0
	ary = []
	for names in user_info:
		ary.append(names['c_d_name'])
	_, failed = get_ord_people(sql_conn, ary)
	nameList = list(set(ary) - set(failed))	#两个集合的差，failed表示不存在
	
	if nameList:
		sql_str = 'delete from ord_pick_up_people where'
		for name in nameList:
			sql_str += ' name="%s" or ' %name
		sql_str = sql_str[0:-3]
		cur.execute(sql_str)
	
	sql_cmd = 'INSERT INTO ord_pick_up_people ( name, sex, phone, c_d_name, state, c_by, c_t ) VALUES '
	if len(user_info)>0: 	
		for o in user_info:
			mid = '( "%s", "%s", "%s", "%s", 1, "%s", %f ),' %( o['name'], o['sex'], o['phone'], o['c_d_name'], o['c_by'], time.time() )
			sql_cmd += mid
		sql_cmd = sql_cmd[0:-1]
		res = cur.execute( sql_cmd )
		cur.close()
		
		if res!=len(user_info):
			return ( res, '数据库中插入用户信息部分或全部失败' )
		else:
			return ( res, '' )
	else:
		return ( res, '' )

		
#校验企业用户对接人名称	
def get_ord_people( sql_conn, names ):
	sql_cmd = 'SELECT name, sex, phone, c_d_name, c_by FROM ord_pick_up_people WHERE state=1 and '
	for n in names:
		sql_cmd += 'c_d_name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['name'], mid['sex'], mid['phone'], mid['c_d_name'], mid['c_by'] = data
		succ_n_set.add( mid['c_d_name'] )
		res[ mid['c_d_name'] ] = mid 
		
	failed = list( set(names)-succ_n_set )
	cur.close()

	return ( res, failed )

	
#保存公司信息
def insert_ord_company( sql_conn, company ):
	cur, res = sql_conn.cursor(), 0
	ary = []
	for names in company:
		ary.append(names['c_d_name'])
	_, failed = get_ord_company(sql_conn, ary)
	nameList = list(set(ary) - set(failed))	#两个集合的差，failed表示不存在
	
	if nameList:
		sql_str = 'delete from ord_company where'
		for name in nameList:
			sql_str += ' name="%s" or ' %name
		sql_str = sql_str[0:-3]
		cur.execute(sql_str)
	
	sql_cmd = 'INSERT INTO ord_company ( g_name, c_d_name, company, payment_days, province, city, district, addr, c_by, c_t ) VALUES '
	if len(company)>0: 	
		for o in company:
			mid = '( "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", %f ),' %( o['g_name'], o['c_d_name'], o['company'], o['payment_days'], o['province'], o['city'], o['district'], o['addr'], o['c_by'], time.time() )
			sql_cmd += mid
		sql_cmd = sql_cmd[0:-1]
		res = cur.execute( sql_cmd )
		cur.close()
		
		if res!=len(company):
			return ( res, '数据库中插入公司信息部分或全部失败' )
		else:
			return ( res, '' )
	else:
		return ( res, '' )
	
	
#校验公司名称	
def get_ord_company( sql_conn, names ):
	sql_cmd = 'SELECT g_name, c_d_name, company, payment_days, province, city, district, addr, c_by, c_t FROM ord_company WHERE state=1 and '
	for n in names:
		sql_cmd += 'c_d_name="%s" or ' % n
	sql_cmd = sql_cmd[0:-3]
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	res, failed, succ_n_set = {}, [], set()
	while True:
		data = cur.fetchone()
		if data is None:
			break
		
		mid = {}
		mid['g_name'], mid['c_d_name'], mid['company'], mid['payment_days'], mid['province'], mid['city'], mid['district'], mid['addr'], mid['c_by'], mid['c_t'] = data
		succ_n_set.add( mid['c_d_name'] )
		res[ mid['c_d_name'] ] = mid 
		
	failed = list( set(names)-succ_n_set )
	cur.close()

	return ( res, failed )

	
#财务汇总订单金额	
def get_finance_summary( sql_conn, startTime, endTime ):
	sql_cmd = 'SELECT company,SUM(price*num) AS sum_price FROM ord_orders_detail WHERE m_id >= "%s" AND m_id <= "%s" GROUP BY company' %(startTime, endTime)
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	data = cur.fetchall()
	cur.close()
	res = []
	for dt in data:
		mid = {}
		mid['company'], mid['sum_price'] = dt
		res.append( mid )
	return res
	

#运营申请开票
#	s_t_m		开始时间
#	e_t_m			结束时间
def get_apply_orders_invoice( sql_conn, s_t_m, e_t_m ):
	sql_cmd = 'SELECT id,c_d_name,company,good,type,sub_type,good_type,price,num,backup,actual_recv,SUM(price*actual_recv) AS sum_price,standar,state' 
	sql_cmd += ' FROM ord_orders_detail WHERE state = 6 AND m_id >= "%s" AND m_id <= "%s" GROUP BY id' %(s_t_m, e_t_m)
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	data = cur.fetchall()
	cur.close()
	res = []
	for dt in data:
		mid = {}
		mid['id'], mid['c_d_name'], mid['company'], mid['good'], mid['type'] = dt[0:5]
		mid['sub_type'], mid['good_type'], mid['price'], mid['num'], mid['backup'] = dt[5:10]
		mid['actual_recv'], mid['sum_price'], mid['standar'] = dt[10:13]
		res.append( mid )
	return res


#运营上传申请开票
def insert_apply_invoice_info ( sql_conn, apply_invoice ):
	cur = sql_conn.cursor()
	count = 0
	for app in apply_invoice:
		sql_cmd = 'update ord_orders_detail set state=%d, o_note=%s where id="%s"' %(app['state'],json.dumps(app['o_note']),app['id'])
		try:
			cur.execute( sql_cmd )
			sql_conn.commit()
			count += 1
		except:
			count = 0
			return {'res':'NO'}, count
	cur.close()
	return ({'res':'OK'}, count)


#运营提交申请开票成功后，按照时间段查询申请开票的数据，发送给财务	
def get_apply_invoice_time( sql_conn, startTime, endTime ):
	sql_cmd = 'SELECT id,c_d_name,company,good,type,sub_type,good_type,price,num,backup,actual_recv,SUM(price*actual_recv) AS sum_price,state,o_note,standar'
	sql_cmd += ' FROM ord_orders_detail WHERE state = 7 AND m_id >= "%s" AND m_id <= "%s" GROUP BY id' %(startTime, endTime)
	cur = sql_conn.cursor()
	cur.execute( sql_cmd )
	data = cur.fetchall()
	cur.close()
	res = []
	for dt in data:
		mid = {}
		mid['id'], mid['c_d_name'], mid['company'], mid['good'], mid['type'] = dt[0:5]
		mid['sub_type'], mid['good_type'], mid['price'], mid['num'], mid['backup'] = dt[5:10]
		mid['actual_recv'], mid['sum_price'], mid['state'], mid['o_note'], mid['standar'] = dt[10:15]
		res.append( mid )
	return res


#财务上传开票信息，修改订单状态（state）为8
def update_finance_invoice( sql_conn, invoice ):
	cur = sql_conn.cursor()
	count = 0
	for n in invoice:
		sql_cmd = 'update ord_orders_detail set state=%d, o_note=%s where id="%s"' %(n['state'],json.dumps(n['o_note']),n['id'])
		try:
			cur.execute( sql_cmd )
			sql_conn.commit()
			count += 1
		except:
			count = 0
			return count
	cur.close()
	return count

#每日20点时执行，修改第二天订单状态为：生产锁定(3)
def update_system_order_lock( sql_conn, time_str ):
	cur = sql_conn.cursor()
	count = 0
	sql_cmd = 'update ord_orders_detail set state=3 where state=1 and m_id = "%s"' %time_str
	try:
		count = cur.execute( sql_cmd )
		sql_conn.commit()
	except:
		return 0
	cur.close()
	return count


#查询所有果切产品
def get_all_goods_fruits_cut( sql_conn, name ):
	cur = sql_conn.cursor()
	sql_cmd = 'select name,info,note,price from ord_goods where type=%s and state<>2'
	cur.execute( sql_cmd, [name] )
	data = cur.fetchall()
	cur.close()
	res = []
	for dt in data:
		mid = {}
		mid['name'], mid['info'], mid['note'], mid['price'] = dt[0:4]
		res.append( mid )
	return res
	

def add_com( sql_conn, com_info_list, com_addr_list ):
	cur = sql_conn.cursor()
	try:
		company = com_info_list[4]
	except:
		company = com_info_list[0]
		
	sql_cmd = 'INSERT INTO ord_company (c_d_name, province, city, district, addr, company, payment_days, state) VALUES (%s, %s, %s, %s, %s, %s, 60, 1)'
	data = [ com_info_list[0] ]
	data.extend( com_addr_list )
	data.append( company )
	try:
		c = cur.execute( sql_cmd, data )
		sql_conn.commit()
	except:
		return {'res':'NO', 'reason':'insert into ord_company failed' }
		
	if c<1:
		return {'res':'NO', 'reason':'insert into ord_company failed' }
	
	sql_cmd = 'INSERT INTO ord_pick_up_people (c_d_name, name, sex, phone, state ) VALUES (%s, %s, "u", %s, 1)'
	try:
		c = cur.execute( sql_cmd, com_info_list[0:3] )
		sql_conn.commit()
	except:
		return {'res':'NO', 'reason':'insert into ord_pick_up_people failed' }
		
	if c<1:
		return {'res':'NO', 'reason':'insert into ord_pick_up_people failed' }
		
	return {'res':'OK'}


# out_res - { type:[name1,name2....]....'果切':{name1:'xxxxxx'....} }
def get_goods_list( sql_conn ):
	cur = sql_conn.cursor()
	sql_cmd = 'SELECT type, name FROM ord_goods'
	cur.execute( sql_cmd )
	res = cur.fetchall()

	types_set = set()
	for r in res:
		types_set.add( r[0] )

	out_res, cuts = {}, [] 
	for t in types_set:
		out_res[t] = set()
		for r in res:
			if r[0]==t:
				out_res[t].add( r[1] )
				if t=='果切':
					cuts.append( r[1] )
		out_res[t] = list( out_res[t] )
	
	out_res['果切'] = {}

	sql_cmd = 'SELECT name, info FROM ord_goods WHERE type="果切" AND ( '
	for n in cuts:
		sql_cmd += 'name=%s OR '
	sql_cmd = sql_cmd[0:-3] + ')'

	cur.execute( sql_cmd, cuts )
	res = cur.fetchall()
	for r in res:
		info = json.loads( r[1] )
		ks = list( info.keys() )
		out_res['果切'][r[0]] = ','.join( ks )
	
	return out_res


def get_companys( sql_conn ):
	cur = sql_conn.cursor()
	sql_cmd = 'SELECT c_d_name FROM ord_company'
	cur.execute( sql_cmd )
	res = cur.fetchall()
	out_res = []
	for r in res:
		out_res.append( r[0] )
	return out_res


if __name__=="__main__":
	db_ip = '101.200.233.199'
	db_user = 'guocool'
	db_passwd = 'aZuL2H58CcrzhTdt'
	db_port = 3306
	db_charset = 'utf8'

	db_name = 'orders_db'
	sql_conn = conn_mysql( db_ip, db_user, db_passwd, 'orders_db', db_port, db_charset )
	#sql_conn = conn_mysql( '127.0.0.1', 'root', '', 'orders_db' )
	#info, sheets_data = rd_xlsx.read_orders( '订单.xlsx' )
	#rd_xlsx.orders_check_and_save( info, sheets_data, sql_conn )
	
	
	#	order_info = { 'id':xxxx(主id), 'auth':xxx(发件人), 'orders':[ {order_1}, {order_2} ] }
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
	'''
	order_1 = { 
		'id': '20190321-1_1',
		'type':			'test',
		'c_d_name':		'公司B',
		'company':		'B科技股份有限公司',
		'good_type':	'饮品,零食',
		'good':			'250ml酸奶',
		'num':			'10',
		'backup':		'3',
		'unit':			'250ml',
		'price':		'34.0',
		'p_note':		'',
		'r_t':			'12:00-14:00',
		't_note':		'冷链运输',
		'addr':			'xxx区xx市231号',
		'contact':		'U1,2315666777'
	}
	
	order_2 = { 
		'id': '20190321-1_2',
		'type':			'test',
		'c_d_name':		'公司C',
		'company':		'C科技股份有限公司',
		'good_type':	'整果',
		'good':			'甘肃红富士',
		'num':			'8',
		'backup':		'16',
		'unit':			'个',
		'price':		'3.0',
		'p_note':		'',
		'r_t':			'13:00-14:00',
		't_note':		'冷链运输',
		'addr':			'xxx区xx市231号',
		'contact':		'U5,231905666777'
	}
	order_info = { 'id':'20190321-1', 'auth':'free-bug@163.com', 'orders':[ order_1, order_2 ] }
	
	main_id = '20190321'
	lt_str = main_id[0:4] + '-' + main_id[4:6] + '-' + main_id[6:8]
	s_t = time.strptime( lt_str, '%Y-%m-%d' )
	order_info['t'] = time.mktime( s_t )
	
	insert_orders( '', order_info )
	
	del_orders_with_main_id( '', '20190314-' )
	
	#返回所有订单
	#print(get_day_orders_all(sql_conn, 20190325))
	#print(get_day_orders_all(sql_conn, 1553443200.0000000, fetch_type='t'))
	
	
	'''
	
	#采购汇总
	order_sum, failed = gen_purchase_table_except_fruit_cutting( sql_conn, '20190527-20190527' )
	#print( order_sum, failed )
	order_sum_cut, failed = gen_purchase_table_fruit_cutting( sql_conn, '20190527-20190602' )
	#print( order_sum_cut, failed )
	order_info = { 'm_id':'20190602', 'auth':'www', 'orders':order_sum, 'order_cut': order_sum_cut}
	wt_xlsx.gen_purchase_sum( order_info, 'wdh-cailiao-20190602.xlsx' )
	exit()
	