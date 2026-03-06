# -*- coding: utf-8 -*-

original_request_func = HTTP.Request
original_preview_func = Proxy.Preview


def Start():
    #HTTP.Headers['Accept'] = 'text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/webp;q=0,image/jpeg,image/apng,*/*;q=0.8'
    #HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
    #HTTP.Headers['Accept-Language'] = 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    HTTP.Request = original_request_func
    HTTP.Request = request_wrapper(HTTP.Request)
    Proxy.Preview = original_preview_func
    Proxy.Preview = preview_wrapper(Proxy.Preview)
    Log.Debug("ffmpeg path: %s", FFMPEG_PATH)


import functools
import subprocess
import threading
from distutils.spawn import find_executable

from .agent_movie import AgentMovie
from .agent_show import AgentShow
from .agent_music import AgentAlbum, AgentArtist
from .route_util import *    

FFMPEG_PATH = find_executable('ffmpeg', os.environ['PATH'])

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


def convert_webp_to_jpg(webp_data):
    if not FFMPEG_PATH:
        return webp_data
    cmd = [
        FFMPEG_PATH,
        '-hide_banner',
        '-loglevel', 'error',
        '-i', 'pipe:0',
        '-vframes', '1',
        '-f', 'image2pipe',
        '-vcodec', 'mjpeg',
        'pipe:1'
    ]
    process = None
    timer = None
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def kill_process():
            try:
                if process and process.poll() is None:
                    process.kill()
            except Exception:
                pass
        timer = threading.Timer(30, kill_process)
        timer.daemon = True
        timer.start()
        
        out, err = process.communicate(input=webp_data)
        if process.returncode == 0:
            return out
        else:
            Log.Error("FFmpeg 오류: %s", str(err))
    except Exception as e:
        Log.Exception("FFmpeg 변환 실패: %s", str(e))
    finally:
        if timer:
            timer.cancel()
        if process and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
    return webp_data


def is_webp(data):
    if len(data) < 16:
        return False
    if data[0:4] == b'RIFF' and data[8:12] == b'WEBP':
        return True
    return False


def check_response(response, url):
    content_type = 'Unknown'
    if 'content-type' in response.headers or 'Content-Type' in response.headers:
        content_type = response.headers['content-type']
    Log.Warn("%s - %s", url, content_type)


def request_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        kwds.setdefault('headers', {})
        kwds['headers']['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'
        response = func(*args, **kwds)
        try:
            if is_webp(response.content):
                check_response(response, args[0])
        except Exception:
            Log.Exception(args[0])
        return response
    return wrapped


def preview_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        args = list(args)
        if is_webp(args[0]):
            args[0] = convert_webp_to_jpg(args[0])
        return func(*args, **kwds)
    return wrapped
