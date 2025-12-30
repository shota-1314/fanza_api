"""
FANZA関連のSQLクエリ定義
"""

def delete_fanza_sub_query() -> str:
    """
    mst_fanza_mainテーブルの全データを削除するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        DELETE FROM mst_fanza_main
    """


def delete_fanza_sub_tag_query() -> str:
    """
    mst_fanza_main_tagテーブルの全データを削除するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        DELETE FROM mst_fanza_main_tag
    """


def delete_fanza_sub_image_query() -> str:
    """
    mst_fanza_sub_imageテーブルの全データを削除するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        DELETE FROM mst_fanza_sub_image
    """


def insert_fanza_sub_query() -> str:
    """
    mst_fanza_mainテーブルにデータを挿入するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        INSERT INTO mst_fanza_main (
            id, title, url, video_link, video_thumbnail, actor_name, actor_image, add_date
        ) VALUES (
            %(id)s, %(title)s, %(url)s, %(video_link)s, %(video_thumbnail)s, 
            %(actor_name)s, %(actor_image)s, %(add_date)s
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            url = EXCLUDED.url,
            video_link = EXCLUDED.video_link,
            video_thumbnail = EXCLUDED.video_thumbnail,
            actor_name = EXCLUDED.actor_name,
            actor_image = EXCLUDED.actor_image,
            add_date = EXCLUDED.add_date
    """


def insert_fanza_sub_tag_query() -> str:
    """
    mst_fanza_main_tagテーブルにタグを挿入するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        INSERT INTO mst_fanza_main_tag (
            id, actor_id, tag_name, add_date
        ) VALUES (
            %(id)s, %(actor_id)s, %(tag_name)s, %(add_date)s
        )
        ON CONFLICT (id, actor_id, tag_name) DO NOTHING
    """


def insert_fanza_sub_image_query() -> str:
    """
    mst_fanza_sub_imageテーブルに画像を挿入するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        INSERT INTO mst_fanza_sub_image (
            id, image_url, add_date
        ) VALUES (
            %(id)s, %(image_url)s, %(add_date)s
        )
        ON CONFLICT (id, image_url) DO NOTHING
    """


def check_tag_exists_query() -> str:
    """
    mst_tagテーブルにタグが存在するかチェックするクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        SELECT COUNT(*) as count
        FROM mst_tag
        WHERE tag_name = %(tag_name)s
    """


def get_existing_content_ids_query() -> str:
    """
    mst_fanza_mainテーブルに既に登録されているcontent_id一覧を取得するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        SELECT id
        FROM mst_fanza_main
    """


def get_fanza_titles_query() -> str:
    """
    mst_fanza_mainテーブルからtitleとactor_nameを取得するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        SELECT id, title, actor_name
        FROM mst_fanza_main
        WHERE title IS NOT NULL AND actor_name IS NOT NULL
        ORDER BY add_date DESC
    """


def get_tag_names_query() -> str:
    """
    mst_tagテーブルからtag_nameを取得するクエリ
    
    Returns
    -------
    str
        SQLクエリ文字列
    """
    return """
        SELECT tag_name, views, tag_index
        FROM mst_tag
        ORDER BY tag_index
    """

