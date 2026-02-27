"""
アンテナサイトRSS取得スクリプト
アンテナサイトのRSSから記事情報を取得し、データベースに登録する
"""
import os
import sys
import time
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from common.db import Database
from queries.antenna_queries import (
    get_active_antenna_sites_query,
    insert_antenna_item_query,
    delete_old_antenna_items_query
)

# 環境変数の読み込み
load_dotenv()

# ==========================================
# 設定エリア
# ==========================================
MAX_WORKERS = 5  # 並列処理のスレッド数
TIMEOUT = 10     # リクエストタイムアウト（秒）
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


from email.utils import parsedate_to_datetime

def parse_rss(xml_content: str, site_name: str, antenna_id: str) -> list:
    """
    RSSコンテンツをパースして記事リストを返す
    """
    items = []
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        
        # itemタグまたはentryタグを探す
        rss_items = soup.find_all(['item', 'entry'])
        
        for item in rss_items:
            try:
                # タイトル
                title_tag = item.find('title')
                title = title_tag.get_text(strip=True) if title_tag else 'No Title'
                
                # リンク
                link_tag = item.find('link')
                link = ''
                if link_tag:
                    link = link_tag.get_text(strip=True)
                    if not link:
                        link = link_tag.get('href', '')
                
                if not link:
                    continue

                # 日付パース
                date_tag = item.find(['dc:date', 'pubDate', 'updated'])
                date_str = date_tag.get_text(strip=True) if date_tag else ''
                
                dt = datetime.now()
                if date_str:
                    try:
                        # RFC 822形式 (pubDate)
                        dt = parsedate_to_datetime(date_str)
                    except:
                        try:
                            # ISO 8601形式 (dc:date, updated)
                            # 簡易的な置換で対応
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        except:
                            pass
                
                # 画像抽出
                image_url = ''
                
                # 1. media:thumbnail
                media_thumb = item.find('media:thumbnail')
                if media_thumb:
                    image_url = media_thumb.get('url', '')
                
                # 2. enclosure
                if not image_url:
                    enclosure = item.find('enclosure', type=lambda t: t and 'image' in t)
                    if enclosure:
                        image_url = enclosure.get('url', '')
                
                # 3. content:encoded / description 内の img
                if not image_url:
                    content_encoded = item.find('content:encoded')
                    description = item.find('description')
                    
                    target_content = ''
                    if description:
                        target_content = description.get_text()
                    elif content_encoded:
                        target_content = content_encoded.get_text()
                    
                    if target_content:
                        content_soup = BeautifulSoup(target_content, 'html.parser')
                        img_tag = content_soup.find('img')
                        if img_tag:
                            image_url = img_tag.get('src', '')

                # PR記事などの除外
                if 'PR' in title or '広告' in title:
                    continue

                items.append({
                    'antenna_id': antenna_id,
                    'title': title,
                    'link': link,
                    'date': dt,  # datetimeオブジェクトを渡す
                    'site_name': site_name,
                    'image_url': image_url
                })
                
            except Exception as e:
                print(f"  記事パースエラー: {e}")
                continue
                
    except Exception as e:
        print(f"RSSパースエラー ({site_name}): {e}")
    
    return items


def fetch_site_rss(site: dict) -> list:
    """
    1つのサイトのRSSを取得・パースする
    """
    site_name = site.get('name', 'Unknown')
    rss_url = site.get('rss_url')
    antenna_id = site.get('antenna_id')
    
    if not rss_url:
        return []
    
    print(f"Fetching: {site_name} ({rss_url})")
    
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(rss_url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        
        return parse_rss(response.content, site_name, antenna_id)
        
    except requests.exceptions.RequestException as e:
        print(f"  RSS取得失敗 ({site_name}): {e}")
        return []
    except Exception as e:
        print(f"  予期せぬエラー ({site_name}): {e}")
        return []


def main():
    print("アンテナサイトRSS取得処理を開始します...")
    
    # データベース接続
    db = Database.get_instance()
    
    try:
        # アンテナサイト取得
        sites = db.query(get_active_antenna_sites_query())
        
        if not sites:
            print("有効なアンテナサイトが見つかりませんでした。")
            return
        
        print(f"{len(sites)}件のアンテナサイトが見つかりました。")
        
        all_items = []
        
        # 並列処理でRSS取得
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_site = {executor.submit(fetch_site_rss, site): site for site in sites}
            
            for future in as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    items = future.result()
                    if items:
                        all_items.extend(items)
                        print(f"  -> {site['name']}: {len(items)}件の記事を取得")
                except Exception as e:
                    print(f"  -> {site['name']}: 処理中にエラーが発生しました: {e}")

        print(f"合計 {len(all_items)} 件の記事を取得しました。DBに保存します...")
        
        if not all_items:
            print("保存する記事がありません。")
            return

        # DB保存処理
        db.start_transaction()
        inserted_count = 0
        
        try:
            for item in all_items:
                # 日付のパースを試みる（失敗したら現在時刻）
                try:
                    # 簡易的な日付パース（必要に応じて強化）
                    # dateutil.parserなどが強力だが、標準ライブラリではないので簡易実装
                    # ここではそのまま文字列として渡してPostgreSQLに任せるか、現在時刻にする
                    # 今回はPostgreSQLが柔軟に解釈してくれることを期待しつつ、
                    # 明らかにフォーマットが違う場合は現在時刻を入れるロジックにするのが安全だが、
                    # 一旦そのまま渡す。
                    pass
                except:
                    item['date'] = datetime.now()

                db.insert(insert_antenna_item_query(), item)
                inserted_count += 1
            
            # 古い記事の削除（オプション）
            # db.query(delete_old_antenna_items_query())
            
            db.commit()
            print(f"DB保存完了: {inserted_count}件の記事を処理しました（重複は無視されました）。")
            
        except Exception as e:
            db.rollback()
            print(f"DB保存中にエラーが発生しました: {e}")
            raise

    except Exception as e:
        print(f"全体エラー: {e}")
    finally:
        print("処理を終了します。")


if __name__ == "__main__":
    main()
