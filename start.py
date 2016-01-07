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

class Spider(Resource):
    def get(self):
        # url = str(key).split('=')[0];
        # print key
        url = request.args.get('key')
        logging.config.fileConfig("logging.conf")
        logger = logging.getLogger("spider")

        if url is None or url == '':
            return json.dumps({'msg': 'url can\'t be empty'})
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
                # generate tinyurl
                f = urllib.urlopen(apiUrl + tempUrl)
                s = f.read()
                logger.info('tinyurl is [' + s + ']')
                item['tinyurl'] = s

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
                    item[u'author'] = soup.select('#post-user')[0].text
                    item['datetime'] = soup.select('#post-date')[0].text
                    item['contenturl'] = url
                    item['md5'] = md5
                    imgsrc = d.find('img[data-type]').attr('src')
                    if imgsrc != '' and imgsrc != None:#uploading img and store it in to data
                        logger.info('has picture in article')
                        logger.info(imgsrc)

                        pic_data = base64.b64encode(urllib2.urlopen(imgsrc).read())

                        pic_data_md5 = hashlib.new("md5", pic_data).hexdigest()

                        data = {}  # upload img data

                        data['uid'] = 2634258
                        data['verifystr'] = pic_data_md5
                        #data['topic_id'] = 100
                        data['source'] = 16
                        data['data'] = pic_data
                        data['apptoken'] = 'dmaitoken01'

                        # client_info = {}
                        # client_info['channel'] = '9'
                        # client_info['type'] = 'android'
                        # client_info['app'] = 11
                        # client_info['version'] = 4.8
                        # client_info['device_id'] = '7A0C057F-0944-4EA9-B193-D1ACB439F607'
                        # client_info['network'] = '2g'
                        # client_info['isp'] = '\u4e2d\u56fd\u79fb\u52a8'
                        # client_info['ip'] = '127.0.0.1'
                        # client_info['ssid'] = ''
                        #
                        # data['client_info'] = client_info


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

                    span_length = d('p').find('span').length
                    for i in range(0,span_length):
                        if d('p').find('span').eq(i).text() != '':
                            item['digest'] = d('p').find('span').eq(i).text()
                            break

                    if item.has_key('digest') == False:
                        item['digest']=''
                    md.save(item)
                    item['success'] = True
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

port = 5000  # default port
if len(sys.argv) >= 2:
    # use port from command line
    port = sys.argv[1]

if len(sys.argv) >= 3:
    # use port from command line
    file_name = sys.argv[2]
    if 'prod' == file_name:
        print 'use prod.py'
        app.config.from_pyfile('prod.py')
    else:
        print 'use test.py'
        app.config.from_pyfile('test.py')
else:
    print 'user test.py in else'
    app.config.from_pyfile('test.py')
try:
    # received port is valid or not
    int(port)


except Exception, ex:
    print ex
    print 'port number is invalid,use default port '
    port = 5000

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=int(port))
