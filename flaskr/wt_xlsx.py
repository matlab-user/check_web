#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xlsxwriter
import time, json
import os, hashlib
import xlrd, sys


# type - 'day', 'full'
def utc_to_localtime_str( utc_t, type='full' ):
	lt = time.localtime( utc_t )
	f = '%Y-%m-%d'
	if type=='full':
		f += ' %H:%M:%S'
	res = time.strftime( f, lt )
	return res
	
	
def localtime_str_to_utc( lt_str ):
	f = '%Y-%m-%d %H:%M:%S'
	s_t = time.strptime( lt_str, f )
	res = time.mktime( s_t )
	return res
	

def gen_production_plan_header( sheet, order_code, auth, cell_format ):
	sheet.set_column( 'A:C', 20 )
	sheet.set_column( 'D:E', 40 )
	sheet.set_column( 'F:F', 30 )
	sheet.set_column( 'G:H', 30 )
	sheet.set_column( 'I:I', 10 )
	sheet.set_column( 'J:J', 50 )
	sheet.set_column( 'K:K', 15 )
	sheet.set_column( 'L:T', 50 )
	sheet.set_column( 'U:U', 60 )
	
	sheet.write( 'A1', order_code, cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'F1', auth, cell_format )
	
	sheet.write( 'A3', '序号', cell_format )
	sheet.write( 'B3', '订单类型', cell_format )
	sheet.write( 'C3', '订单子类型', cell_format )
	sheet.write( 'D3', '公司名称', cell_format )
	sheet.write( 'E3', '开票名称', cell_format )
	sheet.write( 'F3', '类别', cell_format )
	sheet.write( 'G3', '产品名称', cell_format )
	sheet.write( 'H3', '单位', cell_format )
	sheet.write( 'I3', '数量', cell_format )
	sheet.write( 'J3', '备份数量', cell_format )
	sheet.write( 'K3', '规格', cell_format )
	sheet.write( 'L3', '单价(元)', cell_format )
	sheet.write( 'M3', '生产备注', cell_format )
	sheet.write( 'N3', '要求送达时间', cell_format )
	sheet.write( 'O3', '物流备注', cell_format )
	sheet.write( 'P3', '公司地址/联系人', cell_format )
	sheet.write( 'Q3', '联系人', cell_format )
		
	sheet.write( 'R3', '司机', cell_format )
	sheet.write( 'S3', '发车时间', cell_format )
	sheet.write( 'T3', '实际收货数量', cell_format )
	sheet.write( 'U3', '实际收货时间', cell_format )
	
	
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
def gen_production_plan( order_info, out_file_name ):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'center',
		'valign': 'vcenter',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	gen_production_plan_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
	
	###########################
	
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
		#worksheet.set_row( row, 16 )
		for i, k in enumerate( keys_list ):
			if k == 'unit':
				u = json.loads( od[k] )
				if u['info'] != '':
					s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
				else:
					s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
				worksheet.write( row, i, s )
				data += s
			else:
				worksheet.write( row, i, od[k] )
				data += str( od[k] )
		row += 1
	
	#合并单元格处理
	num = row+1	#记录合并行的首行索引
	for ary_ix in ary:
		for ay in array:
			if ay['pack_note'] == ary_ix:
				#worksheet.set_row( row, 15 )
				for i, k in enumerate( keys_list ):
					if k == 'unit':
						u = json.loads( ay[k] )
						if u['info'] != '':
							s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
						else:
							s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
						worksheet.write( row, i, s )
						data += s
					else:
						worksheet.write( row, i, ay[k] )
						data += str( ay[k] )
					if ay['p_note'] != '':
						remark = ay['p_note']
				row += 1
		param_str = str('M') + str(num) + ':' + str('M') + str(row)
		worksheet.merge_range(param_str, remark, cell_format)
		worksheet.write_rich_string(str('M') + str(num), remark, cell_format)
		num = row + 1
		
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'U1', md5 )
	
	workbook.close()
	

