import os
import re
import json
import pathlib
import asyncio
import httpx
import aiohttp

from typing import Iterable
from urllib.parse import urlparse, parse_qs

from bilibili_api import video, Credential, live, article
from bilibili_api.favorite_list import get_video_favorite_list_content
from bilibili_api.opus import Opus
from bilibili_api.video import VideoDownloadURLDataDetecter
from nonebot import on_regex, logger, get_plugin_config
from nonebot.adapters.onebot.v11 import (
    Message,
    Event,
    Bot,
    MessageSegment,
)
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, PrivateMessageEvent
from nonebot.plugin import PluginMetadata

from .config import Config
from .core.constants import (
    COMMON_HEADER,
    DY_URL_TYPE_CODE_DICT,
    DOUYIN_VIDEO,
    GENERAL_REQ_LINK,
    XHS_REQ_LINK,
    DY_TOUTIAO_INFO,
    BILIBILI_HEADER,
    NETEASE_API_CN,
    NETEASE_TEMP_API,
    VIDEO_MAX_MB,
    WEIBO_SINGLE_INFO,
    KUGOU_TEMP_API,
)
from .core import (
    download_img,
    download_file,
    remove_files,
    download_video,
    convert_to_wav,
    get_file_size_mb,
)
from .core.acfun import (
    parse_url,
    download_m3u8_videos,
    parse_m3u8,
    merge_ac_file_to_mp4,
)
from .core.bili23 import download_b_file, merge_file_to_mp4, extra_bili_info
from .core.tiktok import generate_x_bogus_url
from .core.ytdlp import get_video_title, download_ytb_video
from .core.weibo import mid2id

__plugin_meta__ = PluginMetadata(
    name="链接分享解析器",
    description="NoneBot2链接分享解析器插件。解析视频、图片链接/小程序插件，tiktok、bilibili、twitter等实时发送！",
    usage="分享链接即可体验到效果",
    type="application",
    homepage="https://github.com/Yan-Zero/nonebot-plugin-resolver",
    config=Config,
    supported_adapters={"~onebot.v11", "~qq"},
)

# 配置加载
GLOBAL_CONFIG = get_plugin_config(Config)
# 全局名称
GLOBAL_NICKNAME: str = str(getattr(GLOBAL_CONFIG, "r_global_nickname", ""))
# 🪜地址
RESOLVER_PROXY: str = getattr(GLOBAL_CONFIG, "resolver_proxy", "http://127.0.0.1:7890")
# 是否是海外服务器
IS_OVERSEA: bool = bool(getattr(GLOBAL_CONFIG, "is_oversea", False))
# 哔哩哔哩限制的最大视频时长（默认8分钟），单位：秒
VIDEO_DURATION_MAXIMUM: int = int(getattr(GLOBAL_CONFIG, "video_duration_maximum", 480))
# 哔哩哔哩的 SESSDATA
BILI_SESSDATA: str = str(getattr(GLOBAL_CONFIG, "bili_sessdata", ""))
# 构建哔哩哔哩的Credential
credential = Credential(sessdata=BILI_SESSDATA)

bili23 = on_regex(r"(.*)(bilibili.com|b23.tv|BV[0-9a-zA-Z]{10})", priority=1)
douyin = on_regex(r"(.*)(v.douyin.com)", priority=1)
tik = on_regex(r"(.*)(www.tiktok.com)|(vt.tiktok.com)|(vm.tiktok.com)", priority=1)
acfun = on_regex(r"(.*)(acfun.cn)")
twit = on_regex(r"(.*)(x.com)", priority=1)
xhs = on_regex(r"(.*)(xhslink.com|xiaohongshu.com)", priority=1)
y2b = on_regex(r"(.*)(youtube.com|youtu.be)", priority=1)
ncm = on_regex(r"(.*)(music.163.com|163cn.tv)")
weibo = on_regex(r"(.*)(weibo.com|m.weibo.cn)")
kg = on_regex(r"(.*)(kugou.com)")


