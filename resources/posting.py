from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource
from mysql.connector import Error

import boto3
import sys
import urllib.request

import requests

from config import Config
from mysql_connection import get_connection


class PostingListResouce(Resource) :
    # 포스팅 생성
    @jwt_required()
    def post(self) :
        data = request.get_json()
        userId = get_jwt_identity()

        if data['imgURL'] == "" :
            return {'error' : '이미지를 업로드 해주세요'}, 400
        
        if data['content'] == "" :
            return {'error' : '내용을 입력해주세요'}, 400
        

        # 포스팅 저장
        try:
            connection = get_connection()

            query = '''insert into posting
                        (userId, imgUrl, content)
                        values
                        (%s, %s, %s);'''            

            record = (userId, data['imgURL'], data['content'])

            cursor = connection.cursor()
            cursor.execute(query, record)

            postingId = cursor.lastrowid

            str_tags = data['tags']
            contain = ","

            # 태그가 하나일 때 저장
            if contain not in str_tags :
                tag = data['tags']

                tag = tag.lower()

                query = '''select *
                            from tagName
                            where name = %s;'''
                
                record = (tag, )

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

            # 태그가 여러개일 때 저장
            else :
                tag_list = data['tags'].split(",")

                for tag in tag_list:                
                    tag = tag.lower()

                    query = '''select *
                                from tagName
                                where name = %s;'''
                    
                    record = (tag, )

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


class PostingLabelResouce(Resource) :
    # 라벨 생성
    @jwt_required()
    def post(self) :        
        source_language = "en"
        target_language = "ko"

        file = request.files.get('image')        
        userId = get_jwt_identity()

        if file is None :
            return {'error' : '이미지를 업로드 해주세요'}, 400

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

        newFileName = Config.S3_LOCATION + newFileName
        
        i = 0
        for row in tag_list :
            text_to_translate = row
            tag_list[i] = self.translate_text(text_to_translate, source_language, target_language)
            i = i+1
            
        
        return {"result" : "success",
                "tagList" : tag_list,
                "fileUrl" : newFileName}, 200

    # 오토 태깅(rekognition)
    def detect_labels(self, photo, bucket):

        client = boto3.client('rekognition', 
                              'ap-northeast-2', 
                              aws_access_key_id = Config.AWS_ACCESS_KEY_ID,
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

    # 태깅 번역
    def translate_text(self, text, source_lang, target_lang):
        url = "https://openapi.naver.com/v1/papago/n2mt"
        headers = {
            "X-Naver-Client-Id": Config.X_NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": Config.X_NAVER_CLIENT_SECRET
        }
        data = {
            "source": source_lang,
            "target": target_lang,
            "text": text
        }

        response = requests.post(url, headers=headers, data=data)
        
        if response.status_code == 200:
            translated_text = response.json()["message"]["result"]["translatedText"]
            return translated_text
        else:
            return "번역에 실패했습니다. 상태 코드: {}".format(response.status_code)
        
        
class PostingResource(Resource):
    # 포스팅 상세 보기
    @jwt_required()
    def get(self, postingId):
        user_id = get_jwt_identity()

        try:
            connection = get_connection()
            
            # 포스팅 상세정보 쿼리
            query = '''select p.id as postingId, u.profileUrl, 
                                u.nickName, l.level, p.imgURL as postingUrl, 
                                t2.name as tagName, p.content, p.createdAt
                        from posting as p
                        join user as u
                        on p.userId = u.id and p.id = %s
                        join level as l
                        on u.id = l.userId
                        left join tag as t
                        on t.postingId = p.id
                        join tagName as t2
                        on t2.id = t.tagNameId;'''
            
            record = (postingId,)
        
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            result_list = cursor.fetchall()
            
            tag_list = []

            for row in result_list :
                tag_list.append(row['tagName'])
            
            
            result_list[0]['createdAt'] = result_list[0]['createdAt'].isoformat()
            result = result_list[0]
            del result['tagName']

            # 포스팅 상세정보 태그 정보 쿼리
            query = '''select u.nickName
                        from posting as p
                        join likes as l
                        on p.id = l.postingId
                        join user as u
                        on u.id = l.likerId
                        where p.id = %s
                        order by l.id;'''
            
            record = (postingId, )

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, record)

            liker_list = cursor.fetchall()
            
            result['likerList'] = liker_list['nickName']

            cursor.close()
            connection.close()

        except Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500        
        
        return {"result" : "success",
                "item" : result,
                "tagList" : tag_list}, 200
    
    # 포스팅 수정
    @jwt_required()
    def put(self, postingId):

        file = request.files.get('image')
        content = request.form.get('content')
        tag_list = request.form.get('tag')

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
        

        try:
            connection = get_connection()
            query = '''update posting
                        set imgURl = %s,
                        content = %s 
                        where id = %s and userId = %s;'''
            
            imgURL = Config.S3_LOCATION + file.filename

            record = (imgURL, content, postingId, userId)
            
            cursor = connection.cursor()
            cursor.execute(query, record)

            # 태그 수정
            tag_list = ''.join(tag_list).split()
            for tag in tag_list:
                tag = tag.strip().lower().replace("#", "")
                query = '''select *
                            from tagName
                            where name = %s;'''
                record = (tag, )

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

                query = '''update tag
                            set tagNameId = %s
                            where postingId = %s;'''
  
                record = (tagNameId, postingId)

                cursor = connection.cursor()
                cursor.execute(query, record)
            postingId = cursor.lastrowid

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e:
            print(e)
            cursor.close()
            connection.close()
            return {'error':str(e)}, 500
        
        return {'result':'success'}, 200

    # 포스팅 삭제
    @jwt_required()
    def delete(self, postingId):
        
        userId = get_jwt_identity()

        try :
            connection = get_connection()
            query = '''delete from posting
                        where id = %s and userId = %s;'''
            record = (postingId, userId)

            cursor = connection.cursor()
            cursor.execute(query, record)

            connection.commit()

            cursor.close()
            connection.close()

        except Error as e:
            print(e)
            cursor.close()
            connection.close()
            return {"error":str(e)}, 500

        return {"result":"success"}, 200
      

class PostingPopResource(Resource):
    # 포스팅 인기순 정렬
    @jwt_required()
    def get(self):
        userId = get_jwt_identity()
        offset = request.args.get('offset')
        limit = request.args.get('limit')

        try :

            connection = get_connection()
            
            query = '''select *, count(l.id) as likersCnt
                        from posting p
                        left join likes l
                        on p.id = l.postingId
                        group by p.id
                        order by likersCnt desc
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

