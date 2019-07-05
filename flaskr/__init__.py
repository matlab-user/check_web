'''
	export FLASK_APP=flaskr
	export FLASK_ENV=development
	flask run
	
	flask run --host=0.0.0.0 --port=xxxx
'''

import os, re, sys
import time, json
from flask import Flask, g, request, session, send_file, redirect, url_for, abort, send_from_directory, Markup, render_template
from werkzeug.utils import secure_filename
import logging
import logging.handlers
from . import mysql_tools, upload_orders_tool, wt_xlsx
from . import get_produce_plan, count_materials_tool
from . import add_fruit_cut_tool

# 李晓迪		12
# 霍			13

def create_app( test_config=None ):
	# create and configure the app
	app = Flask( __name__, instance_relative_config=True )
	
	if test_config is None:
		# load the instance config, if it exists, when not testing
		app.config.from_pyfile( 'config.py', silent=True )
	else:
		# load the test config if passed in
		app.config.from_mapping( test_config )

	try:
		os.makedirs( app.instance_path )
	except OSError:
		pass
	
	app.config['JSON_AS_ASCII'] = False
	
	def get_sql_conn():
		res = mysql_tools.conn_mysql( app.config['DB_IP'], app.config['DB_USER'], app.config['DB_PASSWD'], app.config['DB_NAME'], app.config['DB_PORT'], app.config['DB_CHARSET'] )
		return res
	
	logger = logging.getLogger( 'wdh' )
	logger.setLevel( logging.DEBUG )
	rh = logging.handlers.RotatingFileHandler( 'logs/wdh.log', maxBytes=800*1024*1024, backupCount=1024 )
	fm = logging.Formatter( '%(asctime)s  %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S' )
	rh.setFormatter( fm )
	logger.addHandler( rh )

	
	def allowed_file( filename ):
		ALLOWED_EXTENSIONS = set( ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif','xlsx'] )
		return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
		
		
	# a simple page that says hello
	@app.route( '/hello', methods = ['POST', 'GET'] )
	def hello():
		return 'Hello, World!</br></br>'
	
	
	@app.route( '/', methods = ['POST', 'GET'] )
	def root():
		return redirect( url_for('hello') )
	
	
	@app.route( '/main', methods = ['POST', 'GET'] )
	def main():
		return app.send_static_file( 'wdh.html' )
	
	
	@app.route( '/see_changes/<string:m_id>', methods = ['POST', 'GET'] )
	def see_changes( m_id ):
		return render_template( 'see_changes_v2.html', m_id=m_id )
		
	@app.route( '/see_changes/get_one_day_changes_orders/<string:m_id>', methods = ['POST', 'GET'] )
	def get_one_day_changed_orders( m_id ):
		sql_conn = get_sql_conn()
		del_orders, new_orders, modified_orders = mysql_tools.get_one_day_changed_orders( sql_conn, m_id )
		sql_conn.close()
		
		res = { 'del':del_orders, 'new':new_orders, 'mod':modified_orders }
		return json.dumps( res )
	
	
	# /order_list/<string:m_id>?user=xxx&passwd=xx
	@app.route( '/order_list/<string:m_id>', methods = ['GET'] )
	def order_list( m_id ):
		users_info = { 
			'wangdehui':{ 'p':'123456','uid':0 },
			'lixiaodi':{ 'p':'lixiaodi','uid':12}
		}
		
		user = request.args.get( 'user' )
		passwd = request.args.get( 'passwd' )
		
		if user in users_info and users_info[user]['p']==passwd:
			uid = users_info[user]['uid']
			auth = user
		else:
			return abort( 404 )
			
		return render_template( 'wdh_table.html', m_id=m_id, uid=uid, auth=auth )

	
	@app.route( '/order_list/get_one_day_all_orders/<string:m_id>/<int:if_all>', methods = ['GET'] )
	def get_one_day_all_orders( m_id, if_all ):
		sql_conn = get_sql_conn()
		res = mysql_tools.get_one_day_all_orders( sql_conn, m_id )
		sql_conn.close()
		
		out_res, i = [], 1
		if not if_all:
			for r in res:
				if r['state']==1:
					r['n'] = i
					del r['state']
					out_res.append( r )
					i += 1
			res = out_res
		return json.dumps( res )

		
	@app.route( '/upload', methods = ['GET', 'POST'] )
	def uploaded_file():
	
		if request.method == 'POST':
			if 'file' not in request.files:
				return 'POST请求中无文件数据'
				
			file = request.files['file']
			if file.filename == '':
				return '请选择上传文件'
				
			if file and allowed_file( file.filename ):
				filename = secure_filename( file.filename )
				save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
				file.save( save_path )
				
				t_list = upload_orders_tool.read_orders_date( save_path )
				if t_list==[]:
					return '订单时间格式错误'
				else:
					ban_t, now, failed_t = app.config['BAN_T']*3600, time.time(), []
					for t in t_list:
						if (now+ban_t)>t:
							failed_t.append( t )
					
					mid_t_str = []
					if failed_t!=[]:
						for t in failed_t:
							mid_t_str.append( wt_xlsx.utc_to_localtime_str(t,type='day') )
						return ','.join(mid_t_str) + ' 已经进入生产锁单, 需专门权限人通过订单修改功能上传'
					
				sql_conn = get_sql_conn()
				res, _ = upload_orders_tool.orders_check_and_save( save_path, sql_conn )
				if res['res']!='OK':
					res_str = '<p>错误</p>' + res['reason']
				else:
					res_str = '正确'
					
				sql_conn.close()
				return res_str
				
			else:
				return '不支持的文件格式'
			
		return '请使用POST方法上传文件'
		
	
	@app.route( '/get_produce_plan/<string:t_range>', methods = ['GET'] )
	def production_plan( t_range ):
		if get_produce_plan.get_t_list( t_range )==[]:
			return '时间输入格式错误'
		file_name = t_range + '_orders.xlsx'
		save_path = os.path.join( app.config['TEMP_FOLDER'], file_name )
		sql_conn = get_sql_conn()
		get_produce_plan.gen_production_plan_v2( sql_conn, save_path, t_range )
		sql_conn.close()
		return send_file( '../'+save_path, as_attachment=True, attachment_filename=file_name )

	
	@app.route( '/download_goods/', methods = ['GET'] )
	def download_goods():
		file_name = 'goods_list.xlsx'
		save_path = os.path.join( app.config['TEMP_FOLDER'], file_name )
		try:
			os.remove( save_path )
		except:
			pass
			
		sql_conn = get_sql_conn()
		res = mysql_tools.get_goods_list( sql_conn )
		com_res = mysql_tools.get_companys( sql_conn )
		sql_conn.close()
		
		get_produce_plan.gen_goods_list( save_path, res, com_res )
		return send_file( '../'+save_path, as_attachment=True, attachment_filename=file_name )
	
	
	@app.route( '/add_g1/<string:g_str>', methods = ['GET'] )
	def add_g1( g_str ):
		# 类型-产品名称-单位
		try:
			type, name, unit = g_str.split( '-' )
		except:
			return '录入格式错误'
		good_info = [ {'type':type,'name':name,'origin':'','unit':unit,'d_unit':'','price':0,'info':'','note':'','standar':''} ]
		sql_conn = get_sql_conn()
		res, reason = mysql_tools.check_and_save_goods_info( sql_conn, good_info, '' )
		sql_conn.close()
		if reason!='':
			return reason
		else:
			return '录入产品成功'
	
	
	@app.route( '/get_mlist/<string:t_range>', methods = ['GET'] )
	def get_mlist( t_range ):
		if get_produce_plan.get_t_list( t_range )==[]:
			return '时间输入格式错误'

		file_name = t_range + '_materials.xlsx'
		save_path = os.path.join( app.config['TEMP_FOLDER'], file_name )
		sql_conn = get_sql_conn()
		count_materials_tool.get_marterials_data( sql_conn, t_range, save_path )
		sql_conn.close()
		return send_file( '../'+save_path, as_attachment=True, attachment_filename=file_name )
	
	
	@app.route( '/get_shipping/<string:date_str>', methods = ['GET'] )
	def get_shipping( date_str ):
		file_name = date_str + '_shipping.xlsx'
		save_path = os.path.join( app.config['TEMP_FOLDER'], file_name )
		sql_conn = get_sql_conn()
		orders = mysql_tools.get_day_orders_all( sql_conn, date_str, fetch_type='m_id' )
		sql_conn.close()
		
		order_info = { 'm_id':date_str, 'auth':'wangdehi', 'orders':orders }
		wt_xlsx.gen_invoice_v3( order_info, save_path )
		
		return send_file( '../'+save_path, as_attachment=True, attachment_filename=file_name )
	
	
	@app.route( '/add_fruit_cut/<string:name>/<string:info>/<string:note>', methods = ['GET'] )
	def add_fruit_cut( name, info, note ):
		cut_info = { 'name':name, 'info':info, 'note':note }
		sql_conn = get_sql_conn()
		res = add_fruit_cut_tool.add_fruit_cut( sql_conn, cut_info )
		sql_conn.close()
		if res['res']=='OK':
			res = '添加果切 %s 成功' % name
		else:
			res = '添加果切 %s 失败。%s' %( name, res['reason'] )
		return res
	
	
	@app.route( '/add_fruit_cut_new/<string:name>/<string:info>', methods = ['GET'] )
	def add_fruit_cut_new( name, info ):
		cut_info = { 'name':name, 'info':info }
		sql_conn = get_sql_conn()
		res = add_fruit_cut_tool.add_fruit_cut_new( sql_conn, cut_info )
		sql_conn.close()
		if res['res']=='OK':
			res = '添加果切 %s 成功' % name
		else:
			res = '添加果切 %s 失败。%s' %( name, res['reason'] )
		return res
		
	
	@app.route( '/add_new_order', methods = ['POST'] )
	def add_new_order():
		if request.method == 'POST':
			if 'file' not in request.files:
				return 'POST请求中无文件数据'
				
			file = request.files['file']
			if file.filename == '':
				return '请选择上传文件'
				
			if file and allowed_file( file.filename ):
				filename = secure_filename( file.filename )
				save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
				file.save( save_path )
				
			sql_conn = get_sql_conn()
			res = upload_orders_tool.add_new_orders( save_path, sql_conn )
			sql_conn.close()
			if res['res']=='OK':
				return '添加新订单成功'
			else:
				return '添加新订单失败'
	
	
	@app.route( '/add_new_order_from_web', methods = ['GET', 'POST'] )
	def add_new_order_from_web():
		'''
		row = { 'id':1, 'type':'w1', 'sub_type':'w2', 'c_d_name':'网易', 'good':'进口柠檬', 'unit':'个', 'num':3,
			'backup':1, 'price':2.0, 'p_note':'wangdehui', 'r_t':'11:00-12:00', 't_note':'xiezhimei', 'pack_note':'p1', 'tools':'new' }
		row = { 'id':1, 'type':'w1', 'sub_type':'w2', 'c_d_name':'网易', 'good':'二分格（果切草莓+果切木瓜）', 'unit':'个', 'num':3,
			'backup':1, 'price':2.0, 'p_note':'wangdehui', 'r_t':'11:00-12:00', 't_note':'xiezhimei', 'pack_note':'p1', 'tools':'new' }
		
		row = { 'n':xx, 'm_id':xx, 'id':'20190527_21_1', 'type':'w1', 'sub_type':'w2', 'c_d_name':'网易', 'good':'二分格（果切草莓+果切木瓜）', 'unit':'个', 'num':3,
			'backup':1, 'price':2.0, 'p_note':'wangdehui', 'r_t':'11:00-12:00', 't_note':'xiezhimei', 'pack_note':'p1', 'tools':'change' }
		order_info = { 'name':'sheet-wdh', 'main_id':'20190101', 'auth':'www', 'data':row }
		'''
		if request.method == 'POST':
			row = dict( request.form )
		
		order_info = { 'name':'sheet-wdh', 'main_id':row['m_id'], 'auth':'x_one', 'data':[row] }
		
		sql_conn = get_sql_conn()
		res = upload_orders_tool.add_change_order_from_web( sql_conn, order_info )
		sql_conn.close()

		return json.dumps( res )
	
	
	# post data - { m_id, id, type, sub_type, c_d_name, good, unit, num, backup, price, p_note, r_t, t_note, pack_note, tools(way) }
	@app.route( '/change_the_order_from_web/<string:orig_id>', methods = ['GET', 'POST'] )
	def change_the_order( orig_id ):
		if request.method == 'POST':
			row = dict( request.form )
	
		order_info = { 'auth':row['auth'], 'main_id':row['m_id'], 'data':[row] }	

		# order_info - { 'name':xx, 'main_id':xx, 'data':[Row] }						
		# Row - { id, type, sub_type, c_d_name, good, unit, num, backup, price, p_note, r_t, t_note, pack_note, tools(way) }
		# 此时 id 为 uid
		sql_conn = get_sql_conn()
		res = upload_orders_tool.add_change_order_from_web( sql_conn, order_info )
		sql_conn.close()
		return json.dumps( res )
	
	
	@app.route( '/del_the_order/<string:order_id>', methods = ['GET'] )
	def del_the_order( order_id ):
		sql_conn = get_sql_conn()
		res = mysql_tools.del_the_order( sql_conn, order_id, 2 )
		sql_conn.close()
		return json.dumps( res )
	
	
	@app.route( '/change_order', methods = ['POST'] )
	def change_order():
		if request.method == 'POST':
			if 'file' not in request.files:
				return 'POST请求中无文件数据'
				
			file = request.files['file']
			if file.filename == '':
				return '请选择上传文件'
				
			if file and allowed_file( file.filename ):
				filename = secure_filename( file.filename )
				save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
				file.save( save_path )
				
		sql_conn = get_sql_conn()		
		res = upload_orders_tool.change_orders( save_path, sql_conn )
		sql_conn.close()
		if res['res']=='OK':
			return '添加新订单成功'
		else:
			return '添加新订单失败'
	
	
	# com_info: 公司名称-联系人-手机号
	# com_addr: 省-市-区-地址
	@app.route( '/add_com/<string:com_info>/<string:com_addr>', methods = ['GET'] )
	def add_com( com_info, com_addr):
		com_info_list = com_info.split( '-' )
		com_addr_list = com_addr.split( '-' )
		if len(com_addr_list)<3 or len(com_addr_list)<4:
			res = '信息输入不正确'
		else:
			sql_conn = get_sql_conn()
			res = mysql_tools.add_com( sql_conn, com_info_list, com_addr_list )
			sql_conn.close()
			if res['res']=='OK':
				res = '添加成功'
			else:
				res = res['reason']
		return res
	
	
	return app