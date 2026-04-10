import time
import re
import requests
from bs4 import BeautifulSoup
from common.db import Database
from queries.fc2_queries import insert_tag_master_query
from queries.fanza_queries import check_tag_exists_query
# ==========================================
# 設定エリア
# ==========================================
BASE_URL = "https://adult.contents.fc2.com/search/"
SEARCH_PARAMS = {
    'tag': 'ハメ撮り',
    'sort': 'daily_mylist',
    'order': 'desc'
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Cookie': 'adc=1; adult=1; age_check_done=1;'
}
MAX_PAGES = 20  # 最大取得ページ数

def insert_fc2_video(db: Database, video_id: str, title: str, tags: list, video_url: str, photo_urls: list, affiliate_url: str) -> None:
    """
    アフィリエイトリンクを含めてDBに登録する
    """
    query = """
        INSERT INTO mst_fc2_videos (
            video_id, title, tags, video_url, photo_urls, affiliate_url
        ) VALUES (
            %(video_id)s, %(title)s, %(tags)s, %(video_url)s, %(photo_urls)s, %(affiliate_url)s
        )
        ON CONFLICT (video_id) DO UPDATE SET
            title = EXCLUDED.title,
            tags = EXCLUDED.tags,
            video_url = EXCLUDED.video_url,
            photo_urls = EXCLUDED.photo_urls,
            affiliate_url = EXCLUDED.affiliate_url,
            updated_at = CURRENT_TIMESTAMP
    """
    db.insert(query, {
        'video_id': video_id,
        'title': title,
        'tags': tags,
        'video_url': video_url,
        'photo_urls': photo_urls,
        'affiliate_url': affiliate_url
    })
    
def ensure_tags_exist(db: Database, tags: list) -> None:
    """
    取得したタグがmst_tagに存在するか確認し、なければ登録する
    """
    for tag_name in tags:
        try:
            # 1. 存在チェック
            res = db.query(check_tag_exists_query(), {'tag_name': tag_name})
            if res and res[0].get('count', 0) == 0:
                # 2. 存在しない場合は新規登録
                db.insert(insert_tag_master_query(), {'tag_name': tag_name})
                print(f"  [新タグ登録] {tag_name}")
        except Exception as e:
            print(f"  タグ「{tag_name}」の確認・登録中にエラー: {e}")

