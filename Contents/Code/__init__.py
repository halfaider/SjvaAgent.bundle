# -*- coding: utf-8 -*-
import functools
import subprocess
import threading
from distutils.spawn import find_executable

import Framework

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

ORIGINAL_HTTP_REQUEST_FUNC = HTTP.Request
ORIGINAL_PROXY_PREVIEW_FUNC = Proxy.Preview
ORIGINAL_STORAGE_SAVE_FUNC = Framework.components.storage.Storage.save
FFMPEG_PATH = find_executable('ffmpeg', os.environ['PATH'])


def Start():
    HTTP.Request = ORIGINAL_HTTP_REQUEST_FUNC
    HTTP.Request = request_wrapper(HTTP.Request)
    Proxy.Preview = ORIGINAL_PROXY_PREVIEW_FUNC
    Proxy.Preview = preview_wrapper(Proxy.Preview)
    Framework.components.storage.Storage.save = ORIGINAL_STORAGE_SAVE_FUNC
    Framework.components.storage.Storage.save = storage_save_wrapper(Framework.components.storage.Storage.save)
    Log.Debug("ffmpeg 경로: %s", FFMPEG_PATH)


def d(data):
    import json
    return json.dumps(data, indent=4, ensure_ascii=False)


def kill_process(process):
    try:
        if process and process.poll() is None:
            process.kill()
    except Exception:
        Log.Error("FFmpeg 프로세스 종료 실패")


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
        timer = threading.Timer(30, kill_process, (process,))
        timer.daemon = True
        timer.start()
        
        out, err = process.communicate(input=webp_data)
        if process.returncode == 0 and out:
            Log.Debug("FFmpeg 변환: WEBP -> JPEG")
            return out
        else:
            Log.Error("FFmpeg 오류: %s", str(err))
    except Exception as e:
        Log.Exception("FFmpeg 변환 실패: %s", str(e))
    finally:
        if timer:
            timer.cancel()
        kill_process(process)
    return webp_data


def is_webp(data):
    if len(data) < 16:
        return False
    if data[0:4] == b'RIFF' or  data[8:12] == b'WEBP':
        return True
    return False


def get_content_type(response):
    for key, value in response.headers.items():
        if key.lower() == 'content-type':
            return value
    return "Unknown"


def request_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        #kwds.setdefault('headers', {'Accept': 'image/webp,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'})
        response = func(*args, **kwds)
        if is_webp(response.content):
            content_type = get_content_type(response)
            Log.Warn("%s - %s", args[0], content_type)
        return response
    return wrapped


def preview_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        try:
            if is_webp(args[0]):
                Log.Debug("WEBP 데이터 발견")
                args = list(args)
                args[0] = convert_webp_to_jpg(args[0])
        except Exception:
            Log.Exception('')
        return func(*args, **kwds)
    return wrapped


def storage_save_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        # def save(self, filename, data, binary=True, mtime_key=None):
        try:
            _, filename, data = args[:3]
            if is_webp(data):
                Log.Debug("WEBP 데이터 발견: %s", filename)
                args = list(args)
                args[2] = convert_webp_to_jpg(data)
        except Exception:
            Log.Exception('')
        return func(*args, **kwds)
    return wrapped
