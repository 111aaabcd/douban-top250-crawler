import requests
from bs4 import BeautifulSoup
import csv
import time
import re


def crawl_douban_top250():
    base_url = "https://movie.douban.com/top250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://movie.douban.com/"
    }
    movie_data = []

    for start in range(0, 250, 25):
        url = f"{base_url}?start={start}"
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, features='html.parser')
        movie_items = soup.find_all('div', class_='item')

        for item in movie_items:
            # 排名
            rank_tag = item.find('em')
            rank = rank_tag.text.strip() if rank_tag else ""

            # 电影名 + 详情页链接
            title_tag = item.find('span', class_='title')
            title = title_tag.text.strip() if title_tag else ""
            link_tag = item.find('a')
            detail_url = link_tag['href'] if link_tag else ""

            # 评分
            rating_tag = item.find('span', class_='rating_num')
            rating = rating_tag.text.strip() if rating_tag else ""

            # 列表页短评提取
            quote_text = ""
            inq_span = item.select_one('div.bd p.quote span.inq')
            if inq_span:
                quote_text = inq_span.get_text(strip=True)
            if not quote_text:
                quote_p = item.select_one('div.bd p.quote')
                if quote_p:
                    quote_text = quote_p.get_text(strip=True)
            if not quote_text:
                all_inq = item.select('span.inq')
                for s in all_inq:
                    text = s.get_text(strip=True)
                    if text:
                        quote_text = text
                        break

            movie_data.append([rank, title, rating, quote_text, detail_url])

        time.sleep(3)
        print(f"已爬取第 {start//25 + 1} 页")

    return movie_data


def fill_missing_quotes(movie_data):
    """补全没有短评的电影：从详情页爬第一条热门短评"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    count = 0

    for row in movie_data:
        rank, title, rating, quote, detail_url = row
        if not quote and detail_url:
            try:
                response = requests.get(detail_url, headers=headers, timeout=10)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')

                # 提取第一条热门短评
                first_comment = soup.select_one('div.comment-item p span.short')
                if first_comment:
                    quote = first_comment.get_text(strip=True)
                    row[3] = quote
                    count += 1
                    print(f"已补全：{rank} {title} —— {quote}")

                time.sleep(2)  # 详情页慢一点，防封
            except Exception as e:
                print(f"补全失败 {title}: {e}")
                continue

    print(f"共补全 {count} 条短评")
    return movie_data


def save_to_csv(data):
    with open('douban_top250.csv', 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['排名', '电影名', '评分', '短评'])
        for row in data:
            # 只存前4列，去掉详情页链接
            writer.writerow(row[:4])
    print("CSV 保存完成")


if __name__ == "__main__":
    data = crawl_douban_top250()

    # 补全缺失的短评（不需要可以注释掉这行）
    data = fill_missing_quotes(data)

    # 剩余空值统一填充
    for row in data:
        if not row[3]:
            row[3] = "无官方短评"

    save_to_csv(data)
