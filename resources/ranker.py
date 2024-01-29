from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error

import boto3

from config import Config
from mysql_connection import get_connection


class RankerResource(Resource):
    # 상위 랭커 20명 프로필 이미지 가져오기
    jwt_required()
    def get(self) :
        try :
            userId = get_jwt_identity()

            connection = get_connection()
            
            query = '''select u.id, u.nickname, u.profileUrl, l.level
                        from user u
                        join level l
                        on u.id = l.userId
                        order by l.level desc
                        limit 20;'''
            
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            result_list = cursor.fetchall()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"result": "fail", "error": str(e)}, 500

        return {"result": "success", 
                "items": result_list,
                "count":len(result_list)}, 200
    
 
class RankerListResource(Resource):
    # 랭킹 프래그먼트 리스트
    jwt_required()
    def get(self):
        try:
            userId = get_jwt_identity()
            connection = get_connection()

            query = '''select row_number() over(order by level desc) as ranking, u.nickname, l.level, l.exp
                        from user u
                        join level l
                        on u.id = l.userId
                        order by l.level desc  
                        limit 0, 100;'''

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            result_list = cursor.fetchall()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"result": "fail", "error": str(e)}, 500

        return {"result": "success", 
                "items": result_list,
                "count":len(result_list)}, 200