from flask import render_template
from flask import request
from flask import url_for
from src.interface import Live
import asyncio

from .main_complete import TikTok

__all__ = ["WebUI"]


class WebUI(TikTok):
    def __init__(self, parameter):
        self.database = None  # 先初始化database属性，后面使用时再设置实际值
        super().__init__(parameter, self.database)
        self.cookie = parameter.cookie
        self.preview = parameter.preview
        self.error_works = {
            "text": "获取作品数据失败！",
            "author": None,
            "describe": None,
            "download": False,
            "music": False,
            "origin": False,
            "dynamic": False,
            "preview": self.preview,
        }
        self.error_live = {
            "text": "提取直播数据失败！",
            "flv": {},
            "m3u8": {},
            "best": "",
            "preview": self.preview,
        }

    @staticmethod
    def _convert_bool(data: dict):
        for i in (
                "folder_mode",
                "music",
                "dynamic_cover",
                "original_cover",
                "download",
        ):
            data[i] = {"on": True, None: False}[data.get(i)]
        for i, j in (
                ("max_size", 0),
                ("chunk", 1024 * 1024),
                ("max_retry", 5),
                ("max_pages", 0),
        ):
            try:
                data[i] = int(data[i])
            except ValueError:
                data[i] = j

    def update_settings(self, data: dict, api=True):
        if not api:
            self._convert_bool(data)
        # print(data)  # 调试使用
        return self.parameter.update_settings_data(data)

    def generate_works_data(self, data: list[dict] | str) -> dict:
        if isinstance(data, str):
            return self.error_works | {"text": "后台下载作品成功！", "preview": data}
        data = data[0]
        return {
            "text": "获取作品数据成功！",
            "author": data["nickname"],
            "describe": data["desc"],
            "download": data["downloads"]
            if data["type"] == "视频"
            else (d := data["downloads"].split()),
            "music": data["music_url"],
            "origin": data["origin_cover"],
            "dynamic": data["dynamic_cover"],
            "preview": data["origin_cover"] or d[0],
        }

    def deal_single_works(self, url: str, download: bool) -> dict:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        ids = loop.run_until_complete(self.links.run(url))
        if not any(ids):
            self.logger.warning(f"{url} 提取作品 ID 失败")
            return {}
        
        # 实现一个完整的记录器模拟
        class CompleteRecorderMock:
            def __init__(self):
                self.field_keys = []  # 必需的属性
                # 添加可能需要的其他属性
                self.fields = {}
                self.name = "mock_recorder"
                
            async def save(self, values):
                # 模拟保存功能，实际上什么都不做
                self.logger.debug("模拟记录器保存数据")
                return True
                
            def __getattr__(self, name):
                # 处理所有未定义的属性访问
                return lambda *args, **kwargs: None
        
        recorder = CompleteRecorderMock()
        recorder.logger = self.logger  # 添加logger属性以便记录日志
        
        # 调用handle_detail但捕获所有异常
        try:
            result = loop.run_until_complete(self._handle_detail(ids, False, recorder, not download))
            return self.generate_works_data(result) if result else {}
        except Exception as e:
            self.logger.error(f"处理作品数据时出错: {str(e)}")
            return {}

    def _filter_best_stream_url(self, stream_urls: list) -> list:
        """从多个流地址中筛选出最佳质量的流地址"""
        if not stream_urls:
            return []
            
        self.logger.info(f"开始筛选 {len(stream_urls)} 个流地址，查找最佳质量")
        
        # 去重处理 - 使用集合存储唯一URL的基础部分（去除查询参数）
        unique_urls = set()
        deduped_urls = []
        
        for url in stream_urls:
            # 获取基本URL，去除查询参数
            base_url = url.split('?')[0] if '?' in url else url
            if base_url not in unique_urls:
                unique_urls.add(base_url)
                deduped_urls.append(url)
        
        self.logger.info(f"去重后剩余 {len(deduped_urls)} 个流地址")
        
        # 根据清晰度和格式分组
        flv_by_quality = {}
        m3u8_by_quality = {}
        other_urls = []
        
        # 清晰度关键词排序（越靠前优先级越高）
        quality_keywords = [
            "origin", "原画", "uhd", "蓝光", "ultra", "hd", "高清", 
            "720p", "1080p", "sd", "标清", "md", "ld", "540", "480", "360"
        ]
        
        for url in deduped_urls:
            url_lower = url.lower()
            
            # 识别URL中的清晰度标记
            quality = "unknown"
            for keyword in quality_keywords:
                if keyword in url_lower:
                    quality = keyword
                    break
                    
            # 特殊处理_sd, _hd等后缀
            for suffix in ["_origin", "_uhd", "_hd", "_sd", "_ld", "_md"]:
                if suffix in url_lower:
                    quality = suffix[1:]  # 去掉下划线
                    break
            
            # 按格式和清晰度分组
            if ".flv" in url_lower:
                if quality not in flv_by_quality:
                    flv_by_quality[quality] = []
                flv_by_quality[quality].append(url)
            elif ".m3u8" in url_lower:
                if quality not in m3u8_by_quality:
                    m3u8_by_quality[quality] = []
                m3u8_by_quality[quality].append(url)
            else:
                other_urls.append(url)
        
        # 按清晰度优先级对分组进行排序
        quality_priority = {keyword: idx for idx, keyword in enumerate(quality_keywords)}
        
        # 初始化结果列表
        filtered_urls = []
        
        # FLV优先 - 按照清晰度排序添加
        sorted_flv_qualities = sorted(
            flv_by_quality.keys(), 
            key=lambda q: quality_priority.get(q, 999)  # 未知清晰度排最后
        )
        
        for quality in sorted_flv_qualities:
            # 每个清晰度只取第一个URL
            if flv_by_quality[quality]:
                filtered_urls.append(flv_by_quality[quality][0])
                self.logger.info(f"添加FLV流地址 [{quality}]: {flv_by_quality[quality][0][:100]}...")
        
        # 然后是M3U8 - 按照清晰度排序添加
        sorted_m3u8_qualities = sorted(
            m3u8_by_quality.keys(), 
            key=lambda q: quality_priority.get(q, 999)
        )
        
        for quality in sorted_m3u8_qualities:
            # 每个清晰度只取第一个URL
            if m3u8_by_quality[quality]:
                filtered_urls.append(m3u8_by_quality[quality][0])
                self.logger.info(f"添加M3U8流地址 [{quality}]: {m3u8_by_quality[quality][0][:100]}...")
        
        # 最后添加其他格式（如果有）
        filtered_urls.extend(other_urls)
        
        # 确保至少有一个结果，如果去重和分类后没有找到不同清晰度，就返回原始列表的第一个
        if not filtered_urls and stream_urls:
            filtered_urls = [stream_urls[0]]
            self.logger.warning("未找到不同清晰度的流地址，使用第一个地址")
            
        # 如果清晰度分类后的列表太少，尝试返回原始URL（去重后）
        if len(filtered_urls) < 3 and len(deduped_urls) > len(filtered_urls):
            self.logger.info(f"按清晰度分类只找到 {len(filtered_urls)} 个不同流地址，尝试使用去重后的地址列表")
            filtered_urls = deduped_urls[:10]  # 最多取10个
            
        # 如果列表非常长，只保留前10个
        if len(filtered_urls) > 10:
            self.logger.info(f"流地址过多，只保留前10个最佳质量的地址")
            filtered_urls = filtered_urls[:10]
            
        # 打印筛选结果
        if filtered_urls:
            self.logger.info(f"筛选出最佳流地址: {filtered_urls[0]}")
            self.logger.info(f"共筛选出 {len(filtered_urls)} 个不同清晰度的流地址")
        
        return filtered_urls

    def _extract_stream_url_by_extension_api(self, url):
        """使用抖音直播API直接获取直播流地址"""
        import httpx
        import time
        import random
        import json
        
        self.logger.info("尝试使用抖音直播API提取直播流地址")
        
        # 尝试提取room_id
        room_id = None
        if "live.douyin.com/" in url:
            room_id = url.split("live.douyin.com/")[-1].split("?")[0].strip('/')
            self.logger.info(f"从URL提取到直播ID: {room_id}")
        
        if not room_id:
            self.logger.error("无法从URL中提取直播ID")
            return []
            
        # 生成随机设备ID
        device_id = ''.join(random.choices('0123456789', k=16))
        # 生成随机iid
        iid = ''.join(random.choices('0123456789', k=16))
        
        # 生成时间戳
        timestamp = str(int(time.time()))
        
        # 构建API请求必要参数
        params = {
            "type_id": "0",
            "live_id": "1",
            "room_id": room_id,
            "app_id": "1128",
            "device_platform": "web",
            "aid": "6383",
            "browser_language": "zh-CN",
            "browser_platform": "Linux",
            "browser_name": "Chrome",
            "browser_version": "120.0.0.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "msToken": self._generate_random_mstoken(),
            "device_id": device_id,
            "iid": iid,
            "_signature": self._generate_signature(),
            "verifyFp": self._generate_verify_fp(),
            "timestamp": timestamp
        }
        
        # 构建API URLs
        apis = [
            # 官方API接口
            {
                "url": f"https://live.douyin.com/webcast/room/web/enter/",
                "params": {
                    "aid": "6383",
                    "device_platform": "web",
                    "web_rid": room_id,
                    "live_id": "1",
                    "browser_language": "zh-CN",
                    "browser_name": "Chrome",
                    "browser_version": "120.0.0.0",
                    "msToken": params["msToken"]
                }
            },
            {
                "url": f"https://webcast.amemv.com/webcast/room/reflow/info/",
                "params": {
                    "verifyFp": params["verifyFp"],
                    "type_id": "0",
                    "live_id": "1",
                    "room_id": room_id,
                    "app_id": "1128",
                    "msToken": params["msToken"]
                }
            },
            {
                "url": f"https://live.douyin.com/webcast/room/web/get_play_url/",
                "params": {
                    "aid": "6383",
                    "app_id": "1128",
                    "web_rid": room_id,
                    "device_platform": "web",
                    "live_id": "1",
                    "msToken": params["msToken"]
                }
            },
            {
                "url": f"https://live.douyin.com/webcast/user/live_info/",
                "params": {
                    "aid": "6383",
                    "device_platform": "web",
                    "device_id": params["device_id"],
                    "room_id": room_id,
                    "app_id": "1128",
                    "msToken": params["msToken"]
                }
            },
            {
                "url": f"https://webcast.douyin.com/webcast/room/get_live_room_playback/",
                "params": {
                    "aid": "6383",
                    "app_id": "1128",
                    "browser_name": "Chrome",
                    "browser_version": "120.0.0.0",
                    "device_platform": "web",
                    "room_id": room_id,
                    "msToken": params["msToken"]
                }
            }
        ]
        
        # 生成并替换所有API链接的X-Bogus参数
        for api in apis:
            query_string = "&".join([f"{k}={v}" for k, v in api["params"].items()])
            api["url"] = f"{api['url']}?{query_string}"
        
        base_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://live.douyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://live.douyin.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Content-Type": "application/json;charset=UTF-8",
            "dnt": "1",
            "sec-ch-ua": '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"'
        }
        
        # 添加Cookie（如果有）
        if hasattr(self.parameter, 'cookie') and self.parameter.cookie:
            base_headers["Cookie"] = self.parameter.cookie
            self.logger.info("添加Cookie到请求头")
        
        # 尝试常见的第三方解析API
        try:
            api_url = f"https://tenapi.cn/v2/douyin_live_stream?url={url}"
            self.logger.info(f"尝试第三方API: {api_url}")
            
            third_party_response = httpx.get(
                api_url, 
                headers={"User-Agent": base_headers["User-Agent"]}, 
                timeout=30, 
                follow_redirects=True
            )
            
            if third_party_response.status_code == 200:
                try:
                    data = third_party_response.json()
                    self.logger.info(f"获取到第三方API响应: {str(data)[:200]}...")
                    
                    if "url" in data:
                        stream_url = data["url"]
                        if stream_url and ("http" in stream_url or "rtmp" in stream_url):
                            self.logger.info(f"从第三方API响应提取到流地址: {stream_url}")
                            return [stream_url]
                    elif "data" in data and "url" in data["data"]:
                        stream_url = data["data"]["url"]
                        if stream_url and ("http" in stream_url or "rtmp" in stream_url):
                            self.logger.info(f"从第三方API响应提取到流地址: {stream_url}")
                            return [stream_url]
                except Exception as e:
                    self.logger.error(f"解析第三方API响应失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"请求第三方API失败: {str(e)}")
        
        # 创建客户端会话以便保持cookie
        client = httpx.Client(
            headers=base_headers,
            timeout=30,
            follow_redirects=True
        )
        
        # 首先访问直播页面获取必要的cookie
        try:
            self.logger.info("访问直播页面获取cookie")
            live_page_url = f"https://live.douyin.com/{room_id}"
            client.get(live_page_url)
        except Exception as e:
            self.logger.error(f"访问直播页面失败: {str(e)}")
        
        for api in apis:
            try:
                self.logger.info(f"尝试API: {api['url']}")
                
                # 随机延迟，避免频率限制
                time.sleep(random.uniform(0.5, 1.5))
                
                # 使用会话发送请求
                response = client.get(api["url"])
                
                if response.status_code != 200:
                    self.logger.info(f"API返回状态码: {response.status_code}")
                    continue
                
                # 尝试解析JSON响应
                try:
                    data = response.json()
                    self.logger.info(f"获取到API响应: {str(data)[:200]}...")
                    
                    # 检查错误码
                    if data.get("status_code", 0) != 0:
                        self.logger.warning(f"API返回错误: {data.get('status_code')}, {data.get('message', '')}")
                        continue
                    
                    # 尝试从不同的响应结构中提取流URL
                    stream_url = None
                    
                    # 通用路径尝试
                    paths = [
                        ["data", "stream_url", "flv_pull_url"],
                        ["data", "stream_url", "hls_pull_url_map"],
                        ["data", "room", "stream_url", "flv_pull_url"],
                        ["data", "room", "streams", "flv_pull_url"],
                        ["result", "streamData", "origin", "main", "flv"],
                        ["data", "data", "playUrl"],
                        ["data", "url"],
                        ["url"],
                        ["flv_pull_url"]
                    ]
                    
                    for path in paths:
                        current = data
                        try:
                            for key in path:
                                if isinstance(current, dict) and key in current:
                                    current = current[key]
                                else:
                                    break
                            else:
                                # 完整路径遍历成功
                                if isinstance(current, str) and ("http" in current or "rtmp" in current):
                                    stream_url = current
                                    return [stream_url]  # 直接返回找到的第一个有效URL
                                elif isinstance(current, dict) and len(current) > 0:
                                    # 如果是字典，收集所有URL
                                    url_list = []
                                    for quality, url in current.items():
                                        if isinstance(url, str) and ("http" in url or "rtmp" in url):
                                            url_list.append(url)
                                            self.logger.info(f"找到流地址 [{quality}]: {url}")
                                    
                                    if url_list:
                                        # 如果找到多个URL，进行筛选
                                        return self._filter_best_stream_url(url_list)
                                elif isinstance(current, list) and len(current) > 0:
                                    # 如果是列表，收集所有可能的URL
                                    url_list = []
                                    for item in current:
                                        if isinstance(item, str) and ("http" in item or "rtmp" in item):
                                            url_list.append(item)
                                    
                                    if url_list:
                                        return self._filter_best_stream_url(url_list)
                        except Exception as e:
                            continue
                    
                except ValueError:
                    # 如果不是JSON，尝试从文本中提取URL
                    import re
                    html = response.text
                    patterns = [
                        r'(https?://[^"\']*?pull-flv[^"\']*?\.flv[^"\']*)',
                        r'(https?://[^"\']*?pull-hls[^"\']*?\.m3u8[^"\']*)',
                        r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.flv[^"\']*)',
                        r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.m3u8[^"\']*)',
                        r'(https?://[^"\']+(?:\.flv|\.m3u8)[^"\']*)'
                    ]
                    
                    all_matches = []
                    for pattern in patterns:
                        matches = re.findall(pattern, html)
                        all_matches.extend(matches)
                    
                    if all_matches:
                        self.logger.info(f"从API文本响应中提取到 {len(all_matches)} 个流地址")
                        return self._filter_best_stream_url(all_matches)
            
            except Exception as e:
                self.logger.error(f"API {api['url']} 请求失败: {str(e)}")
        
        # 尝试直接访问直播页面并分析网络请求
        try:
            self.logger.info(f"尝试直接分析直播页面: {url}")
            
            # 直接获取页面HTML
            response = client.get(url)
            html = response.text
            
            # 提取页面中的关键参数
            import re
            
            # 尝试提取stream URL
            stream_url_patterns = [
                r'(https?://[^"\']*?pull-flv[^"\']*?\.flv[^"\']*)',
                r'(https?://[^"\']*?pull-hls[^"\']*?\.m3u8[^"\']*)',
                r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.flv[^"\']*)',
                r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.m3u8[^"\']*)',
                r'(https?://[^"\']+(?:\.flv|\.m3u8)[^"\']*)'
            ]
            
            all_matches = []
            for pattern in stream_url_patterns:
                matches = re.findall(pattern, html)
                all_matches.extend(matches)
            
            if all_matches:
                self.logger.info(f"从直播页面提取到 {len(all_matches)} 个流地址")
                return self._filter_best_stream_url(all_matches)
                
            # 尝试提取其他关键参数
            try:
                room_data_match = re.search(r'room\s*:\s*({[^}]+})', html)
                if room_data_match:
                    room_data_str = room_data_match.group(1)
                    # 尝试修复不完整的JSON
                    room_data_str = room_data_str.replace("'", '"')
                    try:
                        room_data = json.loads(room_data_str)
                        if "stream_url" in room_data:
                            stream_data = room_data["stream_url"]
                            if isinstance(stream_data, dict) and "flv_pull_url" in stream_data:
                                flv_urls = stream_data["flv_pull_url"]
                                if isinstance(flv_urls, dict) and len(flv_urls) > 0:
                                    # 收集所有URL
                                    url_list = []
                                    for quality, url in flv_urls.items():
                                        if isinstance(url, str) and "http" in url:
                                            url_list.append(url)
                                            self.logger.info(f"从页面数据中提取到流地址 [{quality}]: {url}")
                                    
                                    if url_list:
                                        return self._filter_best_stream_url(url_list)
                    except Exception as e:
                        self.logger.error(f"解析房间数据失败: {str(e)}")
            except Exception as e:
                self.logger.error(f"提取房间数据失败: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"分析直播页面失败: {str(e)}")
        
        # 尝试特殊的移动端API
        try:
            mobile_url = f"https://webcast.amemv.com/webcast/room/reflow/info/?verifyFp=&type_id=0&live_id=1&room_id={room_id}&device_platform=android&app_id=1128"
            self.logger.info(f"尝试移动端API: {mobile_url}")
            
            mobile_headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G9900) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "Referer": "https://live.douyin.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }
            
            mobile_response = httpx.get(mobile_url, headers=mobile_headers, timeout=30)
            
            if mobile_response.status_code == 200:
                try:
                    data = mobile_response.json()
                    
                    if "data" in data and "room" in data["data"] and "stream_url" in data["data"]["room"]:
                        stream_data = data["data"]["room"]["stream_url"]
                        flv_urls = stream_data.get("flv_pull_url", {})
                        
                        if isinstance(flv_urls, dict) and len(flv_urls) > 0:
                            # 收集所有URL
                            url_list = []
                            for quality, url in flv_urls.items():
                                if isinstance(url, str) and "http" in url:
                                    url_list.append(url)
                                    self.logger.info(f"从移动端API提取到流地址 [{quality}]: {url}")
                            
                            if url_list:
                                return self._filter_best_stream_url(url_list)
                except Exception as e:
                    self.logger.error(f"解析移动端API响应失败: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"移动端API请求失败: {str(e)}")
        
        self.logger.warning("所有API尝试均未找到流地址")
        return []

    def _extract_stream_url_by_selenium(self, url: str) -> list:
        """使用Selenium提取直播流地址"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            import time
            
            self.logger.info("初始化Selenium提取流地址")
            
            # 设置Chrome选项
            options = Options()
            options.add_argument("--headless")  # 无头模式
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-notifications")  # 禁用通知
            options.add_argument("--window-size=1920,1080")  # 设置窗口大小
            
            # 额外稳定性选项
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--disable-infobars")
            
            # 设置user-agent
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 创建Chrome实例
            driver = webdriver.Chrome(options=options)
            self.logger.info(f"访问直播页面: {url}")
            
            try:
                # 设置页面加载超时
                driver.set_page_load_timeout(60)
                
                # 访问直播页面
                driver.get(url)
                
                # 如果有Cookie，设置Cookie
                if hasattr(self.parameter, 'cookie') and self.parameter.cookie:
                    self.logger.info("添加Cookie到浏览器")
                    # 先访问抖音域名
                    if "douyin.com" not in driver.current_url:
                        driver.get("https://www.douyin.com")
                    
                    # 添加Cookie
                    try:
                        if isinstance(self.parameter.cookie, dict):
                            for name, value in self.parameter.cookie.items():
                                driver.add_cookie({"name": name, "value": value, "domain": ".douyin.com"})
                        elif isinstance(self.parameter.cookie, str):
                            for cookie in self.parameter.cookie.split(';'):
                                if '=' in cookie:
                                    name, value = cookie.strip().split('=', 1)
                                    driver.add_cookie({"name": name, "value": value, "domain": ".douyin.com"})
                        
                        # 刷新页面使Cookie生效
                        driver.refresh()
                    except Exception as e:
                        self.logger.error(f"设置Cookie时出错: {str(e)}")
                
                # 等待页面加载
                self.logger.info("等待页面加载...")
                time.sleep(10)  # 等待10秒
                
                # 检查页面是否加载完成
                page_state = driver.execute_script('return document.readyState;')
                self.logger.info(f"页面加载状态: {page_state}")
                
                # 执行JavaScript获取网络请求
                self.logger.info("执行JavaScript提取流地址")
                stream_urls = driver.execute_script("""
                // 获取所有网络请求
                let streamUrls = [];
                let performanceEntries = performance.getEntriesByType('resource');
                
                // 过滤FLV和M3U8请求
                for (let entry of performanceEntries) {
                    let url = entry.name;
                    if ((url.includes('.flv') || url.includes('.m3u8')) && 
                        (url.includes('pull-flv') || url.includes('pull-hls') || url.includes('douyincdn.com'))) {
                        streamUrls.push(url);
                    }
                }
                
                return streamUrls;
                """)
                
                # 筛选有效的流地址
                valid_urls = []
                for url in stream_urls:
                    if (".flv" in url or ".m3u8" in url) and "douyincdn.com" in url:
                        valid_urls.append(url)
                
                self.logger.info(f"从Selenium提取到 {len(valid_urls)} 个流地址")
                
                # 如果没有找到流地址，尝试从页面源码中提取
                if not valid_urls:
                    self.logger.info("从网络请求中未找到流地址，尝试从页面源码提取")
                    page_source = driver.page_source
                    
                    # 使用正则表达式从页面源码中提取
                    import re
                    patterns = [
                        r'(https?://[^"\']*?pull-flv[^"\']*?\.flv[^"\']*)',
                        r'(https?://[^"\']*?pull-hls[^"\']*?\.m3u8[^"\']*)',
                        r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.flv[^"\']*)',
                        r'(https?://[^"\']*?douyincdn\.com[^"\']*?\.m3u8[^"\']*)',
                        r'(https?://[^"\']+(?:\.flv|\.m3u8)[^"\']*)'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, page_source)
                        valid_urls.extend(matches)
                    
                    self.logger.info(f"从页面源码提取到 {len(valid_urls)} 个流地址")
                
                return valid_urls
                
            except Exception as e:
                self.logger.error(f"Selenium执行过程中出错: {str(e)}")
                return []
                
            finally:
                # 关闭浏览器
                try:
                    driver.quit()
                except:
                    pass  # 忽略关闭时的错误
                
        except ImportError:
            self.logger.error("未安装Selenium，无法使用浏览器提取")
            return []
        except Exception as e:
            self.logger.error(f"Selenium初始化失败: {str(e)}")
            return []

    def deal_live_data(self, url: str) -> dict:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self.logger.info(f"处理直播URL: {url}")

        # 检查直接推流地址
        if "douyincdn.com" in url and (".flv" in url or ".m3u8" in url):
            import re
            stream_id = re.search(r'stream-(\d+)', url).group(1) if re.search(r'stream-(\d+)', url) else "unknown"
            download_cmd = f"ffmpeg -i '{url}' -c copy -f mp4 -bsf:a aac_adtstoasc 直播_{stream_id}.mp4"
            return {
                "text": "直接使用提供的推流地址",
                "flv": {"直接链接": url},
                "m3u8": {},
                "best": url,
                "preview": self.preview,
                "download_cmd": download_cmd,
                "can_download": True
            }
            
        # 提取room_id，用于后续处理
        room_id = None
        if "live.douyin.com/" in url:
            room_id = url.split("live.douyin.com/")[-1].split("?")[0].strip('/')
            self.logger.info(f"从标准URL提取到直播ID: {room_id}")
            
        # 第一步: 尝试使用浏览器插件API (这是最快的方法)
        stream_urls = self._extract_stream_url_by_extension_api(url)
        
        # 第二步: 如果API方法失败，尝试使用yt-dlp
        if not stream_urls:
            self.logger.info("API方法未能提取流地址，尝试使用yt-dlp")
            try:
                import subprocess
                import json
                
                # 检查yt-dlp是否安装
                try:
                    result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
                    self.logger.info(f"检测到yt-dlp版本: {result.stdout.strip()}")
                    
                    # 使用yt-dlp提取流地址
                    result = subprocess.run(
                        ['yt-dlp', '-j', url], 
                        capture_output=True, 
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        if 'url' in data:
                            stream_urls = [data['url']]
                            self.logger.info(f"yt-dlp成功提取到流地址: {stream_urls[0][:100]}...")
                        elif 'formats' in data and len(data['formats']) > 0:
                            # 收集所有格式的URL
                            formats = sorted(data['formats'], key=lambda x: x.get('quality', 0), reverse=True)
                            stream_urls = [f['url'] for f in formats if 'url' in f]
                            self.logger.info(f"yt-dlp成功提取到{len(stream_urls)}个流地址")
                    else:
                        self.logger.warning(f"yt-dlp提取失败: {result.stderr}")
                except FileNotFoundError:
                    self.logger.warning("未安装yt-dlp，跳过此提取方法")
                except Exception as e:
                    self.logger.error(f"使用yt-dlp提取时出错: {str(e)}")
            except Exception as e:
                self.logger.error(f"yt-dlp处理过程中出错: {str(e)}")
        
        # 第三步: 如果前两种方法都失败，并且有room_id和Selenium可用，尝试使用Selenium
        # 安全检查disable_selenium属性是否存在
        disable_selenium = getattr(self.parameter, 'disable_selenium', False)
        
        if not stream_urls and room_id and not disable_selenium:
            self.logger.info("尝试使用Selenium提取直播流地址")
            try:
                stream_urls = self._extract_stream_url_by_selenium(f"https://live.douyin.com/{room_id}")
            except Exception as e:
                self.logger.error(f"Selenium提取过程中出错: {str(e)}")
        
        # 处理提取结果
        if stream_urls:
            try:
                import re
                room_id = room_id or "unknown"
                if not room_id and "stream-" in stream_urls[0]:
                    match = re.search(r'stream-(\d+)', stream_urls[0])
                    if match:
                        room_id = match.group(1)
                
                # 创建适当的响应结构
                # 根据URL类型区分FLV和M3U8
                flv_urls = {}
                m3u8_urls = {}
                
                for i, stream_url in enumerate(stream_urls):
                    if ".flv" in stream_url.lower():
                        quality_name = f"画质-{i+1}" if i > 0 else "最佳画质"
                        flv_urls[quality_name] = stream_url
                    elif ".m3u8" in stream_url.lower():
                        quality_name = f"画质-{i+1}" if i > 0 else "最佳画质"
                        m3u8_urls[quality_name] = stream_url
                
                # 如果没有分类，将第一个地址作为最佳画质
                if not flv_urls and not m3u8_urls and stream_urls:
                    flv_urls["最佳画质"] = stream_urls[0]
                
                # 确保至少有一个地址用于best字段
                best_url = stream_urls[0] if stream_urls else ""
                
                download_cmd = f"ffmpeg -i '{best_url}' -c copy -f mp4 -bsf:a aac_adtstoasc 直播_{room_id}.mp4"
                
                # 添加有用的说明
                explanation = "通过直接分析网页提取到直播流地址" if len(stream_urls) > 10 else "通过API提取到直播流地址"
                if len(stream_urls) > 1:
                    explanation += f"，已筛选出最佳画质，共有 {len(stream_urls)} 个可用流地址"
                
                # 检查流地址是否有效，提供下载帮助信息
                download_help = "\n\n您可以使用以下方法观看/下载直播：\n1. 将流地址粘贴到支持直播的播放器（如VLC、PotPlayer等）\n2. 使用ffmpeg命令录制直播\n3. 使用下载按钮直接下载"
                        
                return {
                    "text": explanation + download_help,
                    "flv": flv_urls,
                    "m3u8": m3u8_urls,
                    "best": best_url,
                    "preview": self.preview,
                    "download_cmd": download_cmd,
                    "can_download": True
                }
            except Exception as e:
                self.logger.error(f"处理提取结果时出错: {str(e)}")
        
        # 所有方法都失败，返回错误信息
        self.logger.error("无法提取直播流地址")
        return {
            "text": "无法提取直播流地址，请检查URL是否正确。如果确认URL正确，可能是直播间已下播或者服务器无法访问。\n\n您可以尝试：\n1. 刷新页面重试\n2. 使用其他工具如yt-dlp直接下载\n3. 检查网络连接是否正常",
            "flv": {},
            "m3u8": {},
            "best": "",
            "preview": self.preview,
            "download_cmd": "",
            "can_download": False
        }

    def run_server(self, app):
        @app.route("/", methods=["GET"])
        def index():
            return render_template(
                "index.html", **self.parameter.get_settings_data(), preview=self.preview
            )

        @app.route("/settings/", methods=["POST"])
        def settings():
            """保存配置并重新加载首页"""
            self.update_settings(request.json, False)
            return url_for("index")

        @app.route("/single/", methods=["POST"])
        def single():
            url = request.json.get("url")
            download = request.json.get("download", False)
            if not url:
                return self.error_works
            return self.deal_single_works(url, download) or self.error_works

        @app.route("/live/", methods=["POST"])
        def live():
            url = request.json.get("url")
            if not url:
                return self.error_live
            return self.deal_live_data(url) or self.error_live

        @app.route("/download_live/", methods=["POST"])
        def download_live():
            url = request.json.get("url")
            if not url:
                return {"success": False, "message": "未提供URL"}
            
            # 获取直播数据
            live_data = self.deal_live_data(url)
            
            if not live_data.get("can_download", False):
                return {"success": False, "message": "无法获取直播流地址"}
            
            # 创建下载任务
            try:
                import subprocess
                
                # 使用子进程执行ffmpeg命令
                cmd = live_data["download_cmd"].split()
                subprocess.Popen(cmd)
                
                return {"success": True, "message": "开始下载直播"}
            except Exception as e:
                return {"success": False, "message": f"下载直播时出错: {str(e)}"}

        @app.route("/extract_live_selenium/", methods=["POST"])
        def extract_live_selenium():
            url = request.json.get("url")
            if not url:
                return {"success": False, "message": "未提供URL"}
            
            try:
                # 处理room_id
                room_id = None
                if "live.douyin.com/" in url:
                    parts = url.split("live.douyin.com/")
                    if len(parts) > 1:
                        room_id = parts[1].split("/")[0].split("?")[0]
                
                if not room_id:
                    return {"success": False, "message": "无法提取直播间ID"}
                
                # 使用Selenium提取
                stream_urls = self._extract_stream_url_by_selenium(f"https://live.douyin.com/{room_id}")
                
                if not stream_urls:
                    return {"success": False, "message": "未找到推流地址"}
                
                return {
                    "success": True, 
                    "stream_url": stream_urls[0],
                    "message": "成功提取推流地址"
                }
            
            except Exception as e:
                return {"success": False, "message": f"提取失败: {str(e)}"}

        return app

    def _generate_random_mstoken(self):
        """生成随机的msToken"""
        import random
        import string
        
        # 生成24-28位随机字符串
        length = random.randint(24, 28)
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _generate_signature(self):
        """生成随机的_signature参数"""
        import random
        import string
        
        # 生成21位随机字符串，格式类似: _02B4Z6wo00f01N.CzQQAAIDC5shP-oFzqYj1PuD1J3t1IANNlQ7vUQdJZo9nlHrPSW-gL9oP8QO1rVbKGFJ2NQ5zRWG4hTbKjymA2w9HrwadnGQH2zKy.wIbmvkbHrrg11
        prefix = "_02B4Z6wo00"
        middle_length = 80
        middle_chars = string.ascii_letters + string.digits + "-_."
        return prefix + ''.join(random.choice(middle_chars) for _ in range(middle_length))
    
    def _generate_verify_fp(self):
        """生成随机的verifyFp参数"""
        import random
        import string
        import time
        
        # 生成类似: verify_lew7v4p5_V9JeEiVz_fFWM_4PYG_9sGB_etc...的字符串
        prefix = "verify_"
        timestamp = hex(int(time.time()))[2:]  # 十六进制时间戳，不带0x前缀
        middle = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        parts = []
        
        for _ in range(5):
            length = random.randint(4, 8)
            parts.append(''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length)))
        
        return f"{prefix}{middle}_{timestamp}_{'_'.join(parts)}"