#物流上传 返回附件
def get_logistics_order(order_info, out_file_name):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'center',
		'valign': 'vcenter',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	gen_production_plan_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
	keys_list = [ 'id', 'type', 'sub_type', 'c_d_name', 'company', 'good_type', 'good', 'standar', 'num', 'backup', 'unit', 'price', 'p_note', 'r_t', 't_note', 'addr', 'contact','driver','d_t','actual_recv','a_t' ]
	
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
	
	
	row, data = 3, ''
	#未合并单元格处理
	for od in lt_ary:
		#worksheet.set_row( row, 16 )
		for i, k in enumerate( keys_list ):
			if k == 'unit':
				u = json.loads( od[k] )
				if u['info'] != '':
					s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
				else:
					s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
				worksheet.write( row, i, s )
				data += s
			else:
				worksheet.write( row, i, od[k] )
				data += str( od[k] )
		row += 1
	
	#合并单元格处理
	num = row+1	#记录合并行的首行索引
	for ary_ix in ary:
		for ay in array:
			if ay['pack_note'] == ary_ix:
				#worksheet.set_row( row, 15 )
				for i, k in enumerate( keys_list ):
					if k == 'unit':
						u = json.loads( ay[k] )
						if u['info'] != '':
							s = str('u:') + str(u['u']) + ',' + str('info:') + str(json.loads(u['info'])) + ',' + str('d_unit:') + str(u['d_unit'])
						else:
							s = str('u:') + str(u['u']) + ',' + str('info:') + str('') + ',' + str('d_unit:') + str(u['d_unit'])
						worksheet.write( row, i, s )
						data += s
					else:
						worksheet.write( row, i, ay[k] )
						data += str( ay[k] )
					if ay['p_note'] != '':
						remark = ay['p_note']
				row += 1
		param_str = str('M') + str(num) + ':' + str('M') + str(row)
		worksheet.merge_range(param_str, remark, cell_format)
		worksheet.write_rich_string(str('M') + str(num), remark, cell_format)
		num = row + 1
		
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'U1', md5 )
	
	workbook.close()
	

def get_purchase_sum_header(sheet, order_code, auth, cell_format):
	sheet.set_column( 'A:A', 15 )
	sheet.set_column( 'B:B', 15 )
	sheet.set_column( 'C:D', 30 )
	sheet.set_column( 'E:F', 20 )
	sheet.set_column( 'G:K', 40 )
	
	sheet.write( 'A1', order_code, cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'F1', auth, cell_format )
	'''
	sheet.write( 'A3', '品类', cell_format )
	sheet.write( 'B3', '商品名称', cell_format )
	sheet.write( 'C3', '产品计量单位表示的数值', cell_format )
	sheet.write( 'D3', '当前参考单格', cell_format )
	sheet.write( 'E3', '总价', cell_format )
	sheet.write( 'F3', '总数量', cell_format )
	'''
	sheet.write( 'A3', '类型', cell_format )
	sheet.write( 'B3', '产品名称', cell_format )
	sheet.write( 'C3', '规格（产品计量单位）', cell_format )
	sheet.write( 'D3', '需要数量', cell_format )

	
def get_purchase_sum_header2(sheet, order_code, auth, cell_format):
	sheet.set_column( 'A:A', 15 )
	sheet.set_column( 'B:B', 15 )
	sheet.set_column( 'C:D', 30 )
	sheet.set_column( 'E:F', 20 )
	sheet.set_column( 'G:K', 40 )
	
	sheet.write( 'A1', order_code, cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'F1', auth, cell_format )

	sheet.write( 'A3', '类型', cell_format )
	sheet.write( 'B3', '产品名称', cell_format )
	sheet.write( 'C3', '规格（产品计量单位）', cell_format )
	sheet.write( 'D3', '需要数量', cell_format )
	
	
# order_info = { 'm_id':xxxx, 'auth':xxx, 'orders':{ {order_1}, {order_2} } }
# order_x - dict 类型
#	type: 		订单类型，		
#	good:		产品名称，		
#	num:		数量，			
#	unit:		规格
#	val:		产品计量单位表示的数值
#	price:		单价
#	s_price:	总价
#	n:			总数量（数量+备份数量）
#	sum:		汇总的数量
def gen_purchase_sum( order_info, out_file_name ):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet( '零食糕点整果饮品' )
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	get_purchase_sum_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
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
	get_purchase_sum_header2( worksheet, order_info['m_id'], order_info['auth'], cell_format )
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

	workbook.close()

	
	
#三联单数据封装
def get_logistics_order_form(orders):
	ary = []
	for name in orders['orders']:
		ary.append(name['c_d_name'])
	ary = set(ary)#去重
	res_ary = []
	for ay in ary:
		list_ary = []
		for od in orders['orders']:
			if ay == od['c_d_name']:
				list_ary.append(od)
		res_ary.append(list_ary)
	return res_ary


