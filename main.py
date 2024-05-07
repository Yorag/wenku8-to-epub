"""
从wenku8.net下载小说，并按卷转epub
"""
import os
import sys

from create_epub import Epub, XML_TITLE_LABEL, XML_PARAGRAPH_LABEL, XML_IMAGE_LABEL
from wenku8 import Wenku8Download
#-------------------------

# xxxx.xxxx.workers.dev 或 自定义域名
wenkupic_proxy_host = 'wenku-img.jsone.gq'

save_epub_dir = 'epub/'
#-------------------------


if not os.path.exists(save_epub_dir):
    os.makedirs(save_epub_dir)


if __name__ == '__main__':
    book_id = input('输入要下载的小说id（如 https://www.wenku8.net/book/2906.htm 的id是2906）：')
    if not book_id.isdigit(): print('book_id is valid.'); sys.exit(0)

    wk = Wenku8Download(book_id)
    if wk.error_msg: print(wk.error_msg); sys.exit(0)

    print('\nLight Noval Title:', wk.book['title'], '\n')

    vol_idx = 0
    for it in wk.book['toc']:
        book_title = wk.book['title'] + ' ' + it['volume']
        vol_idx += 1
        wk.image_idx = 0

        book_epub = Epub()
        book_epub.set_metadata(book_title, author=wk.book['author'], desp=wk.book['description'],
                               publisher=wk.book['publisher'], source_url=wk.book['api']['detail'],
                               label_list=wk.book['labels'],
                               cover_path='src/cover.jpg', vol_idx=vol_idx)

        print('start making volume:', book_title)
        for chapter_title, chapter_href in it['chapter']:
            content_title, content_list, image_urls = wk.get_chapter(chapter_href)
            if wk.error_msg: print(wk.error_msg); sys.exit(0)

            # 设置HTML格式
            html_body = XML_TITLE_LABEL.format(ct=content_title)
            if content_list:
                print('├──', 'chapter-text start:', chapter_title)
                for p in content_list:
                    html_body += XML_PARAGRAPH_LABEL.format(p=p)
                print('│   └── chapter-text finished')
            else:
                print('├──', 'chapter-image start:', chapter_title)
                for img_url in image_urls:
                    file_path, file_name, file_base = wk.save_image(img_url, wenkupic_proxy_host)
                    if file_name:
                        book_epub.set_images(file_path)
                        html_body += XML_IMAGE_LABEL.format(fb=file_base, fn=file_name)
                    print('│   ├──', img_url, 'success' if file_name else 'fail')
                print('│   └── chapter-image finished')
            book_epub.set_html(chapter_title, html_body)  # 分卷下载，不指定第三个参数（卷名）

        book_epub.pack_book(save_epub_dir)
        wk.clear_src()
        print('└── volume finished\n')

