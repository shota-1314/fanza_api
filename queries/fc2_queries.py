def insert_tag_master_query() -> str:
    """
    mst_tagテーブルに新しいタグを登録するクエリ
    """
    return """
        INSERT INTO mst_tag (tag_name, views, tag_index)
        VALUES (%(tag_name)s, 0, (SELECT COALESCE(MAX(tag_index), 0) + 1 FROM mst_tag))
        ON CONFLICT (tag_name) DO NOTHING
    """

