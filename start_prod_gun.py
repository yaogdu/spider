#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import os.path
path = os.path.abspath('')
print path
os.system('export spider_env=prod.py')
os.system('gunicorn -c gun.conf start:app  1>/dev/null 2>&1 &')