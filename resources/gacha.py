from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error

from config import Config
from mysql_connection import get_connection


class GachaResouce(Resource) :
    # 뽑기(가챠) 획득하고 컬렉션에 저장
    @jwt_required()
    def put(self) :
        userId = get_jwt_identity()
        data = request.get_json()
        
        try : 
            connection = get_connection()
            
            query = '''update randomBox
                        set count = %s
                        where userId = %s;'''
            record = (data['boxCount'], userId)

            cursor = connection.cursor()
            cursor.execute(query, record)

            query = '''select id
                        from `character`
                        where characterName = %s;'''
            record = (data['gachaCharacterName'],)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result = cursor.fetchall()

            characterNum = result[0]['id']

            query = '''select *
                        from collection
                        where userId = %s and characterId = %s;'''
            record = (userId, characterNum)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result = cursor.fetchall()

            # 이미 내가 캐릭터를 가지고있으면 아무 작업을 하지 않는다.
            if len(result) != 0 :
                return {"result" : "이미 가지고 있는 캐릭터 입니다."}, 200

            query = '''insert into collection
                            (userId, characterId)
                            values (%s, %s);'''
            record = (userId, characterNum)

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