@bili23.handle()
async def bilibili(bot: Bot, event: Event) -> None:
    """
        哔哩哔哩解析
    :param bot:
    :param event:
    :return:
    """
    # 消息
    url: str = str(event.get_message()).strip()
    # 正则匹配
    url_reg = (
        r"(http:|https:)\/\/(space|www|live).bilibili.com\/[A-Za-z\d._?%&+\-=\/#]*"
    )
    b_short_rex = r"(http:|https:)\/\/b23.tv\/[A-Za-z\d._?%&+\-=\/#]*"
    # BV处理
    if re.match(r"^BV[1-9a-zA-Z]{10}$", url):
        url = "https://www.bilibili.com/video/" + url
    # 处理短号、小程序问题
    if "b23.tv" in url or ("b23.tv" and "QQ小程序" in url):
        b_short_url = re.search(b_short_rex, url.replace("\\", ""))[0]
        resp = httpx.get(b_short_url, headers=BILIBILI_HEADER, follow_redirects=True)
        url: str = str(resp.url)
    else:
        url: str = re.search(url_reg, url).group(0)
    # ===============发现解析的是动态，转移一下===============
    if ("t.bilibili.com" in url or "/opus" in url) and BILI_SESSDATA != "":
        # 去除多余的参数
        if "?" in url:
            url = url[: url.index("?")]
        dynamic_id = int(re.search(r"[^/]+(?!.*/)", url)[0])
        dynamic_info = await Opus(dynamic_id, credential).get_info()
        # 这里比较复杂，暂时不用管，使用下面这个算法即可实现哔哩哔哩动态转发
        if dynamic_info is not None:
            title = dynamic_info["item"]["basic"]["title"]
            paragraphs = []
            for module in dynamic_info["item"]["modules"]:
                if "module_content" in module:
                    paragraphs = module["module_content"]["paragraphs"]
                    break
            desc = paragraphs[0]["text"]["nodes"][0]["word"]["words"]
            pics = paragraphs[1]["pic"]["pics"]
            await bili23.send(
                Message(f"{GLOBAL_NICKNAME}识别：B站动态，{title}\n{desc}")
            )
            send_pics = []
            for pic in pics:
                img = pic["url"]
                send_pics.append(
                    make_node_segment(bot.self_id, MessageSegment.image(img))
                )
            # 发送异步后的数据
            await send_forward_both(bot, event, send_pics)
        return
    # 直播间识别
    if "live" in url:
        # https://live.bilibili.com/30528999?hotRank=0
        room_id = re.search(r"\/(\d+)$", url).group(1)
        room = live.LiveRoom(room_display_id=int(room_id))
        room_info = (await room.get_room_info())["room_info"]
        title, cover, keyframe = (
            room_info["title"],
            room_info["cover"],
            room_info["keyframe"],
        )
        await bili23.send(
            Message(
                [
                    MessageSegment.image(cover),
                    MessageSegment.image(keyframe),
                    MessageSegment.text(
                        f"{GLOBAL_NICKNAME}识别：哔哩哔哩直播，{title}"
                    ),
                ]
            )
        )
        return
    # 专栏识别
    if "read" in url:
        read_id = re.search(r"read\/cv(\d+)", url).group(1)
        ar = article.Article(read_id)
        # 如果专栏为公开笔记，则转换为笔记类
        # NOTE: 笔记类的函数与专栏类的函数基本一致
        if ar.is_note():
            ar = ar.turn_to_note()
        # 加载内容
        await ar.fetch_content()
        markdown_path = f"{os.getcwd()}/article.md"
        with open(markdown_path, "w", encoding="utf8") as f:
            f.write(ar.markdown())
        await bili23.send(Message(f"{GLOBAL_NICKNAME}识别：哔哩哔哩专栏"))
        await bili23.send(
            Message(MessageSegment(type="file", data={"file": markdown_path}))
        )
        return
    # 收藏夹识别
    if "favlist" in url and BILI_SESSDATA != "":
        # https://space.bilibili.com/22990202/favlist?fid=2344812202
        fav_id = re.search(r"favlist\?fid=(\d+)", url).group(1)
        fav_list = (await get_video_favorite_list_content(fav_id))["medias"][:10]
        favs = []
        for fav in fav_list:
            title, cover, intro, link = (
                fav["title"],
                fav["cover"],
                fav["intro"],
                fav["link"],
            )
            logger.info(title, cover, intro)
            favs.append(
                [
                    MessageSegment.image(cover),
                    MessageSegment.text(
                        f"🧉 标题：{title}\n📝 简介：{intro}\n🔗 链接：{link}"
                    ),
                ]
            )
        await bili23.send(
            f"{GLOBAL_NICKNAME}识别：哔哩哔哩收藏夹，正在为你找出相关链接请稍等..."
        )
        await bili23.send(make_node_segment(bot.self_id, favs))
        return
    # 获取视频信息
    video_id = re.search(r"video\/[^\?\/ ]+", url)[0].split("/")[1]
    v = video.Video(video_id, credential=credential)
    video_info = await v.get_info()
    if video_info is None:
        await bili23.send(Message(f"{GLOBAL_NICKNAME}识别：B站，出错，无法获取数据！"))
        return
    video_title, video_cover, video_desc, video_duration = (
        video_info["title"],
        video_info["pic"],
        video_info["desc"],
        video_info["duration"],
    )
    # 校准 分p 的情况
    page_num = 0
    if "pages" in video_info:
        # 解析URL
        parsed_url = urlparse(url)
        # 检查是否有查询字符串
        if parsed_url.query:
            # 解析查询字符串中的参数
            query_params = parse_qs(parsed_url.query)
            # 获取指定参数的值，如果参数不存在，则返回None
            page_num = int(query_params.get("p", [1])[0]) - 1
        else:
            page_num = 0
        if "duration" in video_info["pages"][page_num]:
            video_duration = video_info["pages"][page_num].get(
                "duration", video_info.get("duration")
            )
        else:
            # 如果索引超出范围，使用 video_info['duration'] 或者其他默认值
            video_duration = video_info.get("duration", 0)
    # 截断下载时间比较长的视频
    online = await v.get_online()
    online_str = (
        f'🏄‍♂️ 总共 {online["total"]} 人在观看，{online["count"]} 人在网页端观看'
        + (
            f"\n🔗 链接：https://www.bilibili.com/video/av{video_info['aid']}"
            if "aid" in video_info
            else ""
        )
    )
    if video_duration > VIDEO_DURATION_MAXIMUM or not GLOBAL_CONFIG.download_video:
        return await bili23.finish(
            Message(MessageSegment.image(video_cover))
            + Message(
                f"\n{GLOBAL_NICKNAME}识别：B站，{video_title}\n{extra_bili_info(video_info)}\n📝 简介：{video_desc}\n{online_str}"
            )
        )
    await bili23.send(
        Message(MessageSegment.image(video_cover))
        + Message(
            f"\n{GLOBAL_NICKNAME}识别：B站，{video_title}\n{extra_bili_info(video_info)}\n📝 简介：{video_desc}\n{online_str}"
        )
    )
    # 获取下载链接
    logger.info(page_num)
    download_url_data = await v.get_download_url(page_index=page_num)
    detecter = VideoDownloadURLDataDetecter(download_url_data)
    streams = detecter.detect_best_streams()
    video_url, audio_url = streams[0].url, streams[1].url
    # 下载视频和音频
    path = os.getcwd() + "/" + video_id
    try:
        await asyncio.gather(
            download_b_file(video_url, f"{path}-video.m4s", logger.info),
            download_b_file(audio_url, f"{path}-audio.m4s", logger.info),
        )
        merge_file_to_mp4(
            f"{video_id}-video.m4s", f"{video_id}-audio.m4s", f"{path}-res.mp4"
        )
    finally:
        remove_res = remove_files([f"{video_id}-video.m4s", f"{video_id}-audio.m4s"])
        logger.info(remove_res)
    # 发送出去
    # await bili23.send(Message(MessageSegment.video(f"{path}-res.mp4")))
    await auto_video_send(bot, event, f"{path}-res.mp4")
    # 这里是总结内容，如果写了cookie就可以
    if BILI_SESSDATA != "":
        ai_conclusion = await v.get_ai_conclusion(await v.get_cid(0))
        if ai_conclusion["model_result"]["summary"] != "":
            send_forword_summary = make_node_segment(
                bot.self_id,
                ["bilibili AI总结", ai_conclusion["model_result"]["summary"]],
            )
            await bili23.send(Message(send_forword_summary))


