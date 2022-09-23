# -*- coding: utf-8 -*-
import os
import requests
import itertools as it
import random
import json
import re
from multiprocessing.pool import ThreadPool
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from os.path import splitext
from a_parser import AParser
from bs4 import BeautifulSoup
from slugify import slugify
from html_sanitizer import sanitizer
from time import sleep

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# **************************************************************************
api = AParser('http://127.0.0.1:9091/API', 'aHTt%a$U7Cl6')
# to = 'ru'
# langs = (
#     'bg', 'cs', 'da', 'de', 'el', 'es', 'et', 'fi', 'fr', 'hu', 'it', 'ja',
#     'lt', 'lv', 'nl', 'pl', 'pt_br', 'ro', 'ru', 'sk', 'sl', 'sv'
# )
langs = ('es',)
threads = 1
use_proxy = 0
# urls = [line.rstrip('\n') for line in open('sources.txt', encoding="utf-8")]
# **************************************************************************


def fast_translate(text, to):
    if use_proxy:
        transl_json = api.oneRequest('DeepL::Translator', to, text)
    else:
        transl_json = api.oneRequest(
            'DeepL::Translator', to, text,
            options=[
                {
                    'type': 'override',
                    'id': 'useproxy',
                    'value': 0
                }
            ]
        )
    api.waitForTask(transl_json)
    transl_res = transl_json['data']['resultString']
    return transl_res


def translate_content(text, to):
    ###########################
    codes = {}
    soup = BeautifulSoup(text, 'html.parser')
    codes1 = soup.find_all('code')
    for code in codes1:
        id = '#' + str(random.randint(1111, 9999))
        codes[id] = code
        code.replace_with(id)

    pre = {}
    pres = soup.find_all('pre')
    for co in pres:
        id = '#' + str(random.randint(1111, 9999))
        pre[id] = co
        co.replace_with(id)

    ###########################

    with open('data/res_soup.html', 'w', encoding='utf-8') as f:
        f.write(soup.get_text('\n'))

    text_str = str(soup).strip()
    cnt = it.count()
    html_tags = {}

    def replace(tag, html_tags, cnt):
        if tag not in html_tags:
            html_tags[tag] = f' <{next(cnt)}> '
        return html_tags[tag]

    text_lambda = re.sub(
        r'(<.*?>)', lambda x: replace(x.group(1), html_tags, cnt), text_str
    ).replace('#', ' #').replace('*', '* ')

    html_tags2 = {}
    for key, value in html_tags.items():
        html_tags2[value] = key

    # if use_proxy:
    #     transl_json = api.oneRequest('DeepL::Translator', to, text_lambda)
    # else:
    #     transl_json = api.oneRequest(
    #         'DeepL::Translator', to, text_lambda,
    #         options=[
    #             {
    #                 'type': 'override',
    #                 'id': 'useproxy',
    #                 'value': 0
    #             }
    #         ]
    #     )
    # api.waitForTask(transl_json)
    # transl_res = transl_json['data']['resultString']
    transl_res = text_lambda
    with open('data/res1.html', 'w', encoding='utf-8') as f:
        f.write(text_lambda)

    clean_res = transl_res.replace('< ', '<').replace(' >', '>').replace(
        '. >', '>').replace('< .', '<').replace('.>', '>').replace('.>', '>')
    pattern = '|'.join(sorted(html_tags2))
    text_f = re.sub(
        pattern, lambda m: html_tags2.get(m.group(0)), clean_res
    )

    for word, initial in codes.items():
        text_f = text_f.replace(str(word), str(initial))
    for word, initial in pre.items():
        text_f = text_f.replace(str(word), str(initial))
    text_res = BeautifulSoup(text_f, 'html.parser').prettify()
    return str(text_res).replace('\n', '').replace('<p> </p>', '').replace(
        '& amp;', '').replace('<p></p>', '')


