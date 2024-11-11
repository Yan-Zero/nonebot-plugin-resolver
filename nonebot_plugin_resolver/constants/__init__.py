from .ncm import NETEASE_API_CN  # noqa: F401
from .ncm import NETEASE_TEMP_API  # noqa: F401
from .xhs import XHS_REQ_LINK  # noqa: F401
from .bili import BILIBILI_HEADER  # noqa: F401
from .kugou import KUGOU_TEMP_API  # noqa: F401
from .weibo import WEIBO_SINGLE_INFO  # noqa: F401
from .tiktok import TIKTOK_VIDEO  # noqa: F401
from .tiktok import DOUYIN_VIDEO  # noqa: F401
from .tiktok import DY_TOUTIAO_INFO  # noqa: F401
from .tiktok import URL_TYPE_CODE_DICT  # noqa: F401

"""
通用解析
"""
GENERAL_REQ_LINK = "http://47.99.158.118/video-crack/v2/parse?content={}"

"""
通用头请求
"""
COMMON_HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 "
    "UBrowser/6.2.4098.3 Safari/537.36"
}

"""
视频最大大小（MB）
"""
VIDEO_MAX_MB = 100

"""
解析关闭名单
"""
RESOLVE_SHUTDOWN_LIST_PICKLE_PATH = "./data/resolver/resolver_shutdown_list.pkl"