@douyin.handle()
async def dy(bot: Bot, event: Event) -> None:
    """
        抖音解析
    :param bot:
    :param event:
    :return:
    """
    # 消息
    msg: str = str(event.get_message()).strip()
    logger.info(msg)
    # 正则匹配
    reg = r"(http:|https:)\/\/v.douyin.com\/[A-Za-z\d._?%&+\-=#]*"
    dou_url = re.search(reg, msg, re.I)[0]
    dou_url_2 = httpx.get(dou_url).headers.get("location")
    # logger.error(dou_url_2)
    reg2 = r".*(video|note)\/(\d+)\/(.*?)"
    # 获取到ID
    dou_id = re.search(reg2, dou_url_2, re.I)[2]
    # logger.info(dou_id)
    # 如果没有设置dy的ck就结束，因为获取不到
    douyin_ck = getattr(GLOBAL_CONFIG, "douyin_ck", "")
    if douyin_ck == "":
        logger.error(GLOBAL_CONFIG)
        await douyin.send(
            Message(f"{GLOBAL_NICKNAME}识别：抖音，无法获取到管理员设置的抖音ck！")
        )
        return
    # API、一些后续要用到的参数
    headers = {
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "referer": f"https://www.douyin.com/video/{dou_id}",
        "cookie": douyin_ck,
    } | COMMON_HEADER
    api_url = DOUYIN_VIDEO.format(dou_id)
    api_url = generate_x_bogus_url(api_url, headers)  # 如果请求失败直接返回
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers, timeout=10) as response:
            detail = await response.json()
            if detail is None:
                await douyin.send(Message(f"{GLOBAL_NICKNAME}识别：抖音，解析失败！"))
                return
            # 获取信息
            detail = detail["aweme_detail"]
            # 判断是图片还是视频
            url_type_code = detail["aweme_type"]
            url_type = DY_URL_TYPE_CODE_DICT.get(url_type_code, "video")
            await douyin.send(
                Message(f"{GLOBAL_NICKNAME}识别：抖音，{detail.get('desc')}")
            )
            # 根据类型进行发送
            if url_type == "video":
                # 识别播放地址
                player_uri = detail.get("video").get("play_addr")["uri"]
                player_real_addr = DY_TOUTIAO_INFO.format(player_uri)
                # 发送视频
                # await douyin.send(Message(MessageSegment.video(player_addr)))
                await auto_video_send(bot, event, player_real_addr)
            elif url_type == "image":
                # 无水印图片列表/No watermark image list
                no_watermark_image_list = []
                # 有水印图片列表/With watermark image list
                # 遍历图片列表/Traverse image list
                for i in detail["images"]:
                    # 无水印图片列表
                    # no_watermark_image_list.append(i['url_list'][0])
                    no_watermark_image_list.append(
                        MessageSegment.image(i["url_list"][0])
                    )
                    # 有水印图片列表
                    # watermark_image_list.append(i['download_url_list'][0])
                # imgList = await asyncio.gather([])
                await send_forward_both(
                    bot, event, make_node_segment(bot.self_id, no_watermark_image_list)
                )


