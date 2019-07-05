from . import mysql_tools
import os, sys
import time, re
import json


# cut_info - { 'name':xx, 'info':组成和出成信息, 'note':重量-种类 }
# 覆盖重名品
# 补全后的信息: name, type, unit, d_unit, info, state, note, c_t, price
def add_fruit_cut( sql_conn, cut_info ):
	try:
		w, n = cut_info['note'].split( '-' )
	except:
		return { 'res':'NO', 'reason':'note字段格式错误.应为 weight-num' }
	
	mid, p = {}, re.compile( r'[，,]' )
	cells = p.split( cut_info['info'] )
	p = re.compile( r'(\S+)[:：][ ]*(\d+(\.\d+)?)' )
	for c in cells:
		m = p.match( c )
		if m:
			mid[ m.group(1) ] = m.group(2)
		else:
			return { 'res':'NO', 'reason':'%s 格式错误' %c }
	cut_info['info'] = json.dumps( mid )
	
	cur = sql_conn.cursor()
	sql_str = 'DELETE FROM ord_goods WHERE name=%s'
	cur.execute( sql_str, [ cut_info['name'] ] )
	sql_conn.commit()
	
	c_t = time.time()
	sql_str = 'INSERT INTO ord_goods ( type, name, unit, d_unit, price, info, state, c_t, note) VALUES ("果切",%s,"个","盒",0,%s,1,%s,%s)'
	cur.execute( sql_str, (cut_info['name'], cut_info['info'], c_t, cut_info['note']) )
	sql_conn.commit()
	
	cur.close()
	
	return { 'res':'OK' }


def add_fruit_cut_new( sql_conn, cut_info ):
	mid, p = {}, re.compile( r'[，,]' )
	cells = p.split( cut_info['info'] )
	p = re.compile( r'(\S+)[:：][ ]*(\d+(\.\d+)?)' )
	for c in cells:
		m = p.match( c )
		if m:
			mid[ m.group(1) ] = m.group(2)
		else:
			return { 'res':'NO', 'reason':'%s 格式错误' %c }
	cut_info['info'] = mid
	
	cur = sql_conn.cursor()
	sql_str = 'SELECT info FROM ord_goods WHERE name=%s'
	cur.execute( sql_str, ( cut_info['name'], ) )
	res = cur.fetchone()
	if res is not None:
		info = json.loads( res[0] )
	else:
		return { 'res':'NO', 'reason':'%s 不存在' %cut_info['name'] }
	
	for k, v in cut_info['info'].items():
		info[k] = v

	info = json.dumps( info )
	
	sql_str = 'UPDATE ord_goods SET info=%s WHERE name=%s'
	cur.execute( sql_str, (info, cut_info['name']) )
	sql_conn.commit()
	cur.close()
	
	return { 'res':'OK' }
	

if __name__=='__main__':

	db_ip = '127.0.0.1'
	db_user = 'blue'
	db_passwd = 'blue'
	db_name = 'orders_db'
	db_port = 3306
	db_charset = 'utf8'
	
	cut_info = { 'name':'wdh-cut', 'info':'w:0.5,h:0.9,f:0.7', 'note':'101-2' }
	sql_conn = mysql_tools.conn_mysql( db_ip, db_user, db_passwd, db_name, db_port, db_charset )
	res = add_fruit_cut( sql_conn, cut_info )
	print( res )