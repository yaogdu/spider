#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import os.path
path = os.path.abspath('')
print path
os.system('python '+path+'/start.py 5001 &')
os.system('python '+path+'/start.py 5002 &')
os.system('python '+path+'/start.py 5003 &')