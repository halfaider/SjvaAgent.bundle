# -*- coding: utf-8 -*-
import os, json, urllib, unicodedata, urllib2
from .agent_base import AgentBase, PutRequest


class ModuleKtv(AgentBase):
    module_name = 'ktv'

    def get_year(self, media):
        try:
            data = AgentBase.my_JSON_ObjectFromURL('http://127.0.0.1:32400/library/metadata/%s/children' % media.id)
            # 시즌.
            Log(json.dumps(data, indent=4))
            filename = data['MediaContainer']['Metadata'][0]['Media'][0]['Part'][0]['file']
            ret = os.path.splitext(os.path.basename(filename))[0]
            match = Regex(r'(?P<date>\d{6})').search(ret)
            if match:
                return match.group('date')
        except Exception as e:
            Log.Exception(str(e))


    def search(self, results, media, lang, manual):
        try:
            try:
                code = self.get_code_from_folderpath(media)
                if code != None and code.startswith('MT'):
                    code = code.replace('MT', 'FT')
                if code != None and code.startswith('F'):
                    meta = MetadataSearchResult(id=code, name=code, year=1900, score=200, thumb="", lang=lang)
                    results.Append(meta)
                    #return
            except Exception as e:
                Log.Exception(str(e))

            # 2021-12-13 닥터 슬럼프 리메이크 FT105262
            if manual and media.show is not None and media.show.startswith('FT'):
                code = media.show
                meta = MetadataSearchResult(id=code, name=code, year='', score=100, thumb="", lang=lang)
                results.Append(meta)
                return

            if manual and media.show is not None and media.show.startswith('K'):
                # 2022-11-18 KBS 같은 경우
                try:
                    code, title = media.show.split('|')
                    if code != 'KTV':
                        meta = MetadataSearchResult(id=code, name=title, year='', score=100, thumb="", lang=lang)
                        results.Append(meta)
                        return
                except Exception:
                    pass

            # KTV|수당영웅
            Log('SEARCH 0: %s' % media.show)
            if manual and media.show is not None and media.show.startswith('KTV'):
                keyword = media.show.replace('KTV|', '')

            else:
                Log('SEARCH : %s' % media.show)
                keyword = media.show
                Log('>> %s : %s %s' % (self.module_name, keyword, manual))
            Log('KEYWORD : %s', keyword)
            use_json = False
            search_data = None
            search_key = u'search|%s' % keyword
            if self.is_read_json(media) and manual == False:
                info_json = self.get_info_json(media)
                if info_json is not None and search_key in info_json:
                    search_data = info_json[search_key]
                    use_json = True
            if search_data is None:
                search_data = self.send_search(self.module_name, keyword, manual)
                if search_data is not None and self.is_write_json(media):
                    self.save_info(media, {search_key:search_data})
                    #self.append_info(media, search_key, search_data)

            if search_data is None:
                return
            #Log(json.dumps(search_data, indent=4))
            # 2021-07-07
            # 다음 차단-> 차단상태에서 ott search data 저장 -> 점수 미달 -> 새로고침 안됨
            max_score = 0
            daum_max_score = 100
            equal_max_score = 100
            if 'daum' in search_data:
                data = search_data['daum']
                flag_media_season = False
                if len(media.seasons) > 1:
                    for media_season_index in media.seasons:
                        if int(media_season_index) > 1:# and int(media_season_index) < 1900:
                            flag_media_season = True
                            break

                # 미디어도 시즌, 메타도 시즌
                if flag_media_season and len(data['series']) > 1:
                    # 마지막 시즌 ID
                    results.Append(MetadataSearchResult(
                        id=data['series'][-1]['code'],
                        name=u'%s | 시리즈' % keyword,
                        year=data['series'][-1]['year'],
                        score=100, lang=lang)
                    )

                # 미디어 단일, 메타 시즌
                elif len(data['series']) > 1:
                    #reversed
                    for index, series in enumerate(reversed(data['series'])):
                        Log(index)
                        Log(series)
                        if series['year'] is not None:
                            score = 95-(index*5)
                            if media.year == series['year']:
                                score = 100
                            if score < 20:
                                score = 20
                            if 'status' in series and series['status'] == 0:
                                score = score -40
                            max_score = max(max_score, score)
                            results.Append(MetadataSearchResult(id=series['code'], name=series['title'], year=series['year'], score=score, lang=lang))
                # 미디어 단일, 메타 단일 or 미디어 시즌, 메타 단일
                else:
                    # 2019-05-23 미리보기 에피들이 많아져서 그냥 방송예정도 선택되게.
                    #if data['status'] != 0:
                    # 2021-06-27 동명 컨텐츠중 년도 매칭되는것을 100으로 주기위해 99로 변경
                    if 'equal_name' in data and len(data['equal_name']) > 0:
                        score = daum_max_score = 99
                        #나의 아저씨 동명 같은 년도
                        if data['year'] == media.year:
                            score = daum_max_score = 100
                            equal_max_score = 99
                    else:
                        score = 100
                    meta = MetadataSearchResult(id=data['code'], name=data['title'], year=data['year'], thumb=data['image_url'], score=score, lang=lang)
                    tmp = data['extra_info'] + ' '
                    if data['status'] == 0:
                        tmp = tmp + u'방송예정'
                    elif data['status'] == 1:
                        tmp = tmp + u'방송중'
                    elif data['status'] == 2:
                        tmp = tmp + u'방송종료'
                    tmp = tmp + self.search_result_line() + data['desc']
                    meta.summary = tmp
                    meta.type = 'movie'
                    max_score = max(max_score, score)
                    results.Append(meta)

                if 'equal_name' in data:
                    for index, program in enumerate(data['equal_name']):
                        if program['year'] == media.year:
                            score = min(equal_max_score, 100 - (index))
                            max_score = max(max_score, score)
                            results.Append(MetadataSearchResult(id=program['code'], name='%s | %s' % (program['title'], program['studio']), year=program['year'], score=score, lang=lang))
                        else:
                            score = min(equal_max_score, 80 - (index*5))
                            max_score = max(max_score, score)
                            results.Append(MetadataSearchResult(id=program['code'], name='%s | %s' % (program['title'], program['studio']), year=program['year'], score=score, lang=lang))
            def func(show_list):
                for idx, item in enumerate(show_list):
                    score = min(daum_max_score, item['score'])
                    meta = MetadataSearchResult(id=item['code'], name=item['title'], score=score, thumb=item['image_url'], lang=lang)
                    meta.summary = item['site'] + ' ' + item['studio']
                    meta.type = "movie"
                    results.Append(meta)
                    return score
            if 'tving' in search_data:
                score = func(search_data['tving'])
                max_score = max(max_score, score)
            if 'wavve' in search_data:
                score = func(search_data['wavve'])
                max_score = max(max_score, score)
            if 'watcha' in search_data:
                score = func(search_data['watcha'])
                max_score = max(max_score, score)
            if use_json and max_score < 85:
                self.remove_info(media)
                self.search(results, media, lang, manual)

        except Exception as e:
            Log.Exception(str(e))


    def update_info(self, metadata, metadata_season, meta_info, image_urls, metadata_season_index):
        #metadata.original_title = metadata.title
        #metadata.title_sort = unicodedata.normalize('NFKD', metadata.title)
        metadata.studio = meta_info['studio']
        try: metadata.originally_available_at = Datetime.ParseDate(meta_info['premiered']).date()
        except Exception: pass
        metadata.content_rating = meta_info['mpaa']
        metadata.summary = meta_info['plot']
        metadata_season.summary = metadata.summary
        metadata.genres.clear()
        for tmp in meta_info['genre']:
            metadata.genres.add(tmp)

        module_prefs = self.get_module_prefs(self.module_name)
        # 부가영상
        for item in meta_info['extras']:
            url = 'sjva://sjva.me/playvideo/%s|%s' % (item['mode'], item['content_url'])
            metadata.extras.add(self.extra_map[item['content_type'].lower()](url=url, title=self.change_html(item['title']), originally_available_at=Datetime.ParseDate(item['premiered']).date(), thumb=item['thumb']))

        # rating
        for item in meta_info['ratings']:
            if item['name'] == 'tmdb':
                metadata.rating = item['value']
                metadata.audience_rating = 0.0

        # role
        #metadata.roles.clear()
        for item in ['actor', 'director', 'credits']:
            for item in meta_info[item]:
                actor = metadata.roles.new()
                actor.role = item['role']
                actor.name = item['name']
                actor.photo = item['thumb']
                Log('%s - %s'% (actor.name, actor.photo))

        # poster
        ProxyClass = Proxy.Media
        season_valid_names = set()
        poster_templates = {
            'poster': [metadata.posters, metadata_season.posters, 0],
            'landscape': [metadata.art, metadata_season.art, 0],
            'banner': [metadata.banners, None, 0]
        }
        for item in sorted(meta_info['thumb'], key=lambda k: k['score'], reverse=True):
            image_url = item.get('thumb') or item.get('value')
            aspect = item.get('aspect') or 'poster'
            process = poster_templates.get(aspect)
            """
            2026-03-12 halfaider
            프로그램과 동일한 포스터를 시즌에 계속 넣어줄 필요가 있을까?
            """
            if not process or not image_url or image_url in image_urls[aspect]:
                continue
            try:
                image_data = HTTP.Request(image_url).content
                if not image_data or len(image_data) < 16:
                    Log.Warn("유효하지 않은 이미지 데이터: %s", image_url)
                    continue
                process[2] = process[2] + 1
                content = ProxyClass(image_data, sort_order=process[2])
                """
                2026-03-12 halfaider
                update()에서 validate_keys() 하기 위해
                """
                image_urls[aspect].add(image_url)
                process[0][image_url] = content
                if process[1] is not None:
                    process[1][image_url] = content
                    season_valid_names.add(image_url)
            except Exception as e:
                Log.Exception(str(e))

        # 이거 확인필요. 번들제거 영향. 시즌을 주석처리안하면 쇼에 최후것만 입력됨.
        """
        2026-03-11 halfaider
        validate_keys()는 보유중인 모든 키가 입력받은 기준 목록에 있는지 검사함
        만약 기준 목록에 없으면 삭제
        그래서 각 시즌마다 validate_keys()를 하면 마지막 시즌에서 작업한 포스터만 남음
        """
        metadata_season.posters.validate_keys(season_valid_names)
        metadata_season.art.validate_keys(season_valid_names)

        # 테마
        valid_names = []
        if 'themes' in meta_info['extra_info']:
            for tmp in meta_info['extra_info']['themes']:
                try:
                    if tmp not in metadata.themes:
                        self.set_http_data(tmp, metadata.themes, valid_names)
                except Exception: pass

        # 테마2

        # Get the TVDB id from the Movie Database Agent
        tvdb_id = None
        if 'tmdb_id' in meta_info['extra_info']:
            tvdb_id = Core.messaging.call_external_function(
                'com.plexapp.agents.themoviedb',
                'MessageKit:GetTvdbId',
                kwargs = dict(
                    tmdb_id = meta_info['extra_info']['tmdb_id']
                )
            )
        Log('TVDB_ID : %s', tvdb_id)
        THEME_URL = 'https://tvthemes.plexapp.com/%s.mp3'
        if tvdb_id and THEME_URL % tvdb_id not in metadata.themes:
            tmp = THEME_URL % tvdb_id
            try:
                self.set_http_data(tmp, metadata.themes, valid_names, len(valid_names) + 1)
            except Exception: pass
        metadata.themes.validate_keys(valid_names)


    def update_episode(self, show_epi_info, episode, media, info_json, is_write_json, meta_code, frequency=None):
        site_orders = ['daum', 'tving', 'wavve']
        if isinstance(meta_code, str) and len(meta_code) > 1:
            if meta_code[1] == "W":
                site_orders.sort(key=lambda x: x != "wavve")
            elif meta_code[1] == "V":
                site_orders.sort(key=lambda x: x != "tving")

        def get_daum_episode_info(code, info_json, is_write_json, module_name, send_episode_info_func):
            if info_json and code in info_json:
                daum_episode_info = info_json[code]
            else:
                daum_episode_info = send_episode_info_func(module_name, code)
                if daum_episode_info and is_write_json:
                    info_json[code] = daum_episode_info
            return daum_episode_info

        valid_thumb_names = set()
        daum_episode_info = None
        daum_code = (show_epi_info.get('daum') or {}).get('code') or ''
        sort_order = 0
        for site in site_orders:
            try:
                if site not in show_epi_info:
                    continue
                if site == 'daum':
                    if not daum_episode_info:
                        daum_episode_info = get_daum_episode_info(daum_code, info_json, is_write_json, self.module_name, self.send_episode_info)
                        if not daum_episode_info:
                            continue
                    for thumb in sorted(daum_episode_info['thumb'], key=lambda k: k.get('score') or 0, reverse=True):
                        image_url = thumb.get('thumb') or thumb.get('value')
                        if not image_url or image_url in valid_thumb_names:
                            continue
                        sort_order = sort_order + 1
                        self.set_http_data(image_url, episode.thumbs, valid_thumb_names, sort_order=sort_order)
                else:
                    image_url = show_epi_info[site].get('thumb') or show_epi_info[site].get('value')
                    if not image_url or image_url in valid_thumb_names:
                        continue
                    sort_order = sort_order + 1
                    self.set_http_data(image_url, episode.thumbs, valid_thumb_names, sort_order=sort_order)
            except Exception:
                Log.Exception('')
            if valid_thumb_names:
                break
        if valid_thumb_names:
            episode.thumbs.validate_keys(valid_thumb_names)
        
        for site in site_orders:
            try:
                if site not in show_epi_info:
                    continue
                if site == 'daum':
                    if not daum_episode_info:
                        daum_episode_info = get_daum_episode_info(daum_code, info_json, is_write_json, self.module_name, self.send_episode_info)
                        if not daum_episode_info:
                            continue
                    epi_info = daum_episode_info
                    episode.title = daum_episode_info['title']
                else:
                    epi_info = show_epi_info[site]
                    episode.title = epi_info['title'] if epi_info.get('title') else epi_info['premiered']
                    if frequency:
                        episode.title = u'%s회 (%s)' % (frequency, episode.title)
                episode.originally_available_at = Datetime.ParseDate(epi_info['premiered']).date()
                episode.summary = epi_info['plot']
            except Exception:
                Log.Exception('')
            if episode.originally_available_at and episode.title and episode.summary:
                break
        
        if daum_episode_info:
            for item in daum_episode_info.get('extras') or ():
                try:
                    url = 'sjva://sjva.me/playvideo/%s|%s' % (item['mode'], item['content_url'])
                    episode.extras.add(self.extra_map[item['content_type'].lower()](url=url, title=self.change_html(item['title']), originally_available_at=Datetime.ParseDate(item['premiered']).date(), thumb=item['thumb']))
                except Exception:
                    Log.Exception('')



    def update(self, metadata, media, lang):
        #self.base_update(metadata, media, lang)
        try:
            is_write_json = self.is_write_json(media)
            module_prefs = self.get_module_prefs(self.module_name)
            flag_ending = False
            flag_media_season = False
            if len(media.seasons) > 1:
                for media_season_index in media.seasons:
                    if int(media_season_index) > 1:# and int(media_season_index) < 1900:
                        flag_media_season = True
                        break

            search_data = None
            search_key = u'search|%s' % media.title
            info_json = {}
            if self.is_read_json(media):
                tmp = self.get_info_json(media)
                #Log(tmp)
                if tmp is not None and search_key in tmp:
                    search_data = tmp[search_key]
                    info_json = tmp

            if search_data is None:
                search_data = self.send_search(self.module_name, media.title, False)
                if search_data is not None and is_write_json:
                    #self.append_info(media, search_key, search_data)
                    info_json[search_key] = search_data

            index_list = [index for index in media.seasons]
            index_list = sorted(index_list)
            Log('SEASON INDEX: %s', index_list)
            #for media_season_index in media.seasons:

            image_urls = {
                'poster': set(),
                'landscape': set(),
                'banner': set()
            }

            # 2021-11-05
            metadata.roles.clear()
            @parallelize
            def UpdateSeasons():
                for media_season_index in index_list:
                    # 2022-04-05
                    search_media_season_index = media_season_index
                    if len(str(media_season_index)) > 2:
                        search_media_season_index = str(media_season_index)[-2:]

                    if search_media_season_index in ['0', '00']:
                        continue

                    #Log(self.d(search_data['daum']['series']))
                    search_title = media.title.replace(u'[종영]', '')
                    search_title = search_title.split('|')[0].strip()
                    Log('search_title2 : %s', search_title)
                    #Log('search_code2 : %s', search_code)

                    # 신과함께3 단일 미디어파일이면 search_media_season_index 1이여서 시즌1이 매칭됨.
                    # 단일 미디어 파일에서는 사용하지 않도록함.
                    # 어짜피 여러 시즌버전을 넣는다면 신과함꼐3도 시즌3으로 바꾸어야함.
                    search_code = metadata.id
                    only_season_title_show = False
                    if flag_media_season and 'daum' in search_data and len(search_data['daum']['series']) > 1:
                        try: #사당보다 먼 의정부보다 가까운 3
                            Log("search series size: %s", len(search_data['daum']['series']))
                            search_title = search_data['daum']['series'][int(search_media_season_index)-1]['title']
                            search_code = search_data['daum']['series'][int(search_media_season_index)-1]['code']
                        except Exception:
                            only_season_title_show = True

                    Log('flag_media_season : %s', flag_media_season)
                    Log('search_title : %s', search_title)
                    Log('search_code : %s', search_code)
                    Log('media_season_index : %s', media_season_index)
                    Log('search_media_season_index: %s', search_media_season_index)


                    Log('only_season_title_show : %s', only_season_title_show)
                    #self.get_json_filepath(media)
                    #self.get_json_filepath(media.seasons[media_season_index])

                    if only_season_title_show == False:

                        meta_info = None
                        if info_json is not None and search_code in info_json:
                            # 방송중이라면 저장된 정보를 무시해야 새로운 에피를 갱신
                            if info_json[search_code]['status'] == 2:
                                meta_info = info_json[search_code]
                        if meta_info is None:
                            meta_info = self.send_info(self.module_name, search_code, title=search_title)
                            if meta_info is not None and is_write_json:
                                #self.append_info(media, search_code, meta_info)
                                info_json[search_code] = meta_info
                                #self.save_info(media, info_json)
                        Log("SEARCH_CODE: %s", search_code)
                        Log("TITLE: %s", meta_info['title'])
                        Log("SUMMARY: %s", meta_info['plot'])
                        Log("METAINFO_CODE: %s", meta_info['code'])
                        Log("METAINFO_SEASON: %s", meta_info['season'])
                        #Log(json.dumps(meta_info, indent=4))

                        if flag_media_season:
                            metadata.title = media.title.split('|')[0].strip()
                        else:
                            metadata.title = meta_info['title']


                        metadata.original_title = metadata.title
                        metadata.title_sort = unicodedata.normalize('NFKD', metadata.title)

                        if flag_media_season == False and meta_info['status'] == 2 and  module_prefs['end_noti_filepath'] != '':
                            parts = media.seasons[media_season_index].all_parts()
                            end_noti_filepath = module_prefs['end_noti_filepath'].split('|')
                            for tmp in end_noti_filepath:
                                if parts[0].file.find(tmp) != -1:
                                    metadata.title = u'[종영]%s' % metadata.title
                                    break

                        metadata_season = metadata.seasons[media_season_index]
                        @task
                        def UpdateSeason(metadata=metadata, metadata_season=metadata_season, meta_info=meta_info, image_urls=image_urls):
                            self.update_info(metadata, metadata_season, meta_info, image_urls, metadata_season_index=media_season_index)

                        # 포스터
                        # Get episode data.
                        for media_episode_index in media.seasons[media_season_index].episodes:
                            episode = metadata.seasons[media_season_index].episodes[media_episode_index]

                            @task
                            def UpdateEpisode(episode=episode, media_episode_index=media_episode_index, media=media, meta_info=meta_info, info_json=info_json, is_write_json=is_write_json, meta_code=metadata.id):
                                frequency = False
                                show_epi_info = None
                                if media_episode_index in meta_info['extra_info']['episodes']:
                                    show_epi_info = meta_info['extra_info']['episodes'][media_episode_index]
                                    self.update_episode(show_epi_info, episode, media, info_json, is_write_json, meta_code)
                                else:
                                    #에피정보가 없다면
                                    match = Regex(r'\d{4}-\d{2}-\d{2}').search(media_episode_index)
                                    if match:
                                        for key, value in meta_info['extra_info']['episodes'].items():
                                            if ('daum' in value and value['daum']['premiered'] == media_episode_index) or ('tving' in value and value['tving']['premiered'] == media_episode_index) or ('wavve' in value and value['wavve']['premiered'] == media_episode_index):
                                                show_epi_info = value
                                                self.update_episode(show_epi_info, episode, media, info_json, is_write_json, meta_code, frequency=key)
                                                break
                                if show_epi_info is None:
                                    return

                                episode.directors.clear()
                                episode.producers.clear()
                                episode.writers.clear()
                                for item in meta_info['credits']:
                                    meta = episode.writers.new()
                                    meta.role = item['role']
                                    meta.name = item['name']
                                    meta.photo = item['thumb']
                                for item in meta_info['director']:
                                    meta = episode.directors.new()
                                    meta.role = item['role']
                                    meta.name = item['name']
                                    meta.photo = item['thumb']


            """
            2026-03-12 halfaider
            이걸 해줘야 고아 파일이 안 생김
            """
            for aspect, urls in image_urls.items():
                if aspect == 'poster':
                    bucket = metadata.posters
                elif aspect == 'landscape':
                    bucket = metadata.art
                elif aspect == 'banner':
                    bucket = metadata.banners
                else:
                    continue
                if urls:
                    bucket.validate_keys(urls)

            # 시즌 title, summary
            if is_write_json and only_season_title_show == False:
                self.save_info(media, info_json)

            # 2021-09-15 주석처리함. 임의의 시즌으로 분할하는 경우를 고려
            #if not flag_media_season:
            #    return

            url = 'http://127.0.0.1:32400/library/metadata/%s' % media.id
            data = JSON.ObjectFromURL(url)
            section_id = data['MediaContainer']['librarySectionID']
            #token = Request.Headers['X-Plex-Token']
            token = self.get_token()
            for media_season_index in media.seasons:
                Log('media_season_index is %s', media_season_index)
                if media_season_index == '0':
                    continue
                try:
                    filepath = media.seasons[media_season_index].all_parts()[0].file
                    tmp = os.path.basename(os.path.dirname(filepath))
                    season_title = None
                    if tmp != metadata.title:
                        Log(tmp)
                        match = Regex(r'(?P<season_num>\d{1,8})\s*(?P<season_title>.*?)$').search(tmp)
                        Log('MATCH: %s' % str(match.groups()))
                        if match and (tmp.startswith(u'시즌 ') or tmp.startswith(u'Season ')):
                            Log('FORCE season_num : %s', match.group('season_num'))
                            Log('FORCE season_title : %s', match.group('season_title'))
                            Log('media_season_index : %s', media_season_index)
                            if int(match.group('season_num')) == int(media_season_index) and match.group('season_title') is not None:
                                season_title = match.group('season_title')
                    try:
                        Log("VAR season_title : %s" % season_title)
                        Log("VAR season_title : %s" % metadata_season.summary)
                    except Exception: pass
                    metadata_season = metadata.seasons[media_season_index]
                    if season_title is None:
                        if metadata_season.summary != None:
                            url = 'http://127.0.0.1:32400/library/sections/%s/all?type=3&id=%s&summary.value=%s&X-Plex-Token=%s' % (section_id, media.seasons[media_season_index].id, urllib.quote(metadata_season.summary.encode('utf8')), token)
                    else:
                        if metadata_season.summary == None:
                            metadata_season.summary = ''
                        url = 'http://127.0.0.1:32400/library/sections/%s/all?type=3&id=%s&title.value=%s&summary.value=%s&X-Plex-Token=%s' % (section_id, media.seasons[media_season_index].id, urllib.quote(season_title.encode('utf8')), urllib.quote(metadata_season.summary.encode('utf8')), token)

                    Log('URL : %s' % url)
                    request = PutRequest(url)
                    response = urllib2.urlopen(request)
                except Exception as e:
                    Log.Exception(str(e))
        except Exception as e:
            Log.Exception(str(e))


