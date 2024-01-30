
from aifc import Error
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource

from mysql_connection import get_connection


class RandomBoxListResouce(Resource) :
    # 상자 정보 가져오기
    @jwt_required()
    def get(self) :        
        userId = get_jwt_identity()

        try :
            connection = get_connection()

            query = '''select *
                        from location
                        where userId = %s and isComplete = 0;'''
            
            record = (userId,)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()

            i = 0
            for row in result_list :
               result_list[i]['createdAt'] = row['createdAt'].isoformat()               
               i = i+1

            cursor.close()
            connection.close()

            return {"result" : "success",
                "myId" : userId,
                "items" : result_list,
                "count" : len(result_list)}, 200

        except Error as e :
            print(e)
            cursor.close()
            connection.close()

            return {"result" : str(e)}, 500