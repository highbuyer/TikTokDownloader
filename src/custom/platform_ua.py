"""
平台检测和User-Agent生成模块
"""
import platform
import sys

def get_platform_info():
    """
    获取当前平台的完整browser_info配置
    
    返回:
        dict: 包含Windows、Mac和Linux三种平台的browser_info和browser_info_tiktok配置
    """
    chrome_version = "131.0.0.0"  # 最新Chrome版本
    
    # Windows平台配置
    windows_ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    windows_browser_info = {
        "User-Agent": windows_ua,
        "pc_libra_divert": "Windows",
        "browser_platform": "Win32",
        "browser_name": "Chrome",
        "browser_version": chrome_version,
        "engine_name": "Blink",
        "engine_version": chrome_version,
        "os_name": "Windows",
        "os_version": "10",
        "webid": ""
    }
    windows_browser_info_tiktok = {
        "User-Agent": windows_ua,
        "app_language": "zh-Hans",
        "browser_language": "zh-CN",
        "browser_name": "Mozilla",
        "browser_platform": "Win32",
        "browser_version": f"5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        "language": "zh-Hans",
        "os": "windows",
        "priority_region": "CN",
        "region": "CN",
        "tz_name": "Asia/Shanghai",
        "webcast_language": "zh-Hans",
        "device_id": ""
    }
    
    # Mac平台配置
    mac_ua = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    mac_browser_info = {
        "User-Agent": mac_ua,
        "pc_libra_divert": "macOS",
        "browser_platform": "MacIntel",
        "browser_name": "Chrome",
        "browser_version": chrome_version,
        "engine_name": "Blink",
        "engine_version": chrome_version,
        "os_name": "macOS",
        "os_version": "10_15_7",
        "webid": ""
    }
    mac_browser_info_tiktok = {
        "User-Agent": mac_ua,
        "app_language": "zh-Hans",
        "browser_language": "zh-CN",
        "browser_name": "Mozilla",
        "browser_platform": "MacIntel",
        "browser_version": f"5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        "language": "zh-Hans",
        "os": "mac",
        "priority_region": "CN",
        "region": "CN",
        "tz_name": "Asia/Shanghai",
        "webcast_language": "zh-Hans",
        "device_id": ""
    }
    
    # Linux平台配置
    linux_ua = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    linux_browser_info = {
        "User-Agent": linux_ua,
        "pc_libra_divert": "Linux",
        "browser_platform": "Linux x86_64",
        "browser_name": "Chrome",
        "browser_version": chrome_version,
        "engine_name": "Blink",
        "engine_version": chrome_version,
        "os_name": "Linux",
        "os_version": "x86_64",
        "webid": ""
    }
    linux_browser_info_tiktok = {
        "User-Agent": linux_ua,
        "app_language": "zh-Hans",
        "browser_language": "zh-CN",
        "browser_name": "Mozilla",
        "browser_platform": "Linux x86_64",
        "browser_version": f"5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        "language": "zh-Hans",
        "os": "linux",
        "priority_region": "CN",
        "region": "CN",
        "tz_name": "Asia/Shanghai",
        "webcast_language": "zh-Hans",
        "device_id": ""
    }
    
    return {
        "windows": {
            "browser_info": windows_browser_info,
            "browser_info_tiktok": windows_browser_info_tiktok
        },
        "darwin": {  # macOS
            "browser_info": mac_browser_info,
            "browser_info_tiktok": mac_browser_info_tiktok
        },
        "linux": {
            "browser_info": linux_browser_info,
            "browser_info_tiktok": linux_browser_info_tiktok
        }
    }

def get_current_platform():
    """
    获取当前操作系统平台
    
    返回:
        str: 'windows', 'darwin' 或 'linux'
    """
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system == 'darwin':  # macOS
        return 'darwin'
    else:  # Linux 和其他平台
        return 'linux'

def update_settings_with_platform_ua(settings):
    """
    根据当前平台更新settings中的browser_info和browser_info_tiktok
    
    参数:
        settings: dict 设置字典
    
    返回:
        dict: 更新后的设置字典
    """
    platform_info = get_platform_info()
    current_platform = get_current_platform()
    
    # 获取当前平台的浏览器信息配置
    if current_platform in platform_info:
        platform_config = platform_info[current_platform]
        
        # 更新抖音平台的browser_info
        if 'browser_info' in settings and isinstance(settings['browser_info'], dict):
            settings['browser_info'] = platform_config['browser_info'].copy()
        
        # 更新TikTok平台的browser_info_tiktok
        if 'browser_info_tiktok' in settings and isinstance(settings['browser_info_tiktok'], dict):
            settings['browser_info_tiktok'] = platform_config['browser_info_tiktok'].copy()
            
        # 确保保留原始proxy和timeout设置
        if 'proxy' in settings and settings['proxy'] is not None:
            settings['proxy'] = settings['proxy']
        if 'proxy_tiktok' in settings and settings['proxy_tiktok'] is not None:
            settings['proxy_tiktok'] = settings['proxy_tiktok']
        if 'timeout' in settings and isinstance(settings['timeout'], (int, float)):
            settings['timeout'] = settings['timeout']
    
    return settings 