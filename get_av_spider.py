import sys
import time
import getopt
import requests
import urllib.request
import pymysql
from lxml import etree
 
class avmo:
 
    def __init__(self):
        #初始化
        self.config()
        try:
            opts, args = getopt.getopt(sys.argv[1:], "hirs:e:t:", ['help','insert','retry','start','end','table'])
        except:
            self.usage()
            sys.exit()
        self.flag_insert = False
        self.flag_retry = False
        self.start_id = '0000'
        self.stop_id = 'zzzz'
        for op, value in opts:
            if op == '-i' or op == '-insert':
                self.flag_insert = True
            elif op == '-r' or op == '-retry':
                self.flag_retry = True
            elif op == '-s' or op == '-start':
                self.start_id = value
            elif op == '-e' or op == '-end':
                self.stop_id = value
            elif op == '-t' or op == '-table':
                self.main_table = value
            elif op == '-h' or op == '-help':
                self.usage()
                sys.exit()
        if self.flag_insert == False:
            self.flag_retry = False
        
        #链接数据库
        self.conn()
        #主程序
        self.main()
         
        #重试失败地址
        # self.retry_errorurl()
        #测试单个页面
        # self.test_page('5qw0')
 
    #销毁
    def __del__(self):
        if self.flag_insert:
            #关闭数据库
            self.CONN.close()
            self.CUR.close()
 
    #默认配置
    def config(self):
        #待insert数据
        self.insert_list = []
        #遍历linkid
        self.sl = '0123456789abcdefghijklmnopqrstuvwxyz'
        #获取sl的字典列表dl
        self.relist()
        #表结构
        self.column=[
        'id',
        'linkid',
        'director',
        'director_url',
        'studio',
        'studio_url',
        'label',
        'label_url',
        'series',
        'series_url',
        'image_len',
        'genre',
        'len',
        'stars',
        'av_id',
        'title',
        'bigimage',
        'release_date']
        #表结构str
        self.column_str = ",".join(self.column)
        #插入阈值
        self.insert_threshold = 30
        #用于重试失败阈值
        self.retry_counter = 0
        #重试阈值
        self.retry_threshold = 5
        #超时时间
        self.timeout = 10
 
        #主表
        self.main_table = 'av_list'
        #重试表
        self.retry_table = 'av_error_linkid'
        #站点url
        site_url = 'https://avmo.pw/cn'
        #番号主页url
        self.movie_url = site_url+'/movie/'
        #导演 制作 发行 系列
        self.director = site_url+'/director'
        self.studio = site_url+'/studio'
        self.label = site_url+'/label'
        self.series = site_url+'/series'
    
    #mysql conn
    def conn(self):
        #如果正式插入那么链接数据库
        if self.flag_insert:
            try:
                #链接数据库
                self.CONN = pymysql.connect(
                    host = '127.0.0.1',
                    port = 3306,
                    user = 'root',
                    passwd = 'root',
                    db = 'avmopw',
                    charset = 'utf8'
                )
                self.CUR = self.CONN.cursor()
            except:
                self.CONN = None
                self.CUR = None
                print('connect mysql fail.')
                self.usage()
                sys.exit()
    #写出命令行格式
    def usage(self):
        print(sys.argv[0] + ' -i -r -s 0000 -e zzzz')
        print(sys.argv[0] + ' -s 1000 -e 2000')
        print('-h(-help):Show usage')
        print('-i(-insert):Insert database')
        print('-r(-retry):Retry error link')
        print('-s(-start):Start linkid')
        print('-e(-end):End linkid')
 
    #测试单个页面
    def test_page(self,linkid):
        url = self.movie_url+linkid
        res = requests.get(url,timeout=self.timeout).text
        #解析页面内容
        data = self.movie_page_data(etree.HTML(res))
        print(data)
 
    #插入重试表
    def insert_retry(self,data):
        if self.flag_retry:
            self.CUR.execute("INSERT INTO {0} (linkid,status_code,datetime)VALUE('{1[0]}',{1[1]} ,now());".format(self.retry_table,data))
            self.CONN.commit()
    
    #主函数，抓取页面内信息
    def main(self):
        for item in self.get_linkid():
            url = self.movie_url+item
            
            try:
                res = requests.get(url, timeout = self.timeout)
                if res.status_code!=200:
                    self.insert_retry((item,res.status_code))
                    print(url,res.status_code)
            except:
                print(url,'requests.get error')
                self.insert_retry((item,0))
                continue
            
            try:
                html=etree.HTML(res.text)
            except:
                print(url,'etree.HTML error')
                self.insert_retry((item,1))
                continue
            
            #解析页面内容
            data=self.movie_page_data(html)
            #从linkid获取id
            id=self.linkid2id(item)
            #输出当前进度
            print(data[12].ljust(16),data[15].ljust(11),item.ljust(5),id)
            
            if self.flag_insert:
                self.insert_list.append(
                    "'{0}','{1}','{2}'".format(id, item, "','".join(data))
                )
                #存储数据
                if self.insert_list.__len__() == self.insert_threshold:
                    self.insert_mysql()
 
    #遍历urlid
    def get_linkid(self):
        for i1 in self.sl:
            for i2 in self.sl:
                for i3 in self.sl:
                    for i4 in self.sl:
                        tmp = i1+i2+i3+i4
                        if tmp > self.stop_id:
                            print('start:{0} end:{1} done!'.format(self.start_id,self.stop_id))
                            #插入剩余的数据
                            self.insert_mysql()
                            #重试错误数据
                            self.retry_errorurl()
                            exit()
                        if self.start_id < tmp:
                            yield tmp
                        else:
                            continue
    #由urlid获取排序自增id
    def linkid2id(self,item):
        return self.dl[item[3]] + self.dl[item[2]]*36 + self.dl[item[1]]*1296 + self.dl[item[0]]*46656
 
    #插入数据库
    def insert_mysql(self):
        if self.insert_list.__len__()==0:
            return
 
        if self.flag_insert!=False:
            sql="REPLACE INTO {2}({0})VALUES({1});".format(self.column_str,"),(".join(self.insert_list),self.main_table)
            self.CUR.execute(sql)
            self.CONN.commit()
 
        print('insert rows:',self.insert_list.__len__(),'retry_counter:',self.retry_counter)
        self.insert_list=[]
        self.retry_counter+=1
 
        if self.flag_retry:
            #重试失败地址
            if self.retry_counter>=self.retry_threshold:
                self.retry_counter=0
                self.retry_errorurl()
 
    #重试
    def retry_errorurl(self):
        sql = 'SELECT linkid FROM {0};'.format(self.retry_table)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
        reslen = res.__len__()
        if reslen == 0:
            return
        print('retry error url:',reslen)
 
        dellist = []
        for item in res:
            reslen -= 1
            url = self.movie_url + item[0]
            try:
                r=requests.get(url,timeout = self.timeout)
                html = etree.HTML(r.text)
            except:
                print(reslen,url,'fail')
                continue
             
            if r.status_code != 200:
                if r.status_code == 404:
                    dellist.append(item[0])
 
                print(reslen, item[0], r.status_code)
                continue
 
            print(reslen,item[0])
            data = self.movie_page_data(html)
            id = self.linkid2id(item[0])
            self.insert_list.append(
                "'{0}','{1}','{2}'".format(id,item[0],"','".join(data))
            )
            dellist.append(item[0])
 
        self.insert_mysql()
        if dellist != []:
            self.CUR.execute('DELETE FROM {0} WHERE {1};'.format(self.retry_table ,' OR '.join([" linkid='{0}' ".format(x) for x in dellist])))
            self.CONN.commit()
 
    #获取idlist的字典
    def relist(self):
        self.dl={}
        for i in range(self.sl.__len__()):
            self.dl[self.sl[i]]=i
 
    def movie_page_data(self,html):
        data = ['' for x in range(16)]
        #获取：导演、制作商、发行商、系列
        info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in info:
            if i.text == None:
                continue
            if i.attrib.get('href')[:27] == self.director:
                #导演
                data[0] = i.text.replace("'","\\'")
                data[1] = i.attrib.get('href')[28:]
                 
            elif i.attrib.get('href')[:25] == self.studio:
                #制作商
                data[2] = i.text.replace("'","\\'")
                data[3] = i.attrib.get('href')[26:]
                 
            elif i.attrib.get('href')[:24] == self.label:
                #发行商
                data[4] = i.text.replace("'","\\'")
                data[5] = i.attrib.get('href')[25:]
                 
            elif i.attrib.get('href')[:25] == self.series:
                #系列
                data[6] = i.text.replace("'","\\'")
                data[7] = i.attrib.get('href')[26:]
                 
        #图片个数image_len
        data[8] = str(html.xpath('//*[@id="sample-waterfall"]/a').__len__())
        #获取类别列表genre
        data[9] = '|'.join(html.xpath('/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'","\\'")
        #时长len
        tmp = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if tmp.__len__() != 0:
            data[10] = tmp[0].replace('分钟','').strip()
        else:
            data[10] = '0'
        #演员stars
        data[11] = '|'.join(html.xpath('//*[@id="avatar-waterfall"]/a/span/text()')).replace("'","\\'")
        #番号
        data[12] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        #接取除了番号的标题
        data[13] = html.xpath('/html/body/div[2]/h3/text()')[0][data[12].__len__()+1:].replace("'","\\'")
        #封面 截取video之后的部分
        data[14] = html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0][37:]
        #发行时间
        data[15] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        return data
    
    #获取所有类别
    def replace_genre(self):
        html = etree.HTML(requests.get('https://avmo.pw/cn/genre').text)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for item in range(div.__len__()):
            g_title = h4[item]
            a = div[item].xpath('a')
            for item2 in a:
                g_name = item2.text.replace('・','')
                g_id = item2.attrib.get('href')[25:]
                insert_list.append("'{0}','{1}','{2}'".format(g_id,g_name,g_title))
        sql = "REPLACE INTO avmo_genre (g_id,g_name,g_title)VALUES({0});".format("),(".join(insert_list))
        self.CUR.execute(sql)
        self.CONN.commit()
    
    #获取最后一次的id
    def get_last(self,where_id = ''):
        if where_id == '':
            sql="SELECT linkid FROM {0} ORDER BY linkid DESC LIMIT 0,1;".format(self.main_table)
        else:
            sql="SELECT linkid FROM {0} WHERE linkid<'{1}' ORDER BY linkid DESC LIMIT 0,1;".format(self.main_table, where_id)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
         
        self.stop_id = 'zzzz'
        if res[0][0] == '':
            self.start_id = '0000'
        else:
            self.start_id = res[0][0]
if __name__ == '__main__':
    avmo()