# orders_list - [ [{key:value}公司A的所有订单], [公司B的所有订单],... ]
def gen_invoice_v2( orders, save_path ):
	orders_list = get_logistics_order_form( orders )
	book = xlsxwriter.Workbook( save_path )
	
	property = {
		'align':'right',
		'font_name': u'微软雅黑',
	}
	cell_format_r = book.add_format( property )
	
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = book.add_format( property )
	
	property = {
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format_n = book.add_format( property )	
	'''
	for orders in orders_list:
		sheet = book.add_worksheet( orders[0]['c_d_name'] )
		sheet_header( sheet, orders[0], cell_format_r, cell_format )
		write_to_sheet( sheet, orders, cell_format_n, cell_format )
	'''
	
	sheet = book.add_worksheet( 'Sheet1' )
	num = 0;
	for orders in orders_list:
		'''
		sheet_header( sheet, orders[0], cell_format_r, cell_format, num )
		sheet, row = write_to_sheet( sheet, orders, cell_format_n, cell_format, num )
		'''
		sheet_header( sheet, orders, cell_format_r, cell_format, num )
		sheet, row = write_to_sheet( sheet, orders, cell_format_n, cell_format, num )
		num = row
	
	
	book.close()


# orders_list - [ [{key:value}公司A的所有订单], [公司B的所有订单],... ]
# 三联单，一页容纳 19 行
def gen_invoice_v3( orders, save_path ):
	orders_list = get_logistics_order_form( orders )
	book = xlsxwriter.Workbook( save_path )
	
	property = {
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format_r = book.add_format( property )

	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
		'top': 2,
		'bottom':2,
	}
	cell_format = book.add_format( property )
	cell_format.set_border_color( '#000000' )
	
	property = {
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format_n = book.add_format( property )	
	
	date_format = book.add_format( {'num_format': 'hh:mm'} )
	
	sheet = book.add_worksheet( 'Sheet1' )
	# 每19行一张单子
	num = 0;
	for orders in orders_list:
		if num % 19 >0:
			num = ( num // 19 + 1 ) * 19
		sheet_header( sheet, orders, cell_format_r, cell_format, num, date_format=date_format )
		sheet, row = write_to_sheet_v3( sheet, orders, book, num )
		num = row - 1
	
	for i in range( num ):
		sheet.set_row( i, 17 )
	book.close()

		
def sheet_header( sheet, orders, cell_format_r, cell_format, num, date_format=None ):
	for od in orders:
		sheet.set_column( 'A:A', 12 )
		sheet.set_column( 'B:B', 30 )
		sheet.set_column( 'G:G', 15 )
		sheet.write( str('A')+str(num+1), '公司名称:', cell_format_r )
		sheet.write( str('B')+str(num+1), od['c_d_name'],cell_format_r )
		sheet.write( str('A')+str(num+2), '收货人:', cell_format_r )
		sheet.write( str('B')+str(num+2), od['contact'], cell_format_r )
		sheet.write( str('A')+str(num+3), '送达时间:', cell_format_r )
		if od['r_t'][0:2]=='0.' and date_format is not None:
			sheet.write( str('B')+str(num+3), float(od['r_t']), date_format )
		else:
			sheet.write( str('B')+str(num+3), od['r_t'], cell_format_r )
		sheet.write( str('A')+str(num+4), '地址:', cell_format_r )
		sheet.write( str('B')+str(num+4), od['addr'], cell_format_r )
		sheet.insert_image( str('G')+str(num+1), './logo.png' )
		
		sheet.write( str('A')+str(num+7), '序号', cell_format )
		sheet.write( str('B')+str(num+7), '产品名称', cell_format )
		sheet.write( str('C')+str(num+7), '单价(元)', cell_format )
		sheet.write( str('D')+str(num+7), '数量', cell_format )
		sheet.write( str('E')+str(num+7), '备份数量', cell_format )
		sheet.write( str('F')+str(num+7), '价格(元)', cell_format )
		sheet.write( str('G')+str(num+7), '优惠', cell_format)
		sheet.write( str('H')+str(num+7), '小计(元)', cell_format )
		return sheet


def write_to_sheet( sheet, orders, cell_format_n, cell_format, num ):
	row, sum_p = 7, 0
	number = 0
	if num != 0:
		row = (num + row)
	for one in orders:
		number += 1
		sheet.write( row, 0, number, cell_format_n )
		sheet.write( row, 1, one['good'], cell_format_n )
		sheet.write( row, 2, one['price'], cell_format_n )
		sheet.write( row, 3, one['num'], cell_format_n )
		sheet.write( row, 4, one['backup'], cell_format_n )
		p = float(one['price']) * ( float(one['num'])+float(one['backup']) )
		sum_p += p
		sheet.write( row, 5, p, cell_format_n )
		sheet.write( row, 7, p, cell_format_n )
		row += 1
	
	sheet.write( row, 6, '订单总金额:', cell_format )
	sheet.write( row, 7, sum_p, cell_format )
	
	for i in range(8):
		sheet.write( row+4, i, '', cell_format )
		
	sheet.write( row+4, 3, '发票验收:', cell_format )
	sheet.write( row+4, 6, '收货人签字:', cell_format )

	row += 8

	return sheet, row


def write_to_sheet_v3( sheet, orders, book, num ):
	row, sum_p = 7, 0
	number = 0
	if num != 0:
		row = (num + row)
		
	# top_bottom
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
		'top': 2,
		'bottom':2,
	}
	top_bottom = book.add_format( property )
	
	# bottom
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
		'bottom':2,
	}
	bottom = book.add_format( property )
	
	# bold
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	bold = book.add_format( property )
	
	property = {
		'align':'left',
		'font_name': u'微软雅黑',
	}
	norm = book.add_format( property )
	
	for one in orders:
		number += 1
		sheet.write( row, 0, number, norm )
		sheet.write( row, 1, one['good'], norm )
		sheet.write( row, 2, one['price'], norm )
		sheet.write( row, 3, one['num'], norm )
		sheet.write( row, 4, one['backup'], norm )
		p = float(one['price']) * ( float(one['num'])+float(one['backup']) )
		sum_p += p
		sheet.write( row, 5, p, norm )
		sheet.write( row, 7, p, norm )
		row += 1
	
	sheet.write( row, 6, '订单总金额:', bold )
	sheet.write( row, 7, sum_p, bold )
	
	for i in range(8):
		sheet.write( row+4, i, '', bottom )
		
	sheet.write( row+4, 3, '发票验收:', bottom )
	sheet.write( row+4, 6, '收货人签字:', bottom )
	
	row += 8

	return sheet, row

	
#财务订单金额 （格式：订单金额 20190101-20190110）
#	company			公司发票名称
#	sum_price		总金额（订单输入价格 * 数量）
def gen_finance_summary(order_info, out_file_name):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	get_finance_summary_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )

	keys_list = [ 'company', 'sum_price' ]
	row, data = 3, ''
	for order in order_info['orders']:
		worksheet.set_row( row, 2 )
		for i, k in enumerate( keys_list ):
			worksheet.write( row, i, order[k] )
			data += str( order[k] )
		row += 1
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'G1', md5 )
	
	workbook.close()


