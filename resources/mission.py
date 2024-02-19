from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error
import pytz

import requests

from config import Config
from mysql_connection import get_connection
      
class MissionResource(Resource):
    # 포스팅 인기순 정렬
    @jwt_required()
    def post(self):
        userId = get_jwt_identity()
        data = request.get_json()
        mission = "isClear" + str(data['mission'])
        
        try :            
            connection = get_connection()
            
            query = '''select *
                        from mission
                        where userId = %s;'''
            
            record = (userId, )
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()            

            # 테이블에 임무 정보가 없으면 insert 한다
            if len(result_list) == 0 :
                query = '''insert into mission
                            (userId, ''' + mission + ''')
                            values
                            (%s, 1);'''
                
                record = (userId,)
                cursor = connection.cursor()
                cursor.execute(query, record)                

            # 테이블에 임무 정보가 있으면 오늘 날짜가 있는지 확인한다
            else :
                is_equal = 0
                # 현재 시간 정보를 받아온다
                seoul_timezone = pytz.timezone('Asia/Seoul')
                current_time = datetime.now().astimezone(seoul_timezone)
                current_time = current_time.strftime("%Y-%m-%d")

                # db에서 받아온 표준시간을 서울시간으로 변경후 비교한다.
                for row in result_list :
                    db_time = row['createdAt']
                    db_time = db_time.astimezone(seoul_timezone)
                    db_time = db_time.strftime("%Y-%m-%d")
                    
                    if current_time  == db_time :
                        is_equal = 1
                        date_time = row['createdAt']

                #  오늘 날짜 정보가 있으면 update 한다
                if is_equal == 1 :
                    query = '''update mission
                                set ''' + mission + '''= 1
                                where userId = %s and createdAt = %s'''
                    
                    record = (userId, date_time)
                    cursor = connection.cursor()
                    cursor.execute(query, record)

                # 오늘 날짜가 없으면 insert 한다.
                else :
                    query = '''insert into mission
                            (userId, ''' + mission + ''')
                            values
                            (%s, 1);'''
                
                    record = (userId, )
                    cursor = connection.cursor()
                    cursor.execute(query, record)

            connection.commit()
            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"result": "fail", "error": str(e)}, 500

        return {"result": "success"}, 200

