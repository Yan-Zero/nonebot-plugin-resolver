import os
import execjs
import urllib.parse


def generate_x_bogus_url(url, headers):
    """生成抖音A-Bogus签名
    :param url: 视频链接
    :return: 包含X-Bogus签名的URL
    """
    # 调用JavaScript函数
    query = urllib.parse.urlparse(url).query
    abogus_file_path = f"{os.path.dirname(os.path.abspath(__file__))}/a-bogus.js"
    with open(abogus_file_path, "r", encoding="utf-8") as abogus_file:
        abogus_file_path_transcoding = abogus_file.read()
    abogus = execjs.compile(abogus_file_path_transcoding).call(
        "generate_a_bogus", query, headers["User-Agent"]
    )
    # logger.info('生成的A-Bogus签名为: {}'.format(abogus))
    return url + "&a_bogus=" + abogus
