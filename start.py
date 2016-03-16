#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import logging.config
import time
import hashlib
import re
import json
import urllib
import urllib2
import random
import sys
import base64

from flask import Flask, request
from flask_restful import Resource, Api
from bs4 import BeautifulSoup
import requests
from pyquery import PyQuery as pq

from db import MongoDBPipeline

app = Flask(__name__)
api = Api(app)

BASE_URL = 'http://weixin.sogou.com'
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
base_url = 'http://mp.weixin.qq.com/s?'
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("spider")
reload(sys)
sys.setdefaultencoding('utf8')
class Spider(Resource):
    def get(self):
        url = request.args.get('key')
        logger.info('url is '+url)
        if url is None or url == '':
            return json.dumps({'success': False,'msg': 'url can\'t be empty'})
        try:
            if not url.startswith('http://mp.weixin.qq.com/') and not url.startswith('https://mp.weixin.qq.com/'):
                return {'success': False, 'msg': 'url pattern is not correct'}
            d0 = time.time()

            if(url.startswith('https')):#https不可以解析 转换成http ，效果一样
                url = url.replace('https','http')


            ######分解参数 然后拼接最小化参数####
            url = url.replace(base_url,'')

            list = str(url).split('&')

            params = ''
            for param in list:
                if param.startswith('__biz') or param.startswith('mid') or param.startswith('idx') or param.startswith('sn'):
                    params = params + param + '&'

            if params.endswith('&'):
                params = params[0:len(params) -1]
            url = base_url + params

            DB = app.config.get('DB')
            md = MongoDBPipeline(DB['db'],DB['col'],DB['address'],DB['replicaSet'])
            md5 = hashlib.new("md5", url).hexdigest()
            logger.info('url is ' + url + ' and md5 is ' + md5)
            item = md.find({'md5': md5});
            if item is not None and item.__len__() > 0:
                logger.info('fetch data from mongodb with key [' + md5 + ']')
                del item['_id']
                item['success'] = True
                return item
            else:
                logger.info('request from url [' + url + ']')
                item = {}

                TINYURL = app.config.get('TINYURL')
                apiUrl = TINYURL['tinyurl']  # tiny url service
                logger.info('tinyurl config is :[' + apiUrl + ']')


                tempUrl = url.replace('#', '%23').replace('&', '%26')
                try:
                    # generate tinyurl
                    f = urllib2.urlopen(apiUrl + tempUrl,timeout=5)
                    s = f.read()
                    logger.info('tinyurl is [' + s + ']')
                    item['tinyurl'] = s
                except Exception,ex:
                    logger.error('generate tinyurl error')
                    logger.error(ex)
                    item['tinyurl'] = tempUrl


                s = requests.Session()
                headers = {"User-Agent": UA}
                s.headers.update(headers)
                url2 = BASE_URL + '/weixin?query=123'
                r = s.get(url2)
                if 'SNUID' not in s.cookies:
                    p = re.compile(r'(?<=SNUID=)\w+')
                    s.cookies['SNUID'] = p.findall(r.text)[0]
                    suv = ''.join([str(int(time.time() * 1000000) + random.randint(0, 1000))])
                    s.cookies['SUV'] = suv

                # read page infomation
                s = requests.Session()
                s.headers.update({"User-Agent": UA})
                try:
                    r = s.get(url)

                    html = r.text
                    soup = BeautifulSoup(html, 'lxml')
                    p = re.compile(r'\?wx_fmt.+?\"')
                    content = str(soup.select("#js_content")[0]).replace('data-src', 'src')
                    d = pq(content)
                    item[u'title'] = soup.select('title')[0].text
                    print item['title']
                    item[u'author'] = soup.select('#post-user')[0].text
                    item['datetime'] = soup.select('#post-date')[0].text
                    item['contenturl'] = url
                    item['md5'] = md5
                    imgsrc = d.find('img[data-type]').attr('src')
                    if imgsrc != '' and imgsrc != None:#uploading img and store it in to data
                        logger.info('has picture in article')
                        logger.info(imgsrc)
                        try:

                            pic_data = base64.b64encode(urllib2.urlopen(imgsrc,timeout=5).read())

                            pic_data_md5 = hashlib.new("md5", pic_data).hexdigest()

                            data = {}  # upload img data

                            data['uid'] = 2634258
                            data['verifystr'] = pic_data_md5
                            #data['topic_id'] = 100
                            data['source'] = 16
                            data['data'] = pic_data
                            data['apptoken'] = 'dmaitoken01'

                            UPLOADING = app.config.get('UPLOADING')
                            upload_url = UPLOADING['url'];  # upload img url
                            logger.info('uploading url is ['+upload_url+']')
                            uploading_req = urllib2.urlopen(upload_url, json.dumps(data))
                            upload_result_content = uploading_req.read()
                            upload_result = json.loads(upload_result_content)
                            logger.info('uploading_result is ')
                            logger.info(upload_result)
                            if (upload_result['success'] == 1):
                                logger.info('uploading img ' + imgsrc + ' successfully')
                                item['img'] = upload_result['file_url']
                            else:
                                logger.info('uploading img ' + imgsrc + ' failed')
                                item['img'] = ''
                        except Exception,ex:
                            logger.error('uploading img error and set img to original img path')
                            logger.error(ex)
                            item['img']=imgsrc

                    span_length = d('p').find('span').length
                    for i in range(0,span_length):
                        if d('p').find('span').eq(i).text() != '':
                            digest = d('p').find('span').eq(i).text()
                            try:
                                digest = digest.encode("latin1").decode("utf8")#乱码判断
                            except Exception,e:
                                logger.error('normal utf-8 string')
                            item['digest'] = digest
                            break

                    if item.has_key('digest') == False:
                        item['digest']=''
                    md.save(item)
                    item['success'] = True
                    print item
                    logger.info('save item to mongodb ')

                except Exception, ex:
                    logger.error('error occurred')
                    logger.error(ex)
                    item = {'success': False}
                return item
        except Exception, ex:
            logger.info('error occurred while read info from url [' + url + ']')
            logger.error(ex)
            return {'success': False}

api.add_resource(Spider, '/')

try:
    app.config.from_envvar('spider_env')
except Exception,ex:
    logger.error('config file error,prepare to user test.py')
    app.config.from_pyfile('test.py')

if __name__ == '__main__':
    app.run(host='0.0.0.0',threaded=True)
