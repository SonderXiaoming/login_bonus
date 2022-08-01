import random
import hoshino
from hoshino import Service, R
from hoshino.typing import MessageSegment, CQEvent
from hoshino.util import DailyNumberLimiter
from PIL import Image, ImageFont
from .base import *
from .text import *
import base64
from io import BytesIO

sv = Service(
    name='签到奖励',
    visible=True,  # 是否可见
    enable_on_default=True,  # 是否默认启用
    bundle='娱乐',
    help_='[星乃签到] 给主さま盖章章'
)

PRELOAD = True  # 是否启动时直接将所有图片加载到内存中以提高查看仓库的速度(增加约几M内存消耗)
COL_NUM = 8  # 查看仓库时每行显示的卡片个数

__BASE = os.path.split(os.path.realpath(__file__))
FRAME_DIR_PATH = os.path.join(__BASE[0], 'image')
DIR_PATH = os.path.join(os.path.expanduser(hoshino.config.RES_DIR), 'img', 'priconne', 'stamp')
font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), 'arial.ttf'), 16)
card_file_names_all = []

# 资源预检
image_cache = {}
image_list = os.listdir(DIR_PATH)
for image in image_list:
    # 图像缓存
    if PRELOAD:
        image_path = os.path.join(DIR_PATH, image)
        img = Image.open(image_path)
        image_cache[image] = img.convert('RGBA') if img.mode != 'RGBA' else img
    card_file_names_all.append(image)
len_card = len(card_file_names_all)

def normalize_digit_format(n):
    return f'0{n}' if n < 10 else f'{n}'


def get_pic(pic_path, grey):
    if PRELOAD:
        sign_image = image_cache[pic_path]
    else:
        sign_image = Image.open(os.path.join(hoshino.config.RES_DIR, 'img', 'priconne', 'stamp', pic_path))
    sign_image = sign_image.resize((80, 80), Image.ANTIALIAS)
    if grey:
        sign_image = sign_image.convert('L')
    return sign_image


lmt = DailyNumberLimiter(1)


# @sv.on_fullmatch('签到', '盖章', '妈', '妈?', '妈妈', '妈!', '妈！', '妈妈！', only_to_me=True)
@sv.on_rex(r"^盖章$|^(妈|ma)(妈|ma|!|！)?[!！]?$", only_to_me=True)
async def give_okodokai(bot, ev: CQEvent):
    uid = ev.user_id
    gid = ev.group_id
    if not lmt.check(f"{uid}@{gid}"):
        await bot.send(ev, '明日はもう一つプレゼントをご用意してお待ちしますね', at_sender=True)
        return
    lmt.increase(f"{uid}@{gid}")
    present = random.choice(login_presents)
    todo = random.choice(todo_list)
    stamp = random.choice(card_file_names_all)
    card_id = stamp[:-4]
    db.add_card_num(gid, uid, card_id)
    await bot.send(ev,
                   f'\nおかえりなさいませ、主さま{R.img("priconne/stamp/" + stamp).cqcode}\n{present}を獲得しました\n'
                   f'私からのプレゼントです\n主人今天要{todo}吗？',
                   at_sender=True)


@sv.on_prefix('收集册')
async def storage(bot, ev: CQEvent):
    uid = 0
    if len(ev.message) == 1 and ev.message[0].type == 'text' and not ev.message[0].data['text']:
        uid = ev.user_id
    elif ev.message[0].type == 'at':
        uid = int(ev.message[0].data['qq'])
    else:
        await bot.finish(ev, '参数格式错误, 请重试')
    
    row_num = len_card//COL_NUM if len_card % COL_NUM !=0 else len_card//COL_NUM-1
    base = Image.open(FRAME_DIR_PATH + '/frame.png')
    base = base.resize((40 + COL_NUM * 80 + (COL_NUM - 1) * 10, 150 + row_num * 80 + (row_num - 1) * 10),
                       Image.ANTIALIAS)
    cards_num = db.get_cards_num(ev.group_id, uid)
    row_index_offset = 0
    row_offset = 0
    cards_list = card_file_names_all
    for index, c_id in enumerate(cards_list):
        row_index = index // COL_NUM + row_index_offset
        col_index = index % COL_NUM
        f = get_pic(c_id, False) if int(c_id[:-4]) in cards_num else get_pic(c_id, True)
        base.paste(f, (
            30 + col_index * 80 + (col_index - 1) * 10, row_offset + 40 + row_index * 80 + (row_index - 1) * 10))
    row_offset += 30
    ranking = db.get_group_ranking(ev.group_id, uid)
    ranking_desc = f'第{ranking}位' if ranking != -1 else '未上榜'
    buf = BytesIO()
    base = base.convert('RGB')
    base.save(buf, format='JPEG')
    base64_str = f'base64://{base64.b64encode(buf.getvalue()).decode()}'
    await bot.send(ev,
                   f'{MessageSegment.at(uid)}的收集册:[CQ:image,file={base64_str}]\n'
                   f'图鉴完成度: {normalize_digit_format(len(cards_num))}/{normalize_digit_format(len(card_file_names_all))}'
                   f'\n当前群排名: {ranking_desc}')
