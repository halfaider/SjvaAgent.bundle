# -*- coding: utf-8 -*-

original_request_func = HTTP.Request


def Start():
    #HTTP.Headers['Accept'] = 'text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/webp;q=0,image/jpeg,image/apng,*/*;q=0.8'
    #HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
    #HTTP.Headers['Accept-Language'] = 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    HTTP.Request = original_request_func
    HTTP.Request = wrapper(HTTP.Request)


import functools

from .agent_movie import AgentMovie
from .agent_show import AgentShow
from .agent_music import AgentAlbum, AgentArtist
from .route_util import *    
     
"""
if tmp == 'Jav Censored':
    from .agent_jav_censored import AgentJavCensored
    from .agent_jav_censored_ama import AgentJavCensoredAma
    
elif tmp == 'Jav Censored Ama':
    from .agent_jav_censored_ama import AgentJavCensoredAma
    from .agent_jav_censored import AgentJavCensored
"""

def d(data):
    import json
    return json.dumps(data, indent=4, ensure_ascii=False)


def is_webp(data):
    if len(data) < 16:
        return False
    if data[0:4] == b'RIFF' and data[8:12] == b'WEBP':
        return True
    return False


def wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        kwds.setdefault('headers', {})
        kwds['headers']['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'
        kwds['headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        kwds['headers']['Accept-Language'] = 'ko,en-US;q=0.9,en;q=0.8,de;q=0.7,zh-CN;q=0.6,zh;q=0.5,lb;q=0.4'
        response = func(*args, **kwds)
        try:
            if is_webp(response.content):
                content_type = 'Unknown'
                if 'content-type' in response.headers or 'Content-Type' in response.headers:
                    content_type = response.headers['content-type']
                Log.Warn("%s - %s", args[0], content_type)
        except Exception:
            Log.Exception(args[0])
        return response
    return wrapped