@tik.handle()
async def tiktok(bot: Bot, event: Event) -> None:
    """
        tiktok解析
    :param event:
    :return:
    """
    # 消息
    url: str = str(event.get_message()).strip()

    # 海外服务器判断
    proxy = None if IS_OVERSEA else RESOLVER_PROXY

    url_reg = r"(http:|https:)\/\/www.tiktok.com\/[A-Za-z\d._?%&+\-=\/#@]*"
    url_short_reg = r"(http:|https:)\/\/vt.tiktok.com\/[A-Za-z\d._?%&+\-=\/#]*"
    url_short_reg2 = r"(http:|https:)\/\/vm.tiktok.com\/[A-Za-z\d._?%&+\-=\/#]*"

    if "vt.tiktok" in url:
        temp_url = re.search(url_short_reg, url)[0]
        temp_resp = httpx.get(temp_url, follow_redirects=True, proxies=proxy)
        url = temp_resp.url
    elif "vm.tiktok" in url:
        temp_url = re.search(url_short_reg2, url)[0]
        temp_resp = httpx.get(
            temp_url,
            headers={"User-Agent": "facebookexternalhit/1.1"},
            follow_redirects=True,
            proxies=proxy,
        )
        url = str(temp_resp.url)
    else:
        url = re.search(url_reg, url)[0]
    title = get_video_title(url, IS_OVERSEA, RESOLVER_PROXY)

    await tik.send(Message(f"{GLOBAL_NICKNAME}识别：TikTok，{title}\n"))

    target_tik_video_path = await download_ytb_video(
        url, IS_OVERSEA, os.getcwd(), RESOLVER_PROXY, "tiktok"
    )
    await auto_video_send(bot, event, target_tik_video_path)


