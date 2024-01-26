from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error

import boto3

from config import Config
from mysql_connection import get_connection


class PostingListResouce(Resource) :
    # 포스팅 생성
    @jwt_required()
    def post(self) :
        file = request.files.get('image')
        content = request.form.get('content')

        userId = get_jwt_identity()

        if file is None :
            return {'error' : '이미지를 업로드 해주세요'}, 400
        
        currentTime = datetime.now()
        newFileName = currentTime.isoformat().replace(':', '_') + str(userId) +'jpeg'
        file.filename = newFileName

        s3 = boto3.client('s3',
                          aws_access_key_id = Config.AWS_ACCESS_KEY,
                          aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)
        
        try:
            s3.uploadFileobj(file, Config.S3_BUCKET,
                             file.filename,
                             ExtraArgs = {'ACL':'public-read',
                                           'ContentType':'image/jpeg'})
        except Exception as e:
            print(e)
            return {'error' : str(e)}, 500
        

        try:
            connection = get_connection()

            query = '''insert into posting
                        (userId, imgUrl, content)
                        values
                        (%s, %s, %s);'''

            imgURL = Config.S3_LOCATION + file.filename

            record = (userId, imgURL, content)

            cursor = connection.cursor()
            cursor.execute(query, record)

            postingId = cursor.lastrowid

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {'error' : str(e)}, 500
        
        return {"result" : "success"}, 200
    
    # 모든 포스팅 가져오기
    @jwt_required()
    def get(self) :
        try :
            userId = get_jwt_identity()

            offset = request.args.get('offset')
            limit = request.args.get('limit')

            connection = get_connection()
            
            query = '''select *
                        from posting
                        order by createdAt decs
                        limit '''+str(offset)+''', '''+str(limit)+''';;'''
            
            record = (userId, )
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)
            result_list = cursor.fetchall()


            i = 0
            for row in result_list :
                result_list[i]['created_at'] = row['created_at'].isoformat()
                result_list[i]['updated_at'] = row['updated_at'].isoformat()
                i = i + 1

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
            
        
class PostingResource(Resource):
    # 포스팅 상세 보기
    @jwt_required()
    def get(self, posting_id):

        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            
            # 포스팅 상세정보 쿼리
            query = '''select p.id as postId, p.imgURL, p.content, 
                                u.id as userId, u.email, p.createdAt, 
                                count(l.id) as likeCnt, 
                                if(l2.id is null, 0, 1) as isLike
                        from posting p
                        join user u
                        on p.userId = u.id
                        left join `likes` l
                        on p.id = l.postingId
                        left join `likes` l2
                        on p.id = l2.postingId and l2.likerId = %s
                        where p.id = %s;'''
            record = (user_id, posting_id)
        
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            if len(result_list) == 0 :
                return {"error":"데이터가 없습니다."}, 400 
            

            post = result_list[0]


            # 포스팅 상세정보 태그 정보 쿼리
            query = '''select concat('#', tn.name) as tag
                        from tag t
                        join tagName tn
                        on t.tagNameId = tn.id
                        where postingId = %s;'''
            
            record = (posting_id, )

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()

            print(result_list)

            tag = [] # 빈 리스트 만들기
            for tag_dict in result_list:
                tag.append(tag_dict['tag'])

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500
        
        
        post['createdAt'] = post['createdAt'].isoformat()
        
        
        return {"result":"success",
                "post":post,
                "tag":tag}, 200
        