def get_finance_summary_header( sheet, startEndTIme, auth, cell_format ):
	sheet.set_column( 'A:A', 40 )
	sheet.set_column( 'B:B', 30 )
	sheet.set_column( 'C:C', 15 )
	sheet.set_column( 'D:D', 30 )
	sheet.set_column( 'E:E', 5 )
	sheet.set_column( 'F:F', 40 )
	sheet.set_column( 'G:G', 40 )
	
	sheet.write( 'A1', startEndTIme, cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'F1', auth, cell_format )

	sheet.write( 'A3', '公司发票名称', cell_format )
	sheet.write( 'B3', '订单总额', cell_format )
	
	
#财务订单详情 （格式：订单详情 20190101-20190110）
#	id				订单全id（20190315-录入人id_x）
#	c_d_name		公司显示名称
#	company			公司发票名称
#	good			商品名称
#	type			订单类型
#	sub_type		订单子类型
#	good_type		商品种类
#	price			订单输入价格，单位：元
#	num				数量
#	backup			备份数量
#	actual_recv		客户实际接收数量
#	sum_price		总金额（客户实际接收数量 * 订单输入价格）
def gen_apply_orders_invoice(order_info, out_file_name):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )	
	get_apply_orders_invoice_header( worksheet, order_info['m_id'], order_info['auth'], cell_format )
		
	keys_list = [ 'id', 'c_d_name', 'company', 'good', 'type', 'sub_type', 'good_type', 'standar', 'price', 'num', 'backup', 'actual_recv', 'sum_price' ]
	row, data = 3, ''
	for order in order_info['orders']:
		#worksheet.set_row( row, 13 )
		for i, k in enumerate( keys_list ):
			#worksheet.write( row, i, order[k] )
			if order[k] == None:
				worksheet.write( row, i, 0 )
			else:
				worksheet.write( row, i, order[k] )
			data += str( order[k] )
		row += 1
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'L1', md5 )
	
	workbook.close()
	