def clean_attrs(html, domain):
    """Очистка атрибутов тегов"""
    my_settings = dict(sanitizer.DEFAULT_SETTINGS)
    domain = domain.replace('www.', '')

    def sanitize_href(href, domain=domain):
        if (href.startswith(('/', 'mailto:', 'http:', 'https:', '#', 'tel:'))
                and domain not in href):
            return href
        return '#'

    # Add your changes
    my_settings['tags'].add('img')
    my_settings['tags'].add('code')
    my_settings['tags'].add('pre')
    my_settings['tags'].add('blockquote')
    my_settings['tags'].add('figure')
    my_settings['tags'].add('figcaption')
    my_settings['tags'].add('table')
    my_settings['tags'].add('tbody')
    my_settings['tags'].add('tr')
    my_settings['tags'].add('td')
    my_settings['separate'].add('figure')
    my_settings['separate'].add('tr')
    my_settings['separate'].add('td')
    my_settings['empty'].add('img')
    my_settings['attributes'].update({'img': ('src',)})
    my_settings['attributes'].update({'a': ('href',)})
    my_settings['sanitize_href'] = sanitize_href
    # Use it
    s = sanitizer.Sanitizer(settings=my_settings)
    clean_result = s.sanitize(html)
    soup = BeautifulSoup(clean_result, 'html.parser')

    # clean empty links
    empty_links = soup.find_all('a', href='#')
    for link in empty_links:
        link.unwrap()

    return str(soup)


def download_images(content, slug):
    soup = BeautifulSoup(str(content), 'html.parser')
    num = 0
    for img in soup.findAll('img'):
        num = num + 1
        if '.' not in str(img):
            img.extract()
        else:
            ext = splitext(img['src'])[1].split('?')[0]

            imx = img['src']
            if 'http' not in imx:
                imx = 'https:' + img['src']
            img_path = 'images/' + slug + '/' + str(num) + ext
            if not os.path.isfile(img_path):
                page = requests.get(imx, verify=False)
                if page.status_code == 200:
                    with open(img_path, 'wb') as f:
                        f.write(page.content)

                    img['src'] = img_path

    return str(soup)


def load_json(domain, post_id):
    """Загрузка контента"""
    # post_data = json.loads(requests.get(
    #     f'https://{domain}/wp-json/wp/v2/posts/{str(post_id).strip()}',
    #     verify=False).text)
    post_data = json.loads(open('data/post_data.json', 'r').read())
    title = re.sub('&(.*?);', '', str(post_data['title']['rendered']))

    content = BeautifulSoup(post_data['content']['rendered'], 'html.parser')

    del_ids = ['ez-toc-container', 'toc_container']
    for del_id in del_ids:
        for div in content.find_all('div', id=del_id):
            div.decompose()

    clean_content = clean_attrs(str(content), domain)

    # cat_id = post_data['categories'][0]
    # post_category = json.loads(requests.get(
    #     f'https://{domain}/wp-json/wp/v2/Categories/{str(cat_id)}',
    #     verify=False).text.replace('&amp;', ' and ').replace(
    #     '&gt;', ' and ').strip())
    post_category = json.loads(open('data/cat_data.json', 'r').read())
    cat_title = post_category['name']
    return {
        'title': title,
        'slug': slugify(title),
        'content': clean_content,
        'cat_title': cat_title,
        'cat_slug': slugify(cat_title)
    }


# **************************************************************************

def work(article_address):
    try:
        domain, post_id = article_address.split('|')
        post = load_json(domain, post_id)

        slug = post.get('slug')
        cat_slug = post.get('cat_slug')
        content = download_images(post.get('content'), post.get('slug'))

        transl_content = translate_content(content, 'ru')

        with open('data/res.html', 'w', encoding='utf-8') as f:
            f.write(transl_content)

        # os.makedirs('articles/' + slug)
        # os.makedirs('images/' + slug)

        # for to in langs:
        #     title = fast_translate(post.get('title'), to)
        #     cat = fast_translate(post.get('cat_title'), to)
        #     transl_content = translate_content(content, to)
        #
        #     content_file = 'articles/' + slug + '/' + to + '.txt'
        #     with open(content_file, 'w', encoding='utf-8') as f:
        #         f.write(transl_content)
        #
        #     with open(f'data/multikey_{to}.txt', 'a', encoding='utf-8') as f:
        #         f.write(
        #             f'{title}|{cat}|'
        #             f'[GETFILECONTENT-(articles\\{slug}\\{to}.txt)]|'
        #             f'{slug}|{cat_slug}\n'
        #         )
        #
        #     print(f'Done: {to} - {title}')
        #     sleep(5)

    except Exception as e:
        raise e


# pool = ThreadPool(threads)
# result = pool.map(work, urls)
# pool.close()
# pool.join()
with open('data/sources.txt', 'r', encoding='utf-8') as file:
    url = file.readline().rstrip()

work(url)