@acfun.handle()
async def ac(bot: Bot, event: Event) -> None:
    """
        acfun解析
    :param event:
    :return:
    """
    # 消息
    inputMsg: str = str(event.get_message()).strip()

    # 短号处理
    if "m.acfun.cn" in inputMsg:
        inputMsg = f"https://www.acfun.cn/v/ac{re.search(r'ac=([^&?]*)', inputMsg)[1]}"

    url_m3u8s, video_name = parse_url(inputMsg)
    await acfun.send(Message(f"{GLOBAL_NICKNAME}识别：猴山，{video_name}"))
    m3u8_full_urls, ts_names, output_folder_name, output_file_name = parse_m3u8(
        url_m3u8s
    )
    await asyncio.gather(
        *[download_m3u8_videos(url, i) for i, url in enumerate(m3u8_full_urls)]
    )
    merge_ac_file_to_mp4(ts_names, output_file_name)
    await auto_video_send(bot, event, f"{os.getcwd()}/{output_file_name}")


@twit.handle()
async def twitter(bot: Bot, event: Event):
    """
        推特解析
    :param bot:
    :param event:
    :return:
    """
    msg: str = str(event.get_message()).strip()
    x_url = re.search(r"https?:\/\/x.com\/[0-9-a-zA-Z_]{1,20}\/status\/([0-9]*)", msg)[
        0
    ]

    x_url = GENERAL_REQ_LINK.format(x_url)

    def x_req(url):
        return httpx.get(
            url,
            headers={
                "Accept": "ext/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Host": "47.99.158.118",
                "Proxy-Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-User": "?1",
                **COMMON_HEADER,
            },
        )

    x_data: object = x_req(x_url).json()["data"]

    if x_data is None:
        x_url = x_url + "/photo/1"
        logger.info(x_url)
        x_data = x_req(x_url).json()["data"]
    logger.info(x_data)

    x_url_res = x_data["url"]

    await twit.send(Message(f"{GLOBAL_NICKNAME}识别：小蓝鸟学习版"))

    if x_url_res.endswith(".jpg") or x_url_res.endswith(".png"):
        res = await download_img(x_url_res, "", RESOLVER_PROXY)
    else:
        res = await download_video(x_url_res)

    def auto_determine_send_type(user_id: int, task: str):
        if task.endswith("jpg") or task.endswith("png"):
            return MessageSegment.node_custom(
                user_id=user_id,
                nickname=GLOBAL_NICKNAME,
                content=Message(MessageSegment.image(task)),
            )
        elif task.endswith("mp4"):
            return MessageSegment.node_custom(
                user_id=user_id,
                nickname=GLOBAL_NICKNAME,
                content=Message(MessageSegment.video(task)),
            )

    await send_forward_both(bot, event, auto_determine_send_type(int(bot.self_id), res))
    os.unlink(res)


