import os
import subprocess
import random

import cv2
import sys

import math

import time

from datetime import datetime
from PIL import Image

CONF = {
    # 棋子宽度的一半 pixel
    "player_w/2": 43,
    # 棋子高度 pixel
    "player_h": 202,
    # 按压系数
    "press_coefficient": 1.366,
    # "press_coefficient": 1.392,
}

MAX_SCREENSHOT_WAY = 2
# 匹配小跳棋的模板
PLAYER_CV = cv2.imread('player.jpg', 0)
PLAYER_W, PLAYER_H = PLAYER_CV.shape[::-1]
# 匹配游戏结束画面的模板
END_CV = cv2.imread('end.jpg', 0)
# 匹配中心小圆点的模板
WHITE_CIRCLE_CV = cv2.imread('white_circle.jpg', 0)
WHITE_CIRCLE_W, WHITE_CIRCLE_H = WHITE_CIRCLE_CV.shape[::-1]


def pull_screenshot(filename, screenshot_way):
    '''
    新的方法请根据效率及适用性由高到低排序
    '''
    if screenshot_way == 2 or screenshot_way == 1:
        process = subprocess.Popen('adb shell screencap -p', shell=True, stdout=subprocess.PIPE)
        screenshot = process.stdout.read()
        if screenshot_way == 2:
            binary_screenshot = screenshot.replace(b'\r\n', b'\n')
        else:
            binary_screenshot = screenshot.replace(b'\r\r\n', b'\n')
        f = open('images/' + filename, 'wb')
        f.write(binary_screenshot)
        f.close()
    elif screenshot_way == 0:
        os.system('adb shell screencap -p /sdcard/{}'.format(filename))
        os.system('adb pull /sdcard/{} .'.format(filename))


def check_screenshot(screenshot_way=MAX_SCREENSHOT_WAY):
    '''
    检查获取截图的方式
    '''
    if os.path.isfile('./images/check.png'):
        os.remove('./images/check.png')
    if (screenshot_way < 0):
        print('暂不支持当前设备')
        if os.path.isfile('./images/check.png'):
            os.remove('./images/check.png')
        sys.exit()
    pull_screenshot('check.png', screenshot_way)
    try:
        Image.open('./images/check.png').load()
        print('采用方式 {} 获取截图'.format(screenshot_way))
        if os.path.isfile('./images/check.png'):
            os.remove('./images/check.png')
        return screenshot_way
    except Exception:
        return check_screenshot(screenshot_way - 1)


def build_filename(index):
    return '{}_{:05d}.png'.format(datetime.now().strftime("%Y%m%d%H%M%S"), index)


def find_top(img1, x1):
    H, W, _ = img1.shape
    img1 = cv2.GaussianBlur(img1, (5, 5), 0)
    canny_img = cv2.Canny(img1, 1, 10)

    for row in range(300, H):
        for col in range(W // 8, W):
            # 当检测到切点，且切点与棋子的水平距离大于棋子的一半时（排除棋子高于下一个目标的情况）
            if canny_img[row, col] != 0 and abs(x1 - col) > CONF['player_w/2']:
                return row, col, canny_img


def find_bottom(canny_img, top_x, top_y):
    H, W = canny_img.shape
    for row in range(top_y + 5, H):
        if canny_img[row, top_x] != 0:
            return row


def get_button_position(im):
    '''
    将 swipe 设置为 `再来一局` 按钮的位置
    '''
    h, w, _ = im.shape
    left = int(w / 2)
    top = int(1584 * (h / 1920.0))
    left = int(random.uniform(left - 50, left + 50))
    top = int(random.uniform(top - 10, top + 10))  # 随机防 ban
    return left, top, left, top


def jump(distance, im):
    '''
    跳跃一定的距离
    '''
    press_time = distance * CONF['press_coefficient']
    press_time = max(press_time, 200)  # 设置 200ms 是最小的按压时间
    press_time = int(press_time)

    swipe_x1, swipe_y1, swipe_x2, swipe_y2 = get_button_position(im)

    cmd = 'adb shell input swipe {x1} {y1} {x2} {y2} {duration}'.format(
        x1=swipe_x1,
        y1=swipe_y1,
        x2=swipe_x2,
        y2=swipe_y2,
        duration=press_time
    )
    print(cmd)
    os.system(cmd)
    return press_time


if __name__ == '__main__':
    screenshot_way = check_screenshot()

    i, next_rest, next_rest_time = 0, random.randrange(3, 10), random.randrange(5, 10)
    for i in range(10000):
        filename = build_filename(i)
        pull_screenshot(filename, screenshot_way)
        path = os.path.join('images', filename)
        img_rgb = cv2.imread(path)
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

        # 如果在游戏截图中匹配到带"再玩一局"字样的模板，则循环中止
        res_end = cv2.matchTemplate(img_gray, END_CV, cv2.TM_CCOEFF_NORMED)
        if cv2.minMaxLoc(res_end)[1] > 0.95:
            print('Game over!')
            break

        # 模板匹配截图中小跳棋的位置
        res1 = cv2.matchTemplate(img_gray, PLAYER_CV, cv2.TM_CCOEFF_NORMED)
        min_val1, max_val1, min_loc1, max_loc1 = cv2.minMaxLoc(res1)
        center1_loc = (max_loc1[0] + CONF['player_w/2'], max_loc1[1] + CONF['player_h'])
        x1 = max_loc1[0] + CONF['player_w/2']
        y1 = max_loc1[1] + CONF['player_h']
        # 先尝试匹配截图中的中心原点，
        # 如果匹配值没有达到0.95，则使用边缘检测匹配物块上沿
        res2 = cv2.matchTemplate(img_gray, WHITE_CIRCLE_CV, cv2.TM_CCOEFF_NORMED)
        min_val2, max_val2, min_loc2, max_loc2 = cv2.minMaxLoc(res2)
        if max_val2 > 0.95:
            print('found white circle!')
            x, y = max_loc2[0] + WHITE_CIRCLE_W // 2, max_loc2[1] + WHITE_CIRCLE_H // 2
        else:
            top_y, top_x, canny_img = find_top(img_rgb, x1)
            bottom_y = find_bottom(canny_img, top_x, top_y)
            x = top_x
            y = (top_y + bottom_y) / 2
        center2_loc = (int(x), int(y))

        distance = (center1_loc[0] - x) ** 2 + (center1_loc[1] - y) ** 2
        distance = math.sqrt(distance)
        # 文件名 距离 小跳棋位置 目标位置
        os.system('echo {},{},{},{},{},{} >> data.txt'.format(filename, distance, center1_loc[0], center1_loc[1], x, y))
        jump(distance, img_rgb)

        i += 1
        if i == next_rest:
            print('已经连续打了 {} 下，休息 {}s'.format(i, next_rest_time))
            for j in range(next_rest_time):
                print('\r程序将在 {}s 后继续'.format(next_rest_time - j))
                time.sleep(1)
            print('\n继续')
            i, next_rest, next_rest_time = 0, random.randrange(30, 100), random.randrange(10, 60)

        # 为了保证截图的时候应落稳了，多延迟一会儿，随机值防 ban
        # time.sleep(random.uniform(0.9, 1.2))
        time.sleep(random.uniform(1.5, 2))
