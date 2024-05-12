"""
wenku8下载
"""
import os
import time
import base64
from urllib.parse import urlparse

import requests
from lxml import etree


def delay_time(func):
    """类成员函数装饰器，给带有网络请求的函数追加延时"""
    def wrapper(self, *args, **kwargs):
        ret = func(self, *args, **kwargs)
        time.sleep(self.sleep_time)
        return ret
    return wrapper


class Wenku8Download:
    def __init__(self, book_id, hostname='www.wenku8.com', wenkupic_proxy_host=None, wenkuandroid_proxy_host=None):
        self.hostname = hostname
        self.wenkupic_proxy_host = wenkupic_proxy_host
        self.image_idx = 0
        self.sleep_time = 1  # 默认网络请求停顿时间1s
        # 报错信息
        self.error_msg = ''
        self.src_white_list = ['style.css', 'cover.jpg']
        self.book = {
            'id': book_id,
            'title': '',
            'publisher': '',
            'author': '',
            'status': '',  # ongoing、completed
            'cover_url': '',
            'tags': [],
            'description': '',
            'toc': [],  # [{'volume': '','chapter': []}]
            'api': {
                'detail': f'https://{self.hostname}/book/{book_id}.htm',
                'toc': 'https://www.wenku8.net{toc_path}'
            },
            'copyright': True
        }

        #------------------------
        self.wka = Wenku8AndroidDownload(wenkuandroid_proxy_host)
        self.wka.sleep_time = self.sleep_time

        self._s = requests.Session()
        self._s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0'
        })

        # 先清除src文件夹下无关文件
        self.clear_src()

        # 初始化详情页和目录
        self._get_detail()
        if self.error_msg: return
        self._get_toc()
        self._save_cover()


    @delay_time
    def _get_detail(self):
        """获取书籍详情页内容，收集元数据"""
        res = self._s.get(self.book['api']['detail'])
        html_text = res.content.decode('gbk')
        if res.status_code != 200:
            if '错误原因' in html_text:
                self._get_error_msg(html_text, '错误原因', '<br')
            else:
                self.error_msg = 'Unknow error.'
            return

        if '版权问题' in html_text: self.book['copyright'] = False

        html = etree.HTML(html_text)
        toc_path = html.xpath('//*[@id="content"]/div[1]/div[4]/div/span[1]/fieldset/div/a/@href')
        if toc_path:
            self.book['api']['toc'] = self.book['api']['toc'].format(toc_path=toc_path[0])
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

        description = html.xpath('//*[@id="content"]/div[1]/table[2]/tr/td[2]/span[last()]/text()')
        if description: self.book['description'] = '\n'.join([desp.strip() for desp in description])

    @delay_time
    def _get_toc(self):
        """获取目录"""
        html_text = self._s.get(self.book['api']['toc']).content.decode('gbk')

        html = etree.HTML(html_text)
        toc_nodes = html.xpath('/html/body/table/tr')
        volume = {}  #临时存储volume，引用列表内字典
        for cnode in toc_nodes:
            tds = cnode.xpath('td')
            if len(tds) == 1 and tds[0].xpath('@colspan'):  #通过属性判断是volume
                volume_title = tds[0].xpath('text()')[0]
                self.book['toc'].append({'volume': volume_title, 'chapter': []})
                volume = self.book['toc'][-1]
            else:
                for td in tds:
                    if td.xpath('a'):
                        chapter_href = td.xpath('a/@href')[0]
                        chapter_title = td.xpath('a/text()')[0]
                        volume['chapter'].append((chapter_title, chapter_href))

    @delay_time
    def get_chapter(self, href):
        """获取章节内容，返回章节内容"""
        if self.book['copyright']:
            return self._get_chapter_by_web(href)
        else:
            return self._get_chapter_by_android(href.split('.')[0])

    def _get_chapter_by_web(self, href):
        """通过web端获取章节内容"""
        chapter_url = self.book['api']['toc'].replace('index.htm', href)
        res = self._s.get(chapter_url)
        html_text = res.content.decode('gbk')

        if res.status_code != 200:
            error_list = [('Access denied', '</')]
            for error in error_list:
                if error[0] in html_text:
                    self._get_error_msg(html_text, error[0], error[1])
                    return (None, None, None)
            self.error_msg = 'Unknow error.'
            print('Error HTML:', html_text)
            return(None, None, None)

        html = etree.HTML(html_text)
        content_title = html.xpath('//*[@id="title"]/text()')
        content_title = content_title[0] if content_title else ''

        image_urls, content_list = [], []
        content_nodes = html.xpath('//*[@id="content"]')
        if content_nodes:
            content_nodes = content_nodes[0]
            content_list = [nodes.strip() for nodes in content_nodes.xpath('text()') if nodes.strip()]
            if not len(content_list):  #插图页
                image_nodes = content_nodes.xpath('//*[@class="divimage"]')
                image_urls = [div.xpath('a/@href')[0].replace('http://', 'https://') for div in image_nodes]
        return (content_title, content_list, image_urls)

    def _get_chapter_by_android(self, cid):
        """通过APP端获取章节内容"""
        content = self.wka.get_chapter(self.book['id'], cid, '0')
        if not content: return (None, None, None)
        image_urls, content_list = [], []
        if '<!--image-->' in content:
            image_urls = [l.strip().replace('http://', 'https://')
                          for l in content.split('<!--image-->') if l.strip()]
            content_title = image_urls.pop(0)
        else:
            content_list = [l.strip() for l in content.split() if l.strip()]
            content_title = content_list.pop(0)
        return (content_title, content_list, image_urls)


    @delay_time
    def _save_cover(self, path='src/cover.jpg'):
        """保存封面"""
        if not self.book.get('cover_url'): return
        res = self._s.get(self.book['cover_url'])
        with open(path, 'wb') as f:
            f.write(res.content)

    @delay_time
    def save_image(self, img_url):
        """保存插图"""
        if self.wenkupic_proxy_host: img_url = img_url.replace(urlparse(img_url).hostname, self.wenkupic_proxy_host)
        res = self._s.get(img_url)
        self.image_idx += 1
        _, file_name = os.path.split(img_url)
        _, file_ext = os.path.splitext(file_name)
        file_base = '{:0>3d}'.format(self.image_idx)
        file_name = file_base +  file_ext
        file_path = 'src/' + file_name
        if res.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(res.content)
            return (file_path, file_name, file_base) #('src/001.jpg', '001.jpg', '001')
        else:
            return (file_path, None, None)

    def clear_src(self):
        """清理src文件夹下残存文件"""
        src_dir = 'src'
        for file_name in os.listdir(src_dir):
            if file_name not in self.src_white_list:
                file_path = os.path.join(src_dir, file_name)
                if os.path.isfile(file_path): os.remove(file_path)

    def _get_error_msg(self, html_text, start_text, end_text):
        """从html_text中提取报错信息"""
        error_msg_idx = html_text.find(start_text)
        self.error_msg = html_text[error_msg_idx: html_text.find(end_text, error_msg_idx)]