@xhs.handle()
async def xiaohongshu(bot: Bot, event: Event):
    """
        小红书解析
    :param event:
    :return:
    """
    msg_url = re.search(
        r"(http:|https:)\/\/(xhslink|(www\.)xiaohongshu).com\/[A-Za-z\d._?%&+\-=\/#@]*",
        str(event.get_message()).strip(),
    )[0]
    # 如果没有设置xhs的ck就结束，因为获取不到
    xhs_ck = getattr(GLOBAL_CONFIG, "xhs_ck", "")
    if xhs_ck == "":
        logger.error(GLOBAL_CONFIG)
        await xhs.send(
            Message(
                f"{GLOBAL_NICKNAME}识别内容来自：【小红书】\n无法获取到管理员设置的小红书ck！"
            )
        )
        return

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.9",
        "cookie": xhs_ck,
    } | COMMON_HEADER
    if "xhslink" in msg_url:
        msg_url = httpx.get(msg_url, headers=headers, follow_redirects=True).url
        msg_url = str(msg_url)
    xhs_id = re.search(r"/explore/(\w+)", msg_url)
    if not xhs_id:
        xhs_id = re.search(r"/discovery/item/(\w+)", msg_url)
    if not xhs_id:
        xhs_id = re.search(r"source=note&noteId=(\w+)", msg_url)
    xhs_id = xhs_id[1]

    parsed_url = urlparse(msg_url)
    params = parse_qs(parsed_url.query)
    # 提取 xsec_source 和 xsec_token
    xsec_source = params.get("xsec_source", [None])[0] or "pc_feed"
    xsec_token = params.get("xsec_token", [None])[0]

    html = httpx.get(
        f"{XHS_REQ_LINK}{xhs_id}?xsec_source={xsec_source}&xsec_token={xsec_token}",
        headers=headers,
    ).text

    try:
        response_json = re.findall("window.__INITIAL_STATE__=(.*?)</script>", html)[0]
    except IndexError:
        await xhs.send(
            Message(
                f"{GLOBAL_NICKNAME}识别内容来自：【小红书】\n当前ck已失效，请联系管理员重新设置的小红书ck！"
            )
        )
        return
    response_json = response_json.replace("undefined", "null")
    response_json = json.loads(response_json)
    note_data = response_json["note"]["noteDetailMap"][xhs_id]["note"]
    type = note_data["type"]
    note_title = note_data["title"]
    note_desc = note_data["desc"]
    await xhs.send(Message(f"{GLOBAL_NICKNAME}识别：小红书，{note_title}\n{note_desc}"))

    aio_task = []
    if type == "normal":
        image_list = note_data["imageList"]
        # 批量下载
        async with aiohttp.ClientSession() as session:
            for index, item in enumerate(image_list):
                aio_task.append(
                    asyncio.create_task(
                        download_img(
                            item["urlDefault"],
                            f"{os.getcwd()}/{str(index)}.jpg",
                            session=session,
                        )
                    )
                )
            links_path = await asyncio.gather(*aio_task)
    elif type == "video":
        video_url = note_data["video"]["media"]["stream"]["h264"][0]["masterUrl"]
        return await auto_video_send(bot, event, await download_video(video_url))
    # 发送图片
    links = make_node_segment(
        bot.self_id, [MessageSegment.image(f"file://{link}") for link in links_path]
    )
    # 发送异步后的数据
    await send_forward_both(bot, event, links)
    for temp in links_path:
        os.unlink(temp)


@y2b.handle()
async def youtube(bot: Bot, event: Event):
    msg_url = re.search(
        r"(?:https?:\/\/)?(www\.)?youtube\.com\/[A-Za-z\d._?%&+\-=\/#]*|(?:https?:\/\/)?youtu\.be\/[A-Za-z\d._?%&+\-=\/#]*",
        str(event.get_message()).strip(),
    )[0]

    proxy = None if IS_OVERSEA else RESOLVER_PROXY
    title = get_video_title(msg_url, IS_OVERSEA, proxy)
    await y2b.send(Message(f"{GLOBAL_NICKNAME}识别：油管，{title}\n"))

    if GLOBAL_CONFIG.download_video:
        target_ytb_video_path = await download_ytb_video(
            msg_url, IS_OVERSEA, os.getcwd(), proxy
        )
        await auto_video_send(bot, event, target_ytb_video_path)


@ncm.handle()
async def netease(event: Event):
    message = str(event.get_message())

    # 识别短链接
    if "163cn.tv" in message:
        message = re.search(
            r"(http:|https:)\/\/163cn\.tv\/([a-zA-Z0-9]+)", message
        ).group(0)
        message = str(httpx.head(message, follow_redirects=True).url)

    ncm_id = re.search(r"id=(\d+)", message).group(1)
    if ncm_id is None:
        await ncm.finish(Message(f"❌ {GLOBAL_NICKNAME}识别：网易云，获取链接失败"))

    ncm_detail_url = f"{NETEASE_API_CN}/song/detail?ids={ncm_id}"
    ncm_detail_resp = httpx.get(ncm_detail_url, headers=COMMON_HEADER)

    ncm_song = ncm_detail_resp.json()["songs"][0]
    ncm_title = f'{ncm_song["name"]}-{ncm_song["ar"][0]["name"]}'.replace(
        r'[\/\?<>\\:\*\|".… ]', ""
    )

    ncm_vip_data = httpx.get(
        NETEASE_TEMP_API.format(ncm_title), headers=COMMON_HEADER
    ).json()
    ncm_url = ncm_vip_data["mp3"]
    ncm_cover = ncm_vip_data["img"]
    await ncm.send(
        Message(
            [
                MessageSegment.image(ncm_cover),
                MessageSegment.text(f"{GLOBAL_NICKNAME}识别：网易云音乐，{ncm_title}"),
            ]
        )
    )
    await ncm.send(
        Message(
            MessageSegment.record(await convert_to_wav(await download_file(ncm_url)))
        )
    )


