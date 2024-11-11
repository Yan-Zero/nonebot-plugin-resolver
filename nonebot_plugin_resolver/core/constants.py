GENERAL_REQ_LINK = "http://47.99.158.118/video-crack/v2/parse?content={}"
""" 通用解析 """

COMMON_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 "
    "UBrowser/6.2.4098.3 Safari/537.36"
}
""" 通用头请求 """

VIDEO_MAX_MB = 100
""" 视频最大大小（MB） """

BILIBILI_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 "
    "Safari/537.36",
    "referer": "https://www.bilibili.com",
}
""" 哔哩哔哩的头请求 """

WEIBO_SINGLE_INFO = "https://m.weibo.cn/statuses/show?id={}"
""" 微博单条信息 """

XHS_REQ_LINK = "https://www.xiaohongshu.com/explore/"
""" 小红书下载链接 """

NETEASE_API_CN = "https://www.markingchen.ink"
""" NCM获取歌曲信息链接 """

NETEASE_TEMP_API = "https://api.lolimi.cn/API/wydg/api.php?msg={}&n=1"
""" NCM临时接口 """

KUGOU_TEMP_API = "https://www.hhlqilongzhu.cn/api/dg_kgmusic.php?gm={}&n=1&type=json"
""" KG临时接口 """


DY_URL_TYPE_CODE_DICT = {
    # 抖音/Douyin
    2: "image",
    4: "video",
    68: "image",
    # TikTok
    0: "video",
    51: "video",
    55: "video",
    58: "video",
    61: "video",
    150: "image",
}

DOUYIN_VIDEO = "https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={}&pc_client_type=1&version_code=190500&version_name=19.5.0&cookie_enabled=true&screen_width=1344&screen_height=756&browser_language=zh-CN&browser_platform=Win32&browser_name=Firefox&browser_version=118.0&browser_online=true&engine_name=Gecko&engine_version=109.0&os_name=Windows&os_version=10&cpu_core_num=16&device_memory=&platform=PC"
"""dy视频信息"""


DY_TOUTIAO_INFO = (
    "https://aweme.snssdk.com/aweme/v1/play/?video_id={}&ratio=1080p&line=0"
)
"""今日头条 DY API"""


TIKTOK_VIDEO = "https://api22-normal-c-alisg.tiktokv.com/aweme/v1/feed/"
"""tiktok视频信息"""
