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
ORIGINAL_PROXY_MEDIA_FUNC = Proxy.Media
ORIGINAL_STORAGE_SAVE_FUNC = Framework.components.storage.Storage.save
FFMPEG_PATH = find_executable('ffmpeg', os.environ['PATH'])
DWEBP_PATH = find_executable('dwebp', os.environ['PATH'])


def Start():
    HTTP.Request = ORIGINAL_HTTP_REQUEST_FUNC
    HTTP.Request = request_wrapper(HTTP.Request)
    Proxy.Preview = ORIGINAL_PROXY_PREVIEW_FUNC
    Proxy.Preview = preview_wrapper(Proxy.Preview)
    Proxy.Media = ORIGINAL_PROXY_MEDIA_FUNC
    Proxy.Preview = preview_wrapper(Proxy.Media)
    Framework.components.storage.Storage.save = ORIGINAL_STORAGE_SAVE_FUNC
    Framework.components.storage.Storage.save = storage_save_wrapper(Framework.components.storage.Storage.save)
    Log.Debug("ffmpeg 경로: %s", FFMPEG_PATH)
    Log.Debug("dwebp 경로: %s", DWEBP_PATH)


def d(data):
    import json
    return json.dumps(data, indent=4, ensure_ascii=False)


def kill_process(process):
    try:
        if process and process.poll() is None:
            process.kill()
    except Exception:
        Log.Error("FFmpeg 프로세스 종료 실패")


def convert_webp(webp_data):
    if DWEBP_PATH:
        cmd = [
            DWEBP_PATH,
            '-quiet',
            '-o', '-',
            '--', '-'
        ]
        mode = 'dwebp (WEBP -> PNG)'
    elif FFMPEG_PATH:
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
        mode = 'ffmpeg (WEBP -> JPEG)'
    else:
        return webp_data
    
    process = None
    timer = None
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timer = threading.Timer(30, kill_process, (process,))
        timer.daemon = True
        timer.start()
        
        out, err = process.communicate(input=webp_data)
        if process.returncode == 0 and out:
            Log.Debug(mode)
            return out
        else:
            Log.Error("%s 오류: %s", mode, err.decode('utf-8', 'ignore') if isinstance(err, str) else err)
    except Exception as e:
        Log.Exception("%s 실패: %s", mode, str(e))
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


def request_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        #kwds.setdefault('headers', {'Accept': 'image/webp,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'})
        if 'format=webp' in args[0]:
            args = list(args)
            args[0] = args[0].replace('format=webp', 'format=jpeg')
        response = func(*args, **kwds)
        #if 'content-type' in response.headers:
        #    Log.Debug("%s - %s", args[0], response.headers['content-type'])
        return response
    return wrapped


def preview_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        try:
            if is_webp(args[0]):
                Log.Debug("WEBP 데이터 발견")
                args = list(args)
                args[0] = convert_webp(args[0])
        except Exception:
            Log.Exception('')
        return func(*args, **kwds)
    return wrapped


def shorten_plex_path(full_path):
    parts = os.path.normpath(full_path).split(os.sep)
    shorten_parts = [
        item 
        for i, part in enumerate(parts)
        if part.endswith('.bundle') or 'com.plex' in part or '_combined' in part or '_stored' in part or i == len(parts) - 1
        for item in ('...', part)
    ]
    return os.sep.join(shorten_parts)


def storage_save_wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwds):
        # def save(self, filename, data, binary=True, mtime_key=None):
        filename = None
        try:
            _, filename, data = args[:3]
            if is_webp(data):
                Log.Debug("WEBP 데이터 발견: %s", filename)
                args = list(args)
                args[2] = convert_webp(data)
            if data is None:
                Log.Error("None 데이터 발견: %s", filename)
        except Exception:
            Log.Exception('')
        result = func(*args, **kwds)
        if filename:
            Log.Debug('저장: %s', shorten_plex_path(filename))
        return result
    return wrapped