def get_apply_orders_invoice_header( sheet, startEndTIme, auth, cell_format ):
	sheet.set_column( 'A:A', 15 )
	sheet.set_column( 'B:B', 30 )
	sheet.set_column( 'C:F', 30 )
	sheet.set_column( 'G:N', 15 )
	sheet.set_column( 'H:H', 30 )
	sheet.set_column( 'I:K', 15 )
	sheet.set_column( 'L:L', 30 )
	sheet.set_column( 'M:N', 15 )
	
	sheet.write( 'A1', startEndTIme, cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'E1', '申请者：' )
	sheet.write( 'F1', auth, cell_format )
	sheet.write( 'G1', '接收者：' )

	sheet.write( 'A3', '订单编号', cell_format )
	sheet.write( 'B3', '公司显示名称', cell_format )
	sheet.write( 'C3', '公司发票名称', cell_format )
	sheet.write( 'D3', '商品名称', cell_format )
	sheet.write( 'E3', '订单类型', cell_format )
	sheet.write( 'F3', '订单子类型', cell_format )
	sheet.write( 'G3', '商品种类', cell_format )
	sheet.write( 'H3', '单位', cell_format )
	sheet.write( 'I3', '订单输入价格', cell_format )
	sheet.write( 'J3', '下单数量', cell_format )
	sheet.write( 'K3', '备份数量', cell_format )
	sheet.write( 'L3', '实际签收数量', cell_format )
	sheet.write( 'M3', '总价格（单价*实际签收数量）', cell_format )
	sheet.write( 'N3', '开票', cell_format )
	
	
#运营提交申请开票成功后，按照时间段查询申请开票的数据，发送给财务	
def gen_apply_invoice_send_out( ord_info, out_file_name ):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )
	get_apply_invoice_send_out_header( worksheet, ord_info['auth'], cell_format )
		
	keys_list = [ 'id', 'c_d_name', 'company', 'good', 'type', 'sub_type', 'good_type', 'standar', 'price', 'num', 'backup', 'actual_recv', 'sum_price', 'state', 'o_note' ]
	row, data = 3, ''
	for order in ord_info['orders']:
		#worksheet.set_row( row, 15 )
		for i, k in enumerate( keys_list ):
			if k == 'state' and order[k] == 7:
				worksheet.write( row, i, '申请开票' )
			else:
				worksheet.write( row, i, order[k] )
			data += str( order[k] )
		row += 1
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet.write( 'O1', md5 )
	
	
	worksheet2 = workbook.add_worksheet('开票抬头')
	cell_format2 = workbook.add_format( property )
	get_apply_invoice_send_out_header2( worksheet2, ord_info['auth'], cell_format2 )
	keys_list2 = [ 'company', 'price' ]
	row2, data2 = 0, ''
	for od in ord_info['auth']['sheet'][0]:
		#worksheet2.set_row( row2, 2 )
		for i, k in enumerate( keys_list2 ):
			worksheet2.write( row2, i, od[k] )
			data2 += str(od[k])
		row2 += 1
	hash_md5 = hashlib.md5( data.encode('utf-8') )
	md5 = hash_md5.hexdigest()
	worksheet2.write( 'E1', md5 )
	
	workbook.close()

	
def get_apply_invoice_send_out_header( sheet, auth, cell_format ):
	sheet.set_column( 'A:A', 15 )
	sheet.set_column( 'B:B', 30 )
	sheet.set_column( 'C:F', 30 )
	sheet.set_column( 'G:G', 15 )
	sheet.set_column( 'H:H', 30 )
	sheet.set_column( 'I:N', 15 )
	sheet.set_column( 'O:O', 40 )
	
	sheet.write( 'A1', auth['sn_time'], cell_format )
	sheet.write( 'C1', '导出时间:' )
	
	export_t_str = utc_to_localtime_str( time.time() )
	sheet.write( 'D1', export_t_str )
	sheet.write( 'E1', '申请者：' )
	sheet.write( 'F1', auth['m_mail'], cell_format )
	sheet.write( 'G1', '接收者：' )
	sheet.write( 'H1', auth['u_mail'], cell_format )

	sheet.write( 'A3', '订单编号', cell_format )
	sheet.write( 'B3', '公司显示名称', cell_format )
	sheet.write( 'C3', '公司发票名称', cell_format )
	sheet.write( 'D3', '商品名称', cell_format )
	sheet.write( 'E3', '订单类型', cell_format )
	sheet.write( 'F3', '订单子类型', cell_format )
	sheet.write( 'G3', '商品种类', cell_format )
	sheet.write( 'H3', '单位', cell_format )
	sheet.write( 'I3', '订单输入价格', cell_format )
	sheet.write( 'J3', '下单数量', cell_format )
	sheet.write( 'K3', '备份数量', cell_format )
	sheet.write( 'L3', '实际签收数量', cell_format )
	sheet.write( 'M3', '总价格（单价*实际签收数量）', cell_format )
	sheet.write( 'N3', '开票', cell_format )
	sheet.write( 'O3', '详情', cell_format )	

	
