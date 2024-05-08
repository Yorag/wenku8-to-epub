"""
wenku8下载
"""
import os
import time
from urllib.parse import urlparse

import requests
from lxml import etree




def delay_time(func):
    '''类成员函数装饰器，给带有网络请求的函数追加延时'''
    def wrapper(self, *args, **kwargs):
        ret = func(self, *args, **kwargs)
        time.sleep(self.sleep_time)
        return ret
    return wrapper


class Wenku8Download:
    def __init__(self, book_id):
        self.book = {
            'title': '',
            'publisher': '',
            'author': '',
            'status': '', #ongoing、completed
            'cover_url': '',
            'tags': [],
            'description': '',
            'toc': [],  #[{'volume': '','chapter': []}]
            'api': {} #即self.api
        }

        #------------------------
        self._api = {
            'detail': 'https://www.wenku8.net/book/{book_id}.htm',
            'toc': 'https://www.wenku8.net{toc_path}'
        }
        self._s = requests.Session()
        self._s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0'
        })
        self.image_idx = 0
        self.sleep_time = 1  # 默认网络请求停顿时间1s
        # 错误信息
        self.error_msg = ''

        # 先清除src文件夹下无关文件
        self.src_white_list = ['style.css', 'cover.jpg']
        self.clear_src()

        # 初始化详情页和目录
        self._get_detail(book_id)
        if self.error_msg: return
        self._get_toc()
        self._save_cover()


    @delay_time
    def _request(self, url):
        res = self._s.get(url)  # 修改这里
        return res.content.decode('gbk')


    def _get_detail(self, book_id):
        '''获取书籍详情页内容，收集元数据'''
        self.book['api']['detail'] = self._api['detail'].format(book_id=book_id)
        html_text = self._request(self.book['api']['detail'])
        if '错误原因' in html_text:
            error_msg_idx = html_text.find('错误原因：')
            self.error_msg = html_text[error_msg_idx: html_text.find('<br', error_msg_idx)]
            return

        html = etree.HTML(html_text)
        toc_path = html.xpath('//*[@id="content"]/div[1]/div[4]/div/span[1]/fieldset/div/a/@href')
        if toc_path: self.book['api']['toc'] = self._api['toc'].format(toc_path=toc_path[0])
        else:
            self.error_msg = 'directory not detected.'
            return

        title = html.xpath('//*[@id="content"]/div[1]/table[1]/tr[1]/td/table/tr/td[1]/span/b/text()')
        if title: self.book['title'] = title[0][:title[0].find('(') if '(' in title[0] else None].strip()

        nodes = html.xpath('//*[@id="content"]/div[1]/table[1]/tr[2]')[0]
        self.book['publisher'] = nodes.xpath('td[1]/text()')[0].strip().lstrip('文库分类：')
        self.book['author'] = nodes.xpath('td[2]/text()')[0].strip().lstrip('小说作者：')
        self.book['status'] = nodes.xpath('td[3]/text()')[0].strip().lstrip('文章状态：')

        cover_node = html.xpath('//*[@id="content"]/div[1]/table[2]/tr/td[1]/img/@src')
        if cover_node: self.book['cover_url'] = cover_node[0]

        tags = html.xpath('//*[@id="content"]/div[1]/table[2]/tr/td[2]/span[1]/b/text()')
        if tags: self.book['tags'] = tags[0].strip().lstrip('作品Tags：').split()

        description = html.xpath('//*[@id="content"]/div[1]/table[2]/tr/td[2]/span[6]/text()')
        if description: self.book['description'] = '\n'.join([desp.strip() for desp in description])


    def _get_toc(self):
        '''获取目录'''
        html_text = self._request(self.book['api']['toc'])

        html = etree.HTML(html_text)
        toc_nodes = html.xpath('/html/body/table/tr')
        volume = {} #临时存储volume，引用列表内字典
        for cnode in toc_nodes:
            tds = cnode.xpath('td')
            if len(tds) == 1 and tds[0].xpath('@colspan'): #通过属性判断是volume
                volume_title = tds[0].xpath('text()')[0]
                self.book['toc'].append({'volume': volume_title, 'chapter': []})
                volume = self.book['toc'][-1]
            else:
                for td in tds:
                    if td.xpath('a'):
                        chapter_href = td.xpath('a/@href')[0]
                        chapter_title = td.xpath('a/text()')[0]
                        volume['chapter'].append((chapter_title, chapter_href))


    def get_chapter(self, href):
        '''获取章节内容，返回章节内容'''
        chapter_url = self.book['api']['toc'].replace('index.htm', href)
        html_text = self._request(chapter_url)
        if '因版权问题' in html_text:
            error_msg_idx = html_text.find('因版权问题')
            self.error_msg = html_text[error_msg_idx: html_text.find('<br', error_msg_idx)]
            return (None, None, None)

        html = etree.HTML(html_text)
        content_title = html.xpath('//*[@id="title"]/text()')
        content_title = content_title[0] if content_title else ''

        image_urls, content_list = [], []
        content_nodes = html.xpath('//*[@id="content"]')
        if content_nodes:
            content_nodes = content_nodes[0]
            content_list = [nodes.strip() for nodes in content_nodes.xpath('text()') if nodes.strip()]
            if not len(content_list): #插图页
                image_nodes = content_nodes.xpath('//*[@class="divimage"]')
                image_urls = [div.xpath('a/@href')[0].replace('http://', 'https://') for div in image_nodes]
        return (content_title, content_list, image_urls)


    @delay_time
    def _save_cover(self, path='src/cover.jpg'):
        '''保存封面'''
        if not self.book.get('cover_url'): return
        res = self._s.get(self.book['cover_url'])
        with open(path, 'wb') as f:
            f.write(res.content)


    @delay_time
    def save_image(self, img_url, proxy_host=None):
        '''保存插图'''
        if proxy_host: img_url = img_url.replace(urlparse(img_url).hostname, proxy_host)
        res = self._s.get(img_url)
        self.image_idx += 1
        file_base = '{:0>3d}'.format(self.image_idx)
        file_name = file_base + '.jpg'
        file_path = 'src/' + file_name
        if res.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(res.content)
            return (file_path, file_name, file_base)
        else:
            return (file_path, None, None)


    def clear_src(self):
        '''清理src文件夹下残存文件'''
        src_dir = 'src'
        for file_name in os.listdir(src_dir):
            if file_name not in self.src_white_list:
                file_path = os.path.join(src_dir, file_name)
                if os.path.isfile(file_path): os.remove(file_path)




if __name__ == '__main__':
    pass
        