@kg.handle()
async def kugou(bot: Bot, event: Event):
    message = str(event.get_message())
    # logger.info(message)
    reg1 = r"https?://.*?kugou\.com.*?(?=\s|$|\n)"
    reg2 = r'jumpUrl":\s*"(https?:\\/\\/[^"]+)"'
    reg3 = r'jumpUrl":\s*"(https?://[^"]+)"'
    # 处理卡片问题
    if "com.tencent.structmsg" in message:
        match = re.search(reg2, message)
        if match:
            get_url = match.group(1)
        else:
            match = re.search(reg3, message)
            if match:
                get_url = match.group(1)
            else:
                await kg.send(
                    Message(f"{GLOBAL_NICKNAME}\n来源：【酷狗音乐】\n获取链接失败")
                )
                get_url = None
                return
        if get_url:
            url = json.loads('"' + get_url + '"')
    else:
        match = re.search(reg1, message)
        url = match.group()

    response = httpx.get(url, follow_redirects=True)
    if response.status_code == 200:
        title = response.text
        get_name = r"<title>(.*?)_高音质在线试听"
        name = re.search(get_name, title)
        if name:
            kugou_title = name.group(1)  # 只输出歌曲名和歌手名的部分
            kugou_vip_data = httpx.get(
                f"{KUGOU_TEMP_API.replace('{}', kugou_title)}", headers=COMMON_HEADER
            ).json()

            kugou_url = kugou_vip_data.get("music_url")
            kugou_cover = kugou_vip_data.get("cover")
            kugou_name = kugou_vip_data.get("title")
            kugou_singer = kugou_vip_data.get("singer")
            await kg.send(
                Message(
                    [
                        MessageSegment.image(kugou_cover),
                        MessageSegment.text(
                            f"{GLOBAL_NICKNAME}\n来源：【酷狗音乐】\n歌曲：{kugou_name}-{kugou_singer}"
                        ),
                    ]
                )
            )
            await kg.send(
                Message(
                    MessageSegment.record(
                        await convert_to_wav(await download_file(kugou_url))
                    )
                )
            )
        else:
            await kg.send(
                Message(
                    f"{GLOBAL_NICKNAME}\n来源：【酷狗音乐】\n不支持当前外链，请重新分享再试"
                )
            )
    else:
        await kg.send(Message(f"{GLOBAL_NICKNAME}\n来源：【酷狗音乐】\n获取链接失败"))


@weibo.handle()
async def wb(bot: Bot, event: Event):
    message = str(event.get_message())
    weibo_id = None
    reg = r'(jumpUrl|qqdocurl)": ?"(.*?)"'

    if "com.tencent.structmsg" or "com.tencent.miniapp" in message:
        match = re.search(reg, message)
        print(match)
        if match:
            get_url = match.group(2)
            print(get_url)
            if get_url:
                message = json.loads('"' + get_url + '"')
    else:
        message = message

    if "m.weibo.cn" in message:
        # https://m.weibo.cn/detail/4976424138313924
        match = re.search(r"(?<=detail/)[A-Za-z\d]+", message) or re.search(
            r"(?<=m.weibo.cn/)[A-Za-z\d]+/[A-Za-z\d]+", message
        )
        weibo_id = match.group(0) if match else None
    elif "weibo.com/tv/show" in message and "mid=" in message:
        # https://weibo.com/tv/show/1034:5007449447661594?mid=5007452630158934
        match = re.search(r"(?<=mid=)[A-Za-z\d]+", message)
        if match:
            weibo_id = mid2id(match.group(0))
    elif "weibo.com" in message:
        # https://weibo.com/1707895270/5006106478773472
        match = re.search(r"(?<=weibo.com/)[A-Za-z\d]+/[A-Za-z\d]+", message)
        weibo_id = match.group(0) if match else None

    # 无法获取到id则返回失败信息
    if not weibo_id:
        await weibo.finish(Message("解析失败：无法获取到wb的id"))
    # 最终获取到的 id
    weibo_id = weibo_id.split("/")[1] if "/" in weibo_id else weibo_id
    logger.info(weibo_id)
    # 请求数据
    resp = httpx.get(
        WEIBO_SINGLE_INFO.format(weibo_id),
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "cookie": "_T_WM=40835919903; WEIBOCN_FROM=1110006030; MLOGIN=0; XSRF-TOKEN=4399c8",
            "Referer": f"https://m.weibo.cn/detail/{id}",
        }
        | COMMON_HEADER,
    ).json()
    weibo_data = resp["data"]
    logger.info(weibo_data)
    text, status_title, source, region_name, pics, page_info = (
        weibo_data.get(key, None)
        for key in [
            "text",
            "status_title",
            "source",
            "region_name",
            "pics",
            "page_info",
        ]
    )
    await weibo.send(
        Message(
            f"{GLOBAL_NICKNAME}识别：微博，{re.sub(r'<[^>]+>', '', text)}\n{status_title}\n{source}\t{region_name if region_name else ''}"
        )
    )
    if pics:
        pics = map(lambda x: x["url"], pics)
        download_img_funcs = [
            asyncio.create_task(
                download_img(
                    item,
                    "",
                    headers={"Referer": "http://blog.sina.com.cn/"} | COMMON_HEADER,
                )
            )
            for item in pics
        ]
        links_path = await asyncio.gather(*download_img_funcs)
        # 发送图片
        links = make_node_segment(
            bot.self_id, [MessageSegment.image(f"file://{link}") for link in links_path]
        )
        # 发送异步后的数据
        await send_forward_both(bot, event, links)
        for temp in links_path:
            os.unlink(temp)
    if page_info:
        video_url = page_info.get("urls", "").get("mp4_720p_mp4", "") or page_info.get(
            "urls", ""
        ).get("mp4_hd_mp4", "")
        if video_url and GLOBAL_CONFIG.download_video:
            path = await download_video(
                video_url,
                ext_headers={
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                    "referer": "https://weibo.com/",
                },
            )
            await auto_video_send(bot, event, path)