def get_apply_invoice_send_out_header2(sheet, auth, cell_format):
	sheet.set_column( 'A:A', 40 )
	sheet.set_column( 'B:B', 20 )
	
	sheet.write( 'A1', '公司发票抬头', cell_format )
	sheet.write( 'B1', '开票金额',cell_format )

	
#下载订单模板
def gen_down_order_model(uid, send, out_file_name):
	workbook = xlsxwriter.Workbook( out_file_name )
	worksheet = workbook.add_worksheet()
	property = {
		'bold':True,
		'align':'left',
		'font_name': u'微软雅黑',
	}
	cell_format = workbook.add_format( property )
	
	worksheet.set_column( 'A:C', 20 )
	worksheet.set_column( 'D:E', 40 )
	worksheet.set_column( 'F:I', 15 )
	worksheet.set_column( 'J:J', 30 )
	worksheet.set_column( 'K:K', 20 )
	worksheet.set_column( 'L:L', 30 )
	
	worksheet.write( 'B1', uid, cell_format )
	worksheet.write( 'C1', send, cell_format )
	
	worksheet.write( 'A3', '序号', cell_format )
	worksheet.write( 'B3', '订单类型', cell_format )
	worksheet.write( 'C3', '订单子类型', cell_format )
	worksheet.write( 'D3', '公司名称', cell_format )
	worksheet.write( 'E3', '产品名称', cell_format )
	worksheet.write( 'F3', '单位', cell_format )
	worksheet.write( 'G3', '数量', cell_format )
	worksheet.write( 'H3', '备份数量', cell_format )
	worksheet.write( 'I3', '单价(元)', cell_format )
	worksheet.write( 'J3', '生产备注', cell_format )
	worksheet.write( 'K3', '要求送达时间', cell_format )
	worksheet.write( 'L3', '物流备注', cell_format )
	
	workbook.close()
	
	
	
if __name__=='__main__':
	'''
	utc = time.time()
	res = utc_to_localtime_str( utc )
	utc_2 = localtime_str_to_utc( res )
	'''
	
	order_info = {
		'id': '20190330',
		'auth':'free-bug@163.com',
		'orders': [
			{	'id': 1,
				'type': 'test',
				'c_d_name': 'com_A',
				'company':	'bill_com_A',
				'good_type': '饮品',
				'good': '500ml快乐神仙水',
				'num': 12,
				'backup':3,
				'unit':'个',
				'price':3.00,
				'p_note':'不用清洗',
				'r_t':'12:00-13:00',
				't_note':'全程4摄氏度运输',
				'addr':'某区某号楼124室',
				'contact':'wdh,123455778788'
			},
			
			{	'id': 2,
				'type': 'test',
				'c_d_name': 'com_A',
				'company':	'bill_com_A',
				'good_type': '糕点',
				'good': '250g甜面包',
				'num': 120,
				'backup':20,
				'unit':'个',
				'price':5.00,
				'p_note':'多加酵母',
				'r_t':'13:00-14:00',
				't_note':'全程冷链运输',
				'addr':'某区某号楼412室',
				'contact':'wdh3,123455778788'
			},
			{	'id': 3,
				'type': 'test',
				'c_d_name': 'com_B',
				'company':	'bill_com_A',
				'good_type': '糕点',
				'good': '250g甜面包',
				'num': 120,
				'backup':20,
				'unit':'个',
				'price':5.00,
				'p_note':'多加酵母',
				'r_t':'13:00-14:00',
				't_note':'全程冷链运输',
				'addr':'某区某号楼412室',
				'contact':'wdh3,123455778788'
			}
		]
	}
	#gen_invoice( order_info, 'test.xlsx' )
	gen_invoice_v2( order_info, 'invoice_v2.xlsx' )


