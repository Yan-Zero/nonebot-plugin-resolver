import asyncio
import os
import time
import tempfile
from typing import List, Dict


import aiofiles
import aiohttp
import httpx

from .constants import COMMON_HEADER


async def download_video(url, proxy: str = None, ext_headers=None) -> str:
    """
    异步下载（httpx）视频，并支持通过代理下载。
    文件名将使用时间戳生成，以确保唯一性。
    如果提供了代理地址，则会通过该代理下载视频。

    :param ext_headers:
    :param url: 要下载的视频的URL。
    :param proxy: 可选，下载视频时使用的代理服务器的URL。
    :return: 保存视频的路径。
    """
    # 使用时间戳生成文件名，确保唯一性
    path = os.path.join(os.getcwd(), f"{int(time.time())}.mp4")

    # 判断 ext_headers 是否为 None
    if ext_headers is None:
        headers = COMMON_HEADER
    else:
        # 使用 update 方法合并两个字典
        headers = COMMON_HEADER.copy()  # 先复制 COMMON_HEADER
        headers.update(ext_headers)  # 然后更新 ext_headers

    # 配置代理
    client_config = {
        "headers": headers,
        "timeout": httpx.Timeout(60, connect=5.0),
        "follow_redirects": True,
    }
    if proxy:
        client_config["proxies"] = {"https": proxy}

    # 下载文件
    try:
        async with httpx.AsyncClient(**client_config) as client:
            async with client.stream("GET", url) as resp:
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        await f.write(chunk)
        return path
    except Exception as e:
        print(f"下载视频错误原因是: {e}")
        return None


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


async def download_file(url) -> bytes:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def convert_to_wav(file_bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False) as input_temp_file:
        input_temp_file.write(file_bytes)
        input_temp_file_path = input_temp_file.name

    output_temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output_temp_file_path = output_temp_file.name
    output_temp_file.close()

    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            input_temp_file_path,
            output_temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"ffmpeg failed: {stderr.decode()}")

        with open(output_temp_file_path, "rb") as mp3_file:
            mp3_data = mp3_file.read()
    finally:
        os.remove(input_temp_file_path)
        os.remove(output_temp_file_path)
    return mp3_data


def remove_files(file_paths: List[str]) -> Dict[str, str]:
    """
    根据路径删除文件

    Parameters:
    *file_paths (str): 要删除的一个或多个文件路径

    Returns:
    dict: 一个以文件路径为键、删除状态为值的字典
    """
    results = {}

    for file_path in file_paths:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                results[file_path] = "remove"
            except Exception as e:
                results[file_path] = f"error: {e}"
        else:
            results[file_path] = "don't exist"

    return results


def get_file_size_mb(file_path):
    """
    判断当前文件的大小是多少MB
    :param file_path:
    :return:
    """
    # 获取文件大小（以字节为单位）
    file_size_bytes = os.path.getsize(file_path)

    # 将字节转换为 MB 并取整
    file_size_mb = int(file_size_bytes / (1024 * 1024))

    return file_size_mb
