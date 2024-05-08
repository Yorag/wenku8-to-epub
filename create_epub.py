"""
创建epub
"""
import os
import uuid
# from datetime import datetime
import warnings

from ebooklib import epub


XML_TITLE_LABEL = '<h1>{ct}</h1><hr/>'
XML_PARAGRAPH_LABEL = '<p>{p}</p>'
XML_IMAGE_LABEL = '''<div class="illus duokan-image-single img">
<img alt="{fb}" src="../Images/{fn}"/>
</div>'''



class Epub:
    def __init__(self):
        self.book = epub.EpubBook()
        self.title = None
        self.chapters = [] # [{'chapter': '','pages': []}, {'chapter': ''}, ...]
        self.current_page_idx = 0 # 记录设置到第几页了

        # 设置style.css
        self._set_style()

    def set_metadata(self, title, volume_title=None, author=None, lang='zh', desp=None, date=None,
                publisher=None, source_url=None, tag_list=[], cover_path=None, vol_idx: int=None):
        full_title = title + (' ' + volume_title if volume_title else '')
        self.title = full_title
        '''设置epub元数据'''
        self.book_uuid = str(uuid.uuid4())
        self.book.set_identifier(self.book_uuid)
        self.book.set_title(title)
        self.book.set_language(lang)
        self.book.add_author(author)
        if cover_path:
            with open(cover_path, 'rb') as f:
                self.book.set_cover('Images/cover.jpg', f.read())

        self.book.add_metadata('DC', 'description', desp)
        # self.book.add_metadata('DC', 'date', date if date else datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.book.add_metadata('DC', 'publisher', publisher)
        self.book.add_metadata('DC', 'creator', author)
        self.book.add_metadata('DC', 'source', source_url)
        for tag in tag_list:
            self.book.add_metadata('DC', 'subject', tag)
        self.book.add_metadata('DC', 'belongs-to-collection', self.title.split()[0])

        # 适配calibre数据
        self.book.add_metadata(None, 'meta', None,
                               {'name': 'calibre:title_sort', 'content': full_title})
        self.book.add_metadata(None, 'meta', None,
                               {'name': 'calibre:series', 'content': title})
        if vol_idx: self.book.add_metadata(None, 'meta', None,
                                           {'name': 'calibre:series_index', 'content': str(vol_idx)})


    def _set_style(self, css_file_path='src/style.css'):
        """设置css文件"""
        with open(css_file_path, 'r', encoding='utf-8') as f:
            style_data = f.read()
        css = epub.EpubItem(uid='style_nav', file_name='Styles/style.css', media_type='text/css', content=style_data)
        self.book.add_item(css)


    def set_html(self, page_title, page_content, chapter_title=None, lang='zh'):
        """设置章节内容，xhtml格式"""
        self.current_page_idx += 1
        file_name = 'Text/page-{}.xhtml'.format(self.current_page_idx)
        cont = epub.EpubHtml(title=page_title, file_name=file_name, lang=lang)
        cont.add_link(href='../Styles/style.css', rel='stylesheet', type='text/css')

        cont.set_content(page_content.encode('utf-8'))
        self.book.add_item(cont)
        # 将该页内容追加到对应卷
        if chapter_title: # 有二级目录
            for it in self.chapters:
                if it['chapter'].title == chapter_title:
                    it['pages'].append(cont)
                    return
            self.chapters.append({ 'chapter': epub.Section(chapter_title), 'pages': [cont] })
        else: # 无二级目录
            self.chapters.append({ 'chapter': cont })


    def set_images(self, file_path):
        """设置图片对象"""
        _, file_name = os.path.split(file_path)
        file_base, file_ext = os.path.splitext(file_name)
        with open(file_path, 'rb') as f:
            image = epub.EpubItem(uid='image_' + file_base, 
                                  file_name='Images/' + file_name,
                                  media_type='image/jpeg',
                                  content=f.read())
            self.book.add_item(image)


    def pack_book(self, epub_dir=''):
        """打包epub"""
        self._set_toc()
        self._set_spine()
        # 添加目录信息
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        epub_path = os.path.join(epub_dir, self.title + '.epub')
        with warnings.catch_warnings(record=True): # 忽略 UserWarning: Duplicate name 警告信息
            warnings.simplefilter('ignore', category=UserWarning)
            epub.write_epub(epub_path, self.book)


    def _set_toc(self):
        """设置目录文件。需要在设置完所有html后设置"""
        toc_list = []
        for it in self.chapters:
            if it.get('pages'): toc_list.append((it['chapter'], it['pages']))
            else: toc_list.append(it['chapter'])
        self.book.toc = tuple(toc_list)
            

    def _set_spine(self):
        self.book.spine = ['nav']
        elem_list = []
        for c in self.chapters:
            if isinstance(c['chapter'], epub.EpubHtml): elem_list.append(c['chapter'])
            else: elem_list += c['pages']
        self.book.spine += elem_list




if __name__ == '__main__':
    book = Epub()

    book.set_metadata("测试 第一卷", author="Yorag", desp="介绍内容")
    book.set_html('第一章 01',
        '<h1>第一章 01</h1><p>Introduction paragraph.</p>',
        '第一章'
        )
    book.set_html('第一章 02',
        '<h1>第一章 02</h1><p>Introduction paragraph.</p>',
        '第一章'
        )
    book.set_html('第二章 01',
        '<h1>第二章 01</h1><p>Introduction paragraph.</p>',
        '第二章'
        )
    book.set_html('第二章 02',
        '<h1>第二章 02</h1><p>Introduction paragraph.</p>',
        '第二章'
        )
    book.set_html('第三章',
        '<h1>第三章</h1><p>Introduction paragraph.</p>'
        )


    book.pack_book()