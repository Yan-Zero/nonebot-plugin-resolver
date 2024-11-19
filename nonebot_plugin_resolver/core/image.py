import os
import aiohttp

import nonebot

nonebot.require("nonebot_plugin_htmlrender")

from nonebot_plugin_htmlrender import (  # noqa: E402
    md_to_pic,
)

markdown_to_image = md_to_pic


async def download_img(
    url: str, path: str = "", proxy: str = None, session=None, headers=None
) -> str:
    """
    异步下载（aiohttp）网络图片，并支持通过代理下载。
    如果未指定path，则图片将保存在当前工作目录并以图片的文件名命名。
    如果提供了代理地址，则会通过该代理下载图片。

    :param url: 要下载的图片的URL。
    :param path: 图片保存的路径。如果为空，则保存在当前目录。
    :param proxy: 可选，下载图片时使用的代理服务器的URL。
    :return: 保存图片的路径。
    """
    if path == "":
        path = os.path.join(os.getcwd(), url.split("/").pop())
    # 单个文件下载
    if session is None:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, headers=headers) as response:
                if response.status == 200:
                    data = await response.read()
                    with open(path, "wb") as f:
                        f.write(data)
    # 多个文件异步下载
    else:
        async with session.get(url, proxy=proxy, headers=headers) as response:
            if response.status == 200:
                data = await response.read()
                with open(path, "wb") as f:
                    f.write(data)
    return path
