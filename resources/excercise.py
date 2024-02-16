from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error
import pytz

from config import Config
from mysql_connection import get_connection

class ExcerciseRecordResource(Resource):
    # 운동 기록 저장/ 수정
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        data = request.get_json()

        try:
            connection = get_connection()
            
            # 포스팅 상세정보 쿼리
            query = '''select *
                        from excerciseLog
                        where userId = %s;'''
            
            record = (user_id,)
        
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()

            # 데이터베이스에 유저에 대한 정보가 없을 때 (신규 유저)
            if len(result_list) == 0 :
                query = '''insert into excerciseLog
                            (userId, distance, cal, time, steps)
                            values
                            (%s, 0, 0, 0, 0);;'''
            
                record = (user_id,)
            
                cursor = connection.cursor()
                cursor.execute(query, record)

            else :                
                is_equal = 0

                # 현재 시간 정보를 받아온다
                current_time = datetime.now()
                current_time = current_time.strftime("%Y-%m-%d")

                seoul_timezone = pytz.timezone('Asia/Seoul')
                
                # 현재 시간
                print(current_time)
                
                # db에서 받아온 표준시간을 서울시간으로 변경후 비교한다.
                for row in result_list :
                    db_time = row['createdAt']
                    db_time = db_time.astimezone(seoul_timezone)
                    db_time = db_time.strftime("%Y-%m-%d")
                    
                    if current_time  == db_time :
                        is_equal = 1
                        date_time = row['createdAt']
                    
                #  비교한 시간정보가 같을 때 update문을 실행한다.
                if is_equal == 1 :                    
                    query = '''update excerciseLog
                                set distance = %s, cal = %s, time = %s, steps = %s
                                where userId = %s and createdAt = %s;'''
                    record = (data['distance'], data['cal'], data['time'], data['steps'], user_id, date_time)

                    cursor = connection.cursor()
                    cursor.execute(query, record)
                # 비교한 시간정보가 다를 때 inster 한다.
                else :
                    query = '''insert into excerciseLog
                                (userId, distance, cal, time, steps)
                                values
                                (%s, %s, %s, %s, %s);'''
                    
                    record = (user_id, data['distance'], data['cal'], data['time'], data['steps'])

                    cursor = connection.cursor()
                    cursor.execute(query, record)

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500        
        
        return {"result" : "success"}, 200
    # 운동 기록 가져오기
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            
            # 포스팅 상세정보 쿼리
            query = '''select *
                        from excerciseLog
                        where userId = %s;'''
            
            record = (user_id,)
        
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()

            # 현재 시간 정보를 받아온다            
            current_time = datetime.now()
            current_time= current_time.strftime("%Y-%m-%d")

            seoul_timezone = pytz.timezone('Asia/Seoul')

            #  db에 정보가 없을 때 
            if len(result_list) == 0 :

                cursor.close()
                connection.close()

                return {"result" : "success",
                        "steps" : 0,
                        "cal" : 0,
                        "distance" : 0}, 200
            
            # db에 정보가 있으면 가져온다.
            # 금일 운동 기록이 있는지 확인한다            
            for row in result_list :
                db_time = row['createdAt']
                db_time = db_time.astimezone(seoul_timezone)
                db_time = db_time.strftime("%Y-%m-%d")
                

                if current_time == db_time :
                    time = row['createdAt']

                    query = '''select id, userId, distance, cal, steps
                                from excerciseLog
                                where userId = %s and createdAt = %s;'''
                    record = (user_id, time)

                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(query, record)
                    result = cursor.fetchall()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500        
        
        return {"result" : "success",
                "items" : result}, 200