def main():
    print("FC2動画のスクレイピングを開始します...")
    db = Database.get_instance()
    page = 1
    
    while True:
        if page > MAX_PAGES:
            print(f"\n最大取得ページ数（{MAX_PAGES}ページ）に到達したため終了します。")
            break

        SEARCH_PARAMS['page'] = page
        print(f"\n--- ページ {page}/{MAX_PAGES} を取得中 ---")
        
        try:
            res = requests.get(BASE_URL, params=SEARCH_PARAMS, headers=HEADERS, timeout=10)
            res.raise_for_status()
        except Exception as e:
            print(f"ページ一覧の取得に失敗しました: {e}")
            break

        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 💡究極の解決策：階層(divやsection)を無視して、ページ内の「すべてのaタグ」を取得
        a_tags = soup.find_all('a')
        
        video_ids = []
        
        for a_tag in a_tags:
            href = a_tag.get('href', '')
            
            # 「/article/」から始まるリンクだけを対象にする
            if href.startswith('/article/'):
                
                # "?tag=" が含まれているURLは除外してスキップ
                if "?tag=" in href:
                    continue
                
                # URLから数字(動画ID)のみを抽出
                match = re.search(r'/article/(\d+)', href)
                if match:
                    vid = match.group(1)
                    
                    # リストにまだ入っていない場合のみ追加（これで重複・奇数偶数問題が解決します）
                    if vid not in video_ids:
                        video_ids.append(vid)

        if not video_ids:
            print("このページに有効な動画IDがありませんでした。処理を終了します。")
            break

        print(f"{len(video_ids)}件の動画IDを取得しました。詳細ページのスクレイピングを開始します...")

        db.start_transaction()
        try:
            for video_id in video_ids:
                detail_url = f"https://adult.contents.fc2.com/article/{video_id}/"
                try:
                    detail_res = requests.get(detail_url, headers=HEADERS, timeout=10)
                    detail_res.raise_for_status()
                except Exception as e:
                    print(f"動画 {video_id} の取得に失敗: {e}")
                    continue

                detail_soup = BeautifulSoup(detail_res.text, 'html.parser')

                # 【デバッグ用】もし詳細ページが年齢確認で弾かれている場合のチェック
                if "年齢確認" in detail_soup.title.text if detail_soup.title else "":
                    print(f"  -> ID: {video_id} は年齢確認ページにリダイレクトされました。")
                    continue

                # 1. タイトル取得 (階層指定をやめ、特定のクラス内のh3を直接狙う)
                title_elem = detail_soup.select_one('.items_article_headerInfo h3')
                if not title_elem:  # 見つからなかった場合の予備
                    title_elem = detail_soup.select_one('h3')
                raw_title = title_elem.text.strip() if title_elem else "No Title"
                title = raw_title.replace('**pzxxx*xp*', '').strip()

                # 2. タグ取得 (途中の div を無視して a タグを直接取得)
                tags = []
                tag_elems = detail_soup.select('.items_article_TagArea a')
                for tag_elem in tag_elems:
                    tag_text = tag_elem.text.strip()
                    if tag_text:  # 空文字でない場合のみ追加
                        tags.append(tag_text)
                
                # タグのマスター登録（DB保存の前に行う）
                if tags:
                    ensure_tags_exist(db, tags)

                # === 3. 動画URL取得 (メタタグ または 正規表現) ===
                video_url = ""
                # Twitter等でシェアされた時に再生される動画URL（=サンプル動画）をメタタグから取得
                og_video = detail_soup.find('meta', attrs={'property': 'og:video'})
                if og_video and og_video.get('content'):
                    video_url = og_video.get('content')
                else:
                    # メタタグに無い場合は、生のHTMLテキスト全体から「.mp4」を力技で探す
                    mp4_match = re.search(r'(https?://[^"\'\s<>]+?\.mp4)', detail_res.text)
                    if mp4_match:
                        video_url = mp4_match.group(1).replace('\\/', '/')

                # === 4. 写真リスト取得 (メタタグ + 全画像からの絞り込み) ===
                # 4. 写真リスト取得
                photo_urls = []
                
                # 💡 狙っているセクション（.items_article_SampleImages）内の a タグまたは img タグを狙う
                # 階層がズレても良いように、section内の img を直接探します
                sample_section = detail_soup.select_one('section.items_article_SampleImages')
                
                if sample_section:
                    img_elems = sample_section.find_all('img')
                    for img in img_elems:
                        # 遅延読み込み対策：data-src, data-original, src の順でチェック
                        src = img.get('data-src') or img.get('data-original') or img.get('src')
                        
                        if src:
                            src = src.strip()
                            
                            # 💡 // で始まるプロトコル相対URLに https: を補完
                            if src.startswith('//'):
                                src = 'https:' + src
                            
                            # 重複を除外してリストに追加
                            if src not in photo_urls:
                                photo_urls.append(src)

                # 💡【強行突破】もし上記で見つからない場合（JS生成対策）
                # HTML全体のテキストから直接 "contents-thumbnail" を含む画像URLを正規表現で抽出
                if not photo_urls:
                    # //contents-thumbnail... または //storage... というパターンのURLを探す
                    pattern = r'//((?:contents-thumbnail\d*|storage\d*)\.fc2\.com/[^"\'\s<>]+?\.(?:jpg|jpeg|png|webp))'
                    matches = re.findall(pattern, detail_res.text)
                    for match in matches:
                        full_url = 'https://' + match.replace('\\/', '/')
                        if full_url not in photo_urls:
                            photo_urls.append(full_url)
                
                base_article_url = f"https://adult.contents.fc2.com/article/{video_id}/"
                affiliate_url = f"{base_article_url}?tag={video_id}"


                print(f"  -> ID: {video_id} | タイトル: {title[:20]}... | タグ: {len(tags)}件 | 写真: {len(photo_urls)}枚")

                # DBへ登録
                insert_fc2_video(db, video_id, title, tags, video_url, photo_urls, affiliate_url)
                
                time.sleep(1.5)

            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"DB登録中にエラーが発生しました: {e}")
            raise
            
        page += 1
        time.sleep(3)

if __name__ == "__main__":
    main()