class Wenku8AndroidDownload:
    def __init__(self, proxy_host=None):
        self.base_url = f'http://{proxy_host if proxy_host else "app.wenku8.com"}/android.php'
        self.appver = '1.19'
        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 8.0.0; Pixel MIUI/V10.1.2.0.OAGCNFI)'
        }
        self.sleep_time = 1

    @delay_time
    def _request(self, request_body):
        encrypted_request_body = base64.b64encode(request_body.encode()).decode()
        res = requests.post(self.base_url, data={'request': encrypted_request_body,
                                          'timetoken': time.time() * 1000, 'appver': self.appver},
                            headers=self.headers)
        return res

    def get_cover(self, aid, path='src/cover.jpg'):
        res = self._request('action=book&do=cover&aid=' + aid)
        if res.status_code == 200:
            with open(path, 'wb') as f:
                f.write(res.content)
            return True
        else: return False

    def get_toc(self, aid, lang_id='0'):
        res = self._request('action=book&do=list&aid=' + aid + '&t=' + lang_id)
        if res.status_code == 200:
            html_text = res.text.replace('<![CDATA[', '').replace(']]>', '')
            html = etree.HTML(html_text.encode())

            volume_nodes = html.xpath('//*[@vid]')
            for vnode in volume_nodes:
                vid = vnode.xpath('@vid')[0]
                vtitle = vnode.xpath('text()')[0].lstrip()
            pass
        else: return False

    def get_chapter(self, aid, cid, lang_id='0'):
        res = self._request('action=book&do=text&aid=' + aid + '&cid=' + cid + '&t=' + lang_id)
        if res.status_code == 200:
            return res.text
        else: return ''




if __name__ == '__main__':
    pass
