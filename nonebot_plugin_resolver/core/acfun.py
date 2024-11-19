import json
import re
import subprocess
import os
import httpx

from .constants import COMMON_HEADER

HEADERS = {"referer": "https://www.acfun.cn/", **COMMON_HEADER}


def parse_ac_url(url: str) -> tuple[str, str, dict]:
    """解析acfun链接"""
    url_suffix = "?quickViewId=videoInfo_new&ajaxpipe=1"
    url = url + url_suffix

    raw = httpx.get(url, headers=HEADERS).text
    strs_remove_header = raw.split("window.pageInfo = window.videoInfo =")
    strs_remove_tail = strs_remove_header[1].split("</script>")
    str_json = strs_remove_tail[0]
    str_json_escaped = escape_special_chars(str_json)
    video_info = json.loads(str_json_escaped)

    """校准文件名"""
    ac_id = "ac" + video_info["dougaId"] if video_info["dougaId"] is not None else ""
    title = video_info["title"] if video_info["title"] is not None else ""
    author = (
        video_info["user"]["name"] if video_info["user"]["name"] is not None else ""
    )
    upload_time = (
        video_info["createTime"] if video_info["createTime"] is not None else ""
    )
    desc = video_info["description"] if video_info["description"] is not None else ""
    video_name = "_".join([ac_id, title, author, upload_time, desc])[:101].replace(
        " ", "-"
    )

    ks_play_json = video_info["currentVideoInfo"]["ksPlayJson"]
    ks_play = json.loads(ks_play_json)
    representations = ks_play["adaptationSet"][0]["representation"]
    url_m3u8s = [d["url"] for d in representations][3]
    return url_m3u8s, video_name, video_info


def parse_m3u8(m3u8_url: str):
    """解析m3u8链接"""
    m3u8_relative_links = re.split(
        r"\n#EXTINF:.{8},\n", httpx.get(m3u8_url, headers=HEADERS).text
    )[1:]
    # 修改尾部 去掉尾部多余的结束符
    patched_tail = m3u8_relative_links[-1].split("\n")[0]
    m3u8_relative_links[-1] = patched_tail

    # 完整链接，直接加m3u8Url的通用前缀
    # aria2c下载的文件名，就是取url最后一段，去掉末尾url参数(?之后是url参数)
    ts_names = [d.split("?")[0] for d in m3u8_relative_links]
    return (
        ["/".join(m3u8_url.split("/")[0:-1]) + "/" + d for d in m3u8_relative_links],
        ts_names,
        ts_names[0][:-9],
        ts_names[0][:-9] + ".mp4",
    )


async def download_m3u8_videos(m3u8_full_url, i):
    """批量下载m3u8"""
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", m3u8_full_url, headers=HEADERS) as resp:
            with open(f"{i}.ts", "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)


def escape_special_chars(str_json):
    return str_json.replace('\\\\"', '\\"').replace('\\"', '"')


def merge_ac_file_to_mp4(ts_names, full_file_name, should_delete=True):
    concat_str = "\n".join([f"file {i}.ts" for i, d in enumerate(ts_names)])
    with open("file.txt", "w") as f:
        f.write(concat_str)

    subprocess.call(
        f'ffmpeg -y -f concat -safe 0 -i "file.txt" -c copy "{full_file_name}"',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if should_delete:
        os.unlink("file.txt")
        for i in range(len(ts_names)):
            os.unlink(f"{i}.ts")