def make_node_segment(
    user_id, segments: MessageSegment | list
) -> MessageSegment | Iterable[MessageSegment]:
    """将消息封装成 Segment 的 Node 类型，可以传入单个也可以传入多个，返回一个封装好的转发类型
    :param user_id: 可以通过event获取
    :param segments: 一般为 MessageSegment.image / MessageSegment.video / MessageSegment.text
    :return:
    """
    if isinstance(segments, list):
        return [
            MessageSegment.node_custom(
                user_id=user_id, nickname=GLOBAL_NICKNAME, content=Message(segment)
            )
            for segment in segments
        ]
    return MessageSegment.node_custom(
        user_id=user_id, nickname=GLOBAL_NICKNAME, content=Message(segments)
    )


async def send_forward_both(
    bot: Bot, event: Event, segments: MessageSegment | list
) -> None:
    """自动判断message是 List 还是单个，然后发送{转发}，允许发送群和个人
    :param bot:
    :param event:
    :param segments:
    :return:
    """
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_forward_msg(group_id=event.group_id, messages=segments)
    else:
        await bot.send_private_forward_msg(user_id=event.user_id, messages=segments)


async def auto_video_send(bot: Bot, event: Event, data_path: str):
    """
    拉格朗日自动转换成CQ码发送
    :param event:
    :param data_path:
    :return:
    """

    async def upload_both(file_path: str, name: str) -> None:
        """上传文件，不限于群和个人"""
        if isinstance(event, GroupMessageEvent):
            await bot.upload_group_file(
                group_id=event.group_id, file=file_path, name=name
            )
        elif isinstance(event, PrivateMessageEvent):
            await bot.upload_private_file(
                user_id=event.user_id, file=file_path, name=name
            )

    try:
        if data_path is not None and data_path.startswith("http"):
            data_path = await download_video(data_path)
        file_size_in_mb = get_file_size_mb(data_path)
        if file_size_in_mb > VIDEO_MAX_MB:
            await bot.send(
                event,
                Message(
                    f"当前解析文件 {file_size_in_mb} MB 大于 {VIDEO_MAX_MB} MB，尝试改用文件方式发送，请稍等..."
                ),
            )
            return await upload_both(data_path, data_path.split("/")[-1])
        await bot.send(event, MessageSegment.video(f"file://{data_path}"))
    except Exception as e:
        logger.error(f"解析发送出现错误，具体为\n{e}")
    finally:
        for p in [pathlib.Path(data_path), pathlib.Path(data_path + ".jpg")]:
            if p.exists():
                p.unlink()
