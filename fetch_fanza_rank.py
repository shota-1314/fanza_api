"""
FANZAランキング取得スクリプト
FANZA APIからランキングトップ100の情報を取得し、データベースに登録する
"""
import os
import sys
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from dotenv import load_dotenv
from common.db import Database
from utils.gemini_client import GeminiClient
from queries.fanza_queries import (
    delete_fanza_sub_query,
    delete_fanza_sub_tag_query,
    delete_fanza_sub_image_query,
    insert_fanza_sub_query,
    insert_fanza_sub_tag_query,
    insert_fanza_sub_image_query,
    check_tag_exists_query,
    get_tag_names_query
)

# 環境変数の読み込み
load_dotenv()

# ==========================================
# 設定エリア
# ==========================================
FANZA_API_KEY = os.getenv("FANZA_API_KEY")
AFFILIATE_ID = os.getenv("FANZA_AFFILIATE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not FANZA_API_KEY:
    print("エラー: 環境変数FANZA_API_KEYが設定されていません")
    sys.exit(1)

if not AFFILIATE_ID:
    print("エラー: 環境変数FANZA_AFFILIATE_IDが設定されていません")
    sys.exit(1)

# Geminiクライアントの初期化
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = GeminiClient(GEMINI_API_KEY)
        print("Gemini APIクライアントを初期化しました")
    except Exception as e:
        print(f"Gemini APIクライアント初期化エラー: {e}")
else:
    print("警告: 環境変数GEMINI_API_KEYが設定されていません。タイトル生成はスキップされます。")


# ==========================================
# ヘルパー関数
# ==========================================
def is_vr_video(genre_list: list) -> bool:
    """
    VR動画か否かを判断
    
    Parameters
    ----------
    genre_list : list
        動画に紐づいているジャンル
    
    Returns
    -------
    bool
        VR動画か否か
    """
    genre_value = 'VR'
    
    for genre in genre_list:
        if genre_value in genre.get('name', ''):
            return True
    
    return False


def get_actor_image(actor_id: str) -> str:
    """
    女優IDからサムネURL取得
    
    Parameters
    ----------
    actor_id : str
        女優ID
    
    Returns
    -------
    str
        サムネURL
    """
    res_url = ''
    
    # URL生成
    url = 'https://api.dmm.com/affiliate/v3/ActressSearch?api_id={api_id}&affiliate_id={affiliate_id}&actress_id={actor_id}&output=json'.format(
        api_id=FANZA_API_KEY,
        affiliate_id=AFFILIATE_ID,
        actor_id=actor_id
    )
    
    try:
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        res_json = res.json()
        
        if 'actress' in res_json.get('result', {}) and len(res_json['result']['actress']) > 0:
            actress = res_json['result']['actress'][0]
            if 'imageURL' in actress and 'small' in actress['imageURL']:
                res_url = actress['imageURL']['small']
    except requests.exceptions.HTTPError as e:
        print(f'HTTPエラーが発生しました（女優画像取得）: {e}')
    except Exception as e:
        print(f'女優画像取得エラー: {e}')
    
    return res_url


def get_tag_list(genre_list: list, db: Database) -> list:
    """
    一致するタグのみを取得
    
    Parameters
    ----------
    genre_list : list
        ジャンルリスト
    db : Database
        データベースインスタンス
    
    Returns
    -------
    list
        タグ名のリスト
    """
    res_tag_list = []
    
    for genre in genre_list:
        tag_name = genre.get('name', '')
        if tag_name and search_tag(tag_name, db):
            res_tag_list.append(tag_name)
    
    return res_tag_list


def search_tag(tag: str, db: Database) -> bool:
    """
    mst_tagテーブルにタグが存在するかチェック
    
    Parameters
    ----------
    tag : str
        タグ名
    db : Database
        データベースインスタンス
    
    Returns
    -------
    bool
        タグが存在するか否か
    """
    try:
        results = db.query(check_tag_exists_query(), {'tag_name': tag})
        if results and len(results) > 0:
            return results[0].get('count', 0) > 0
        return False
    except Exception as e:
        print(f"タグ検索エラー（{tag}）: {e}")
        return False


def register_fanza_sub(
    db: Database,
    content_id: str,
    title: str,
    url: str,
    video_link: str,
    video_thumbnail: str,
    actor_name: str,
    actor_image: str,
    add_date: str
) -> None:
    """
    mst_fanza_mainテーブルにデータを登録
    
    Parameters
    ----------
    db : Database
        データベースインスタンス
    content_id : str
        コンテンツID
    title : str
        タイトル
    url : str
        URL
    video_link : str
        動画リンク
    video_thumbnail : str
        動画サムネイル
    actor_name : str
        女優名
    actor_image : str
        女優画像URL
    add_date : str
        登録日付（YYYY-MM-DD形式）
    """
    try:
        db.insert(insert_fanza_sub_query(), {
            'id': content_id,
            'title': title,
            'url': url,
            'video_link': video_link,
            'video_thumbnail': video_thumbnail,
            'actor_name': actor_name,
            'actor_image': actor_image,
            'add_date': add_date
        })
        print(f'登録成功: {content_id} - {title}')
    except Exception as e:
        print(f'登録失敗（{content_id}）: {e}')
        raise


def register_fanza_sub_tag(
    db: Database,
    content_id: str,
    actor_id: str,
    tag: str,
    add_date: str
) -> None:
    """
    mst_fanza_main_tagテーブルにタグを登録
    
    Parameters
    ----------
    db : Database
        データベースインスタンス
    content_id : str
        コンテンツID
    actor_id : str
        女優ID
    tag : str
        タグ名
    add_date : str
        登録日付（YYYY-MM-DD形式）
    """
    try:
        db.insert(insert_fanza_sub_tag_query(), {
            'id': content_id,
            'actor_id': actor_id,
            'tag_name': tag,
            'add_date': add_date
        })
    except Exception as e:
        print(f'タグ登録失敗（{content_id}, {tag}）: {e}')
        raise


def register_fanza_sub_image(
    db: Database,
    content_id: str,
    image_url: str,
    add_date: str
) -> None:
    """
    mst_fanza_sub_imageテーブルに画像を登録
    
    Parameters
    ----------
    db : Database
        データベースインスタンス
    content_id : str
        コンテンツID
    image_url : str
        画像URL
    add_date : str
        登録日付（YYYY-MM-DD形式）
    """
    try:
        db.insert(insert_fanza_sub_image_query(), {
            'id': content_id,
            'image_url': image_url,
            'add_date': add_date
        })
    except Exception as e:
        print(f'画像登録失敗（{content_id}）: {e}')
        raise


def delete_fanza_list(db: Database) -> None:
    """
    mst_fanza_mainとmst_fanza_main_tagテーブルの全データを削除
    
    Parameters
    ----------
    db : Database
        データベースインスタンス
    """
    try:
        # DELETE文は直接executeする
        with db.db_connection.cursor() as cur:
            cur.execute(delete_fanza_sub_tag_query())
            cur.execute(delete_fanza_sub_image_query())
            cur.execute(delete_fanza_sub_query())
        print('削除完了')
    except Exception as e:
        print(f'削除失敗: {e}')
        raise


# ==========================================
# メイン処理
# ==========================================
def main():
    print("FANZAランキング取得処理を開始します...")
    
    # 現在の日付をYYYY-MM-DD形式で取得
    today = datetime.now()
    today_date = today.strftime("%Y-%m-%d")
    
    # データベース接続
    db = Database.get_instance()
    
    try:
        # mst_tagからtag_nameを取得
        print("mst_tagからタグ名を取得しています...")
        tag_records = db.query(get_tag_names_query())
        
        if not tag_records:
            print("タグデータがありません。処理を終了します。")
            return
        
        print(f"{len(tag_records)}件のタグを取得しました。")
        
        # トランザクション開始
        db.start_transaction()
        
        try:
            # 前日登録リストを全削除
            delete_fanza_list(db)
            
            # 各タグごとに処理
            all_videos = {}  # content_idをキーとして重複を避ける
            registered_count = 0
            skipped_count = 0
            hits_per_request = 50  # 1リクエストあたり50件
            
            for tag_idx, tag_record in enumerate(tag_records, 1):
                tag_name = tag_record.get('tag_name', '')
                if not tag_name:
                    continue
                
                print(f"\n[{tag_idx}/{len(tag_records)}] タグ「{tag_name}」で検索中...")
                
                # キーワード検索で50件取得
                encoded_keyword = quote(tag_name, safe='')
                url = 'https://api.dmm.com/affiliate/v3/ItemList?api_id={api_id}&affiliate_id={affiliate_id}&site=FANZA&service=digital&floor=videoa&hits={hits}&keyword={keyword}&sort=rank&output=json'.format(
                    api_id=FANZA_API_KEY,
                    affiliate_id=AFFILIATE_ID,
                    hits=hits_per_request,
                    keyword=encoded_keyword
                )
                
                try:
                    res = requests.get(url, timeout=30)
                    res.raise_for_status()
                    res_json = res.json()
                    items = res_json.get('result', {}).get('items', [])
                    
                    if not items:
                        print(f"  タグ「{tag_name}」: データが見つかりませんでした。")
                        continue
                    
                    print(f"  タグ「{tag_name}」: {len(items)}件取得")
                    
                    # 各動画を処理
                    for video in items:
                        try:
                            content_id = video.get('content_id', '')
                            if not content_id:
                                continue
                            
                            # 既に登録済みの動画はスキップ（重複回避）
                            if content_id in all_videos:
                                continue
                            
                            # VR動画をスキップ
                            genre_list = video.get('iteminfo', {}).get('genre', [])
                            if is_vr_video(genre_list):
                                skipped_count += 1
                                continue
                            
                            # 動画URLを生成
                            video_url = 'https://cc3001.dmm.co.jp/litevideo/freepv/{first}/{second}/{video_id}/{video_id}mhb.mp4'.format(
                                first=content_id[0],
                                second=content_id[0:3],
                                video_id=content_id
                            )
                            
                            # 女優情報を取得
                            actress_list = video.get('iteminfo', {}).get('actress', [])
                            if not actress_list:
                                skipped_count += 1
                                continue
                            
                            actress = actress_list[0]
                            actor_name = actress.get('name', '')
                            actor_id = actress.get('id', '')
                            
                            if not actor_name:
                                skipped_count += 1
                                continue
                            
                            if not actor_id:
                                skipped_count += 1
                                continue
                            
                            # 女優画像を取得
                            actor_image = get_actor_image(actor_id) if actor_id else ''

                            # タイトル変換処理
                            title = video.get('title', '')
                            if gemini_client and title:
                                try:
                                    optimized_title = gemini_client.generate_seo_title(title, actor_name)
                                    if optimized_title and not optimized_title.startswith("Error"):
                                        print(f"  タイトル変換: {title[:15]}... -> {optimized_title[:15]}...")
                                        title = optimized_title
                                    # API制限考慮の待機
                                    time.sleep(2) 
                                except Exception as e:
                                    print(f"  タイトル変換エラー（{content_id}）: {e}")
                            
                            # メインテーブルに登録
                            register_fanza_sub(
                                db,
                                content_id,
                                title,
                                video.get('affiliateURL', ''),
                                video_url,
                                video.get('imageURL', {}).get('large', ''),
                                actor_name,
                                actor_image,
                                today_date
                            )

                            # サンプル画像を登録
                            sample_images = video.get('sampleImageURL', {}).get('sample_l', [])
                            # 0番目はスキップし、1番目以降から最大5枚を取得
                            if sample_images and len(sample_images['image']) > 1:
                                target_images = sample_images['image'][1:6]  # インデックス1から5枚分（1,2,3,4,5）
                                for img_url in target_images:
                                    register_fanza_sub_image(
                                        db,
                                        content_id,
                                        img_url,
                                        today_date
                                    )
                            
                            # タグを取得して登録
                            tag_list = get_tag_list(genre_list, db)
                            for tag in tag_list:
                                register_fanza_sub_tag(
                                    db,
                                    content_id,
                                    actor_id,
                                    tag,
                                    today_date
                                )
                            
                            # 重複チェック用に記録
                            all_videos[content_id] = True
                            registered_count += 1
                            
                        except Exception as e:
                            print(f"  動画処理エラー（{video.get('content_id', 'unknown')}）: {e}")
                            skipped_count += 1
                            continue
                    
                except requests.exceptions.HTTPError as e:
                    print(f'  HTTPエラーが発生しました（タグ: {tag_name}）: {e}')
                    skipped_count += 1
                    continue
                except Exception as e:
                    print(f'  データ取得エラー（タグ: {tag_name}）: {e}')
                    skipped_count += 1
                    continue
            
            # コミット
            db.commit()
            print(f'\nFANZA登録情報の入れ替えが完了しました。')
            print(f'  登録日付: {today_date}')
            print(f'  登録成功: {registered_count}件')
            print(f'  スキップ: {skipped_count}件')
            
        except Exception as e:
            db.rollback()
            print(f"処理中にエラーが発生しました: {e}")
            raise
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise
    finally:
        print("処理を終了します。")


if __name__ == "__main__":
    main()

