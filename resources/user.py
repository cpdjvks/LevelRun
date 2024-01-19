from flask import request
from flask_jwt_extended import create_access_token, get_jwt, jwt_required
from flask_restful import Resource
from mysql_connection import get_connection
from mysql.connector import Error

import requests
from email_validator import EmailNotValidError, validate_email
from utils import check_password, hash_password

# 회원가입
class UserRegisterResource(Resource) :
    def post(self) :
        data = request.get_json()        

        # 이메일 유효성 검사
        try :
            validate_email(data['email'])

        except EmailNotValidError as e :
            print(e)
            return {"Error" : str(e)}, 400

        # 비밀번호 길이 검사
        if len(data['password']) < 4 and len(data['password']) > 14 :
            return {"Error" : "비밀번호 길이가 올바르지 않습니다."}, 400

        # 단방향 암호화된 비밀번호를 저장
        password = hash_password(data['password'])

        try :
            connection = get_connection()        

            query = '''insert into user
                    (nickName, email, password)
                    value(%s, %s, %s);'''
            record = (data['nickName'], data['email'], password)

            cursor = connection.cursor()
            cursor.execute(query, record)

            

            # 회원가입시 생성한 유저아이디를 데이터베이스에서 가져와
            # 초기 랭크테이블 정보를 넣어준다.
            userId = cursor.lastrowid            

            query = '''insert into `rank`
                        (userId)
                        values
                        (%s);'''

            record = (userId,)
            
            # 커서 초기화 
            cursor = connection.cursor()
            cursor.execute(query, record)            

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()

            return {"Error" : str(e)}, 500
        
        # user 테이블의 id로 JWT 토큰을 만들어야 한다.
        access_token = create_access_token(userId)
        
        return {"result" : "success", "accessToken" : access_token}, 200

# todo : 카카오 회원가입
class KakaoRegisterResource(Resource) :
    pass

# 로그인
class UserLoginResource(Resource) :
    def post(self) :
        data = request.get_json()
        try :
            connection = get_connection()

            query = '''select id, nickName, email, password 
                        from user
                        where email = %s;'''
            
            record = (data['email'],)

            # 딕셔너리 형태로 가져옴
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()

            return {"fail" : str(e)}, 500        

        # 가입정보 확인
        if len(result_list) == 0 :
            return {"Error" : "회원가입된 정보가 없습니다."}, 400
                
        password = str(data['password'])
        

        check = check_password(password, result_list[0]['password'])
        if check == False :
            return {"error" : "비밀번호가 맞지 않습니다."}, 406
        
        # 암호화 토큰생성
        access_token = create_access_token(result_list[0]['id'])

        return {"result" : "success", "accessToken" : access_token}, 200
    
jwt_blocklist = set()
class UserLogoutResource(Resource) :            # 로그아웃
    @jwt_required()
    def delete(self) :
        jti = get_jwt()['jti']          # 토큰안에 있는 jti 정보
        print()
        print(jti)
        print()
        jwt_blocklist.add(jti)

        return {"result" : "success"}, 200


