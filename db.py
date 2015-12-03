# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

from pymongo import MongoClient
from phantom import DB

import logging as log


class MongoDBPipeline(object):
    def __init__(self):

        self.db = DB['db']
        self.col = DB['col']
        #connection = pymongo.Connection(self.server,self.port)
        #connection = MongoClient(self.server,self.port)
        connection = MongoClient(DB['address'], replicaSet=DB['replicaSet'])
        db = connection[self.db]
        self.collection = db[self.col]

    def save(self, item):

        self.collection.insert_one(dict(item))

        return item

    def find(self, item):

        item = self.collection.find_one(item)

        return item
