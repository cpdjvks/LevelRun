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
        
        if content is None :
            return {'error' : '내용을 입력해주세요'}, 400
        
        
        currentTime = datetime.now()
        newFileName = currentTime.isoformat().replace(':', '_') + str(userId) +'jpeg'
        file.filename = newFileName

        s3 = boto3.client('s3',
                          aws_access_key_id = Config.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)
        
        try:
            s3.upload_fileobj(file, Config.S3_BUCKET,
                             file.filename,
                             ExtraArgs = {'ACL':'public-read',
                                           'ContentType':'image/jpeg'})
        except Exception as e:
            print(e)
            return {'error' : str(e)}, 500
        
        # rekognition 서비스 이용
        tag_list = self.detect_labels(newFileName, Config.S3_BUCKET)

        # 포스팅 저장
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

            # 태그 저장
            for tag in tag_list:
                tag = tag.lower()
                query = '''select *
                            from tagName
                            where name = %s;'''
                record = (tag.lower(), )

                cursor = connection.cursor(dictionary=True)
                cursor.execute(query, record)

                result_list = cursor.fetchall()

                if len(result_list) != 0:
                    tagNameId = result_list[0]['id']

                else:
                    query = '''insert into tagName
                                (name)
                                values
                                (%s);'''
            
                    record = (tag, )

                    cursor = connection.cursor()
                    cursor.execute(query, record)

                    tagNameId = cursor.lastrowid

                query = '''insert into tag
                            (postingId, tagNameId)
                            values
                            (%s, %s);'''
  
                record = (postingId, tagNameId)

                cursor = connection.cursor()
                cursor.execute(query, record)

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {'error' : str(e)}, 500
        
        return {"result" : "success"}, 200
    

    # 오토 태깅(rekognition)
    def detect_labels(self, photo, bucket):

        client = boto3.client('rekognition', 
                              'ap-northeast-2', 
                              aws_access_key_id = Config.AWS_ACCESS_KEY,
                              aws_secret_access_key = Config.AWS_SECRET_ACCESS_KEY)


        response = client.detect_labels(Image={'S3Object':{'Bucket':bucket,'Name':photo}},
        MaxLabels=5, )

        labels_list = []
        for label in response['Labels']:
            print("Label: " + label['Name'])
            print("Confidence: " + str(label['Confidence']))
                        
            if label['Confidence'] >= 90 :
                labels_list.append(label['Name'])
        
        return labels_list

    

    # 모든 포스팅 가져오기(최신순)
    @jwt_required()
    def get(self) :
        
        userId = get_jwt_identity()
        offset = request.args.get('offset')
        limit = request.args.get('limit')

        try :

            connection = get_connection()
            
            query = '''select *
                        from posting
                        order by createdAt desc
                        limit '''+offset+''', '''+limit+''';'''
            
            record = (userId, )
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            result_list = cursor.fetchall()

            i = 0
            for row in result_list :
                result_list[i]['createdAt'] = row['createdAt'].isoformat()
                result_list[i]['updatedAt'] = row['updatedAt'].isoformat()
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
        

