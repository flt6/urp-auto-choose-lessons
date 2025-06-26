import hashlib
import dotenv
import base64
import json
import csv
import re

from time import sleep

import requests

from bs4 import BeautifulSoup
from os import path,environ


class Lessons:

    def __init__(self, dealType):
        """
            dealType : 选课的类型
        """
        self.session = requests.session()
        self.lessons_list = []
        self.dealType = dealType
        dotenv.load_dotenv()
        for key in ["uname", "password","recap_username", "recap_password"]:
            if not environ.get(key):
                print(f"请在环境变量中设置{key}")
                exit(-1)
        self.base = environ.get("base", "http://jwstudent.lnu.edu.cn")

    @staticmethod
    def recapture(b64):
        data = {
            "username": environ.get("recap_username"), 
            "password": environ.get("recap_password"), 
            "ID": "04897896", 
            "b64": b64, 
            "version": "3.1.1"
        }
        data_json = json.dumps(data)
        result = json.loads(requests.post("http://www.fdyscloud.com.cn/tuling/predict", data=data_json).text)
        return result["data"]["result"]


    @staticmethod
    def pwd_md5(string: str) -> str:
        md5_part1 = hashlib.md5((string + "{Urp602019}").encode()).hexdigest().lower()
        md5_part2 = hashlib.md5(string.encode()).hexdigest().lower()
        final_result = md5_part1 + '*' + md5_part2
        return final_result

    def deal_info(self, lessons_info):  # 将课程信息进行转换
        deal_lessons = []
        for lesson_info in lessons_info:
            lesson = {}
            kcIds = lesson_info["no"] + "_" + lesson_info["id"] + "_" + lesson_info["term"]
            lesson["kcIds"] = kcIds
            kcms = ""
            for c in lesson_info["name"]:
                c = str(ord(c))
                kcms += c + ','
            kcms += "95,"
            for c in lesson_info["id"]:
                c = str(ord(c))
                kcms += c + ','
            lesson["kcms"] = kcms
            deal_lessons.append(lesson)
        return deal_lessons

    def sum_lessons(self, tokenValue, lessons_list):  # 将所有课程转换后的信息进行集中
        data = {"dealType": self.dealType, "fajhh": self.fajhh, "sj": "0_0", "searchtj": "",
                "kclbdm": "", "inputCode": "", "tokenValue": tokenValue}
        kcIds = ""
        kcms = ""
        not_first = False
        for lesson in lessons_list:
            if not_first:
                kcIds += ','
                kcms += '44,'
            kcIds += lesson["kcIds"]
            kcms += lesson["kcms"]
            not_first = True
        data["kcIds"] = kcIds
        data["kcms"] = kcms
        return data

    def login(self):  # 登录模块
        username = environ.get("uname")
        password = environ.get("password")
        self.username = username
        
        req = self.session.get("http://jwstudent.lnu.edu.cn/login")
        req.raise_for_status()
        html = req.text
        match = re.search(r'name="tokenValue" value="(.+?)">', html)
        if match:
            token_value = match.group(1)
        else:
            raise ValueError("未找到 tokenValue")

        req = self.session.get(f"{self.base}/img/captcha.jpg")
        req.raise_for_status()
        im = req.content
        b64 = base64.b64encode(im).decode('utf-8')
        captcha_code = self.recapture(b64=b64)
        with open("captcha.jpg", "wb") as f:
            f.write(im)
        print(captcha_code)

        hashed_password = self.pwd_md5(password)

        # 模拟请求的 payload
        payload = {
            "j_username": username,
            "j_password": hashed_password,
            "j_captcha": captcha_code,
            "tokenValue": token_value
        }

        # 发送 POST 请求
        url = f"{self.base}/j_spring_security_check"  # 替换为实际登录地址
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = self.session.post(url, data=payload, headers=headers)

        if "发生错误" in response.text:
            err = re.search(r'<strong>发生错误！</strong>(.+)', response.text)
            if err:
                error_message = err.group(1).strip()
                raise ValueError(f"登录失败: {error_message}")
            raise ValueError("登录失败")
        
    def judge_info(self, lesson_no, info):  # 对选课结果进行判断
        if info != "你选择的课程没有课余量！":
            for i in range(len(self.lessons_list)):
                if lesson_no == self.lessons_list[i]['no']:
                    self.lessons_list.pop(i)
                    print(lesson_no + ":" + info)
                    break

    def judge_logout(self, html):  # 账号在其他地方被登录时报错
        if html.url == f"{self.base}/login?errorCode=concurrentSessionExpired":
            print("有人登陆了您的账号！")
            exit(0)

    def judge_choose(self, bs):
        alart = bs.find("div", {"class": "alert alert-block alert-danger"})  # 判断是否可以选课
        if alart is not None:
            print("对不起，当前为非选课阶段！")
            exit(0)

    def get_tokenvalue(self, bs):
        tokenValue = bs.find("input", {"type": "hidden", "id": "tokenValue"})["value"]
        return tokenValue

    def get_term(self, bs):
        term = bs.find("h4").text.split('(')[1].split('\r')[0]
        if term[-1] == '春':
            self.term = term[:9] + "-2-1"
        else:
            self.term = term[:9] + "-1-1"

    def get_fajhh(self, bs):
        self.fajhh = bs.find("li", {"title": "校任选课", "id": "xarxk"})["onclick"].split('=')[1].split("'")[0]

    def get_lesson_page(self):
        try:
            html = self.session.get(url=f"{self.base}/student/courseSelect/courseSelect/index",
                                    timeout=10)
        except requests.ConnectionError:
            print("选课页面无法加载！连接错误！")
            exit(0)
        except requests.HTTPError:
            print("选课页面无法加载！请求网页有问题！")
            exit(0)
        except requests.Timeout:
            print("选课页面无法加载！请求超时！")
            exit(0)
        else:
            self.judge_logout(html)
            bs = BeautifulSoup(html.text, "html.parser")
            return bs

    def get_lessons_list(self):
        road = "user_info/" + str(self.username) + ".csv"
        if not path.exists(road):  # 导入选课内容
            print("选课文件不存在！请检查！")
            exit(0)
        file = open(road, mode='r', encoding='utf-8')
        lessons = csv.reader(file)
        for lesson in lessons:
            lesson_info = {"no": lesson[0], "id": lesson[1], "term": self.term, "name": lesson[2]}
            self.lessons_list.append(lesson_info)
        file.close()

    def search_lessons_info(self):
        lessons_list = []
        for lesson in self.lessons_list:
            data = {'searchtj': lesson['no'], 'xq': '0', 'jc': '0', 'kclbdm': ''}
            url = f"{self.base}/student/courseSelect/freeCourse/courseList"
            for count in range(1, 11):
                try:
                    rp = self.session.post(url=url, data=data, timeout=10)
                except requests.ConnectionError:
                    print("课余量查询失败！连接错误！")
                    print('第%d次重试' % count)
                    continue
                except requests.HTTPError:
                    print("课余量查询失败！请求网页有问题！")
                    print('第%d次重试' % count)
                    continue
                except requests.Timeout:
                    print("课余量查询失败！请求超时！")
                    print('第%d次重试' % count)
                    continue
                else:
                    self.judge_logout(rp)
                    infos = eval(eval(rp.text)['rwRxkZlList'])
                    if len(infos) == 0:
                        print("未找到或已选%s！" % lesson['name'])
                        for i in range(len(self.lessons_list)):
                            if lesson['no'] == self.lessons_list[i]['no']:
                                self.lessons_list.pop(i)
                        break
                    for info in infos:
                        if info['kxh'] == lesson['id'] and int(info['bkskyl']) > 0:
                            lessons_list.append(lesson)
                            break
                    break
            if count == 10:
                print('课余量查询失败！请检查urp！')
                exit(0)
        return lessons_list

    def choose_lessons(self, tokenValue, lesson_list):
        deal_lessons = self.deal_info(lesson_list)
        data = self.sum_lessons(tokenValue, deal_lessons)
        for flag in range(1, 11):
            try:  # 提交选课表单
                rq = self.session.post(url=f"{self.base}/student/courseSelect"
                                           "/selectCourse/checkInputCodeAndSubmit",
                                       data=data,
                                       timeout=10)
            except requests.ConnectionError:
                print("选课提交失败！连接错误！")
                print('第%d次重试！' % flag)
                continue
            except requests.HTTPError:
                print("选课提交失败！请求网页有问题！")
                print('第%d次重试！' % flag)
                continue
            except requests.Timeout:
                print("选课提交失败！请求超时！")
                print('第%d次重试！' % flag)
                continue
            else:
                break
        if flag == 10:
            print("选课提交失败！请检查urp！")
            exit(0)
        self.judge_logout(rq)
        data.pop("tokenValue")
        data.pop("inputCode")
        for flag in range(1, 11):
            try:  # 网站要求的选课二次确认
                self.session.post(url=f"{self.base}/student/courseSelect/selectCourses/waitingfor",
                                  data=data,
                                  timeout=10)
            except requests.ConnectionError:
                print("选课提交确认失败！连接错误！")
                print('第%d次重试！' % flag)
                continue
            except requests.HTTPError:
                print("选课提交确认失败！请求网页有问题！")
                print('第%d次重试！' % flag)
                continue
            except requests.Timeout:
                print("选课提交确认失败！请求超时！")
                print('第%d次重试！' % flag)
                continue
            else:
                break
        if flag == 10:
            print("选课提交确认失败！请检查urp！")
            exit(0)
        self.judge_logout(rq)
        data = {"kcNum": str(len(lesson_list)), "redisKey": self.username + self.dealType}
        i = 1
        while True:
            sleep(1)  # 让服务器处理选课的等待时间，严禁删除！！！
            try:  # 获取选课结果
                rq = self.session.post(url=f"{self.base}/student/"
                                           "  courseSelect/selectResult/query",
                                       data=data,
                                       timeout=10)
            except requests.ConnectionError:
                print("获取选课结果失败！连接错误！")
                exit(0)
            except requests.HTTPError:
                print("获取选课结果失败！请求网页有问题！")
                exit(0)
            except requests.Timeout:
                print("获取选课结果失败！请求超时！")
                exit(0)
            else:
                self.judge_logout(rq)
                if "true" in rq.text:
                    break
                if i > 10:
                    print("获取选课结果失败！请到urp进行确认！")
                    exit(0)
                print("第" + str(i) + "次获取选课结果失败！正在重试！")
                i += 1
        infos = eval(rq.text.replace("true", '"true"'))
        infos = infos["result"]
        for info in infos:  # 判断选课结果并输出
            self.judge_info(info.split("_")[0], info.split(":")[-1])

    def auto_spider(self):  # 自动选课部分
        self.login()  # 进行登录操作
        count = 0
        while self.lessons_list or count == 0:
            sleep(0.5)
            count += 1
            print("第%d次搜索课余量！" % count)
            if count == 1:
                """
                    导入培养方案编号以及选课的学期
                """
                bs = self.get_lesson_page()
                self.judge_choose(bs=bs)
                self.get_term(bs=bs)
                self.get_fajhh(bs=bs)
                self.get_lessons_list()
                token_Value = self.get_tokenvalue(bs=bs)
                self.choose_lessons(tokenValue=token_Value, lesson_list=self.lessons_list)
                bs = self.get_lesson_page()
                self.judge_choose(bs=bs)
                token_Value = self.get_tokenvalue(bs=bs)

            lessons_list = self.search_lessons_info()
            if len(lessons_list) != 0:
                self.choose_lessons(tokenValue=token_Value, lesson_list=self.lessons_list)
                bs = self.get_lesson_page()
                self.judge_choose(bs=bs)
                token_Value = self.get_tokenvalue(bs=bs)
