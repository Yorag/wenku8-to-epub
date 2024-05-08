"""
从wenku8.net下载小说，并按卷转epub
"""
import os
import sys

from create_epub import Epub, XML_TITLE_LABEL, XML_PARAGRAPH_LABEL, XML_IMAGE_LABEL
from wenku8 import Wenku8Download


#--------自定义参数------------
# 反代pic.wenku8.com的host：xxxx.xxxx.workers.dev 或 自定义域名
wenkupic_proxy_host = 'wk8-test.jsone.gq'

# epub存储目录（相对路径/绝对路径）
save_epub_dir = 'epub'

# 是否将插图第一页设为封面，若不设置就默认使用小说详情页封面
use_divimage_set_cover = True

# 每次网络请求后停顿时间，避免封IP
sleep_time = 1
#---------------------------



if not os.path.exists(save_epub_dir):
    os.makedirs(save_epub_dir)

if __name__ == '__main__':
    book_id = input('输入要下载的小说id（如 https://www.wenku8.net/book/2906.htm 的id是2906）：')
    if not book_id.isdigit(): print('book_id is valid.'); sys.exit(0)

    wk = Wenku8Download(book_id)
    if wk.error_msg: print(wk.error_msg); sys.exit(0)
    wk.sleep_time = sleep_time # 设置延迟时间

    print('\nLight Noval Title:', wk.book['title'], '\n')

    # 单独下载某一/些卷
    volume_toc = '\n'.join([str(i+1) + ': ' + it['volume'] for i,it in enumerate(wk.book['toc'])])
    print(volume_toc)
    volume_idx_list = input('输入要下载的卷索引，下载多卷用空格分割（默认0，逐卷下载）：').split()
    # 检查输入索引是否合法
    if volume_idx_list and all(map(lambda i: i.isdigit() and (1 <= int(i) <= len(wk.book['toc'])), volume_idx_list)):
        volume_idx_list = sorted(map(int, volume_idx_list))
    elif volume_idx_list == [] or '0' in volume_idx_list:
        volume_idx_list = list(map(lambda i: i+1, range(len(wk.book['toc']))))
    else:
        print('volume_id is valid.'); sys.exit(0)

    vol_idx = 0
    for it in wk.book['toc']:
        vol_idx += 1
        if vol_idx not in volume_idx_list: continue

        wk.image_idx = 0
        is_set_cover = not use_divimage_set_cover

        book_epub = Epub()
        book_epub.set_metadata(wk.book['title'], it['volume'],author=wk.book['author'], desp=wk.book['description'],
                               publisher=wk.book['publisher'], source_url=wk.book['api']['detail'],
                               tag_list=wk.book['tags'], vol_idx=vol_idx,
                               cover_path='src/cover.jpg' if not use_divimage_set_cover else None)

        print('\nStart making volume:', wk.book['title'], it['volume'])
        for chapter_title, chapter_href in it['chapter']:
            content_title, content_list, image_urls = wk.get_chapter(chapter_href)
            if wk.error_msg: print(wk.error_msg); sys.exit(0)

            # 设置HTML格式
            html_body = XML_TITLE_LABEL.format(ct=chapter_title)
            if content_list:
                print('├──', 'Start downloading chapter-text:', chapter_title)
                for p in content_list:
                    html_body += XML_PARAGRAPH_LABEL.format(p=p)
                print('│   └── Download chapter-text completed.')
            elif image_urls:
                print('├──', 'Start downloading chapter-image:', chapter_title)
                for img_url in image_urls:
                    file_path, file_name, file_base = wk.save_image(img_url, wenkupic_proxy_host)
                    if file_name:
                        if use_divimage_set_cover and img_url == image_urls[0]: # 将插图的第一张图片作为封面
                            book_epub.set_cover(file_path)
                            is_set_cover = True
                        book_epub.set_images(file_path)
                        html_body += XML_IMAGE_LABEL.format(fb=file_base, fn=file_name)
                    print('│   ├──', img_url, '->', file_path, 'success' if file_name else 'fail')
                print('│   └── Download chapter-image completed.')
            else:
                print('│   └── Downloaded empty chapter.')
            book_epub.set_html(chapter_title, html_body)  # 分卷下载，不指定第三个参数（卷名）

        if not is_set_cover: # 插图第一张图片未能设置为封面，就把缩略图作为封面
            book_epub.set_cover('src/cover.jpg')

        book_epub.pack_book(save_epub_dir)
        print('└── Packing volume completed.\n')

        wk.clear_src()

