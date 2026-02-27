def get_active_antenna_sites_query() -> str:
    """
    アクティブなアンテナサイトを取得するクエリ
    """
    return """
    SELECT 
        id, 
        name, 
        url, 
        rss_url, 
        antenna_id 
    FROM 
        antenna_sites 
    WHERE 
        is_active = true
    """

def insert_antenna_item_query() -> str:
    """
    アンテナ記事を登録するクエリ
    リンクの重複時は何もしない
    """
    return """
    INSERT INTO antenna_items (
        antenna_id,
        title,
        link,
        date,
        site_name,
        image_url,
        created_at,
        updated_at
    ) VALUES (
        %(antenna_id)s,
        %(title)s,
        %(link)s,
        %(date)s,
        %(site_name)s,
        %(image_url)s,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (link) DO NOTHING
    """

def delete_old_antenna_items_query() -> str:
    """
    古い記事を削除するクエリ（例：30日以上前）
    """
    return """
    DELETE FROM antenna_items
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
    """
