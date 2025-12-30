import os
import time
import re
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")
            
        genai.configure(api_key=self.api_key)
        
        # 成人向けコンテンツを扱うため、ブロック設定を解除(BLOCK_NONE)にします
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]

        # モデルの準備 (gemini-2.0-flashを使用)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            safety_settings=safety_settings
        )

    def generate_seo_title(self, original_title: str, actor_name: str = "", max_retries: int = 3) -> str:
        """
        Gemini APIを呼び出してタイトルを生成する関数（レート制限対応）
        
        Parameters
        ----------
        original_title : str
            元のタイトル
        actor_name : str
            活動者名（オプション）
        max_retries : int
            最大リトライ回数
        
        Returns
        -------
        str
            生成されたSEOタイトル
        """
        if not original_title:
            return ""
        
        prompt = f"""
    あなたは成人向けコンテンツの専門マーケターです。

    以下の情報を元に、Google検索で上位表示されやすく、かつユーザーが思わずクリックしたくなる
    35文字以内の記事タイトルを作成してください。

    【要件】
    1. フォーマット: [活動者名] - [魅力的なタイトル要約]

    2. 元のタイトルから「具体的なプレイ内容」「衣装」「身体的特徴」などのキーワードを抽出して盛り込むこと。

    3. 活動者名が指定されている場合は必ず含めること。

    4. 過度な煽りや嘘は書かないこと。
    
    5. 品番などの記号的な文字列は削除すること。

    【入力データ】
    活動者名: {actor_name}
    元のタイトル: {original_title}

    出力:
    """

        for attempt in range(max_retries):
            try:
                # API呼び出し
                response = self.model.generate_content(prompt)
                title = response.text.strip()
                # 出力のクリーンアップ処理
                title = self._clean_seo_title(title)
                return title
            except (google_exceptions.ResourceExhausted, Exception) as e:
                # レート制限エラー（429）の場合
                error_str = str(e)
                
                # 429エラーまたはレート制限エラーを検出
                is_rate_limit = (
                    isinstance(e, google_exceptions.ResourceExhausted) or
                    "429" in error_str or
                    "quota" in error_str.lower() or
                    "rate limit" in error_str.lower() or
                    "exceeded your current quota" in error_str.lower()
                )
                
                if is_rate_limit:
                    # リトライ待機時間を抽出（秒単位）
                    retry_seconds = 15  # デフォルト15秒
                    
                    # エラーメッセージから待機時間を抽出
                    if "retry in" in error_str.lower() or "Please retry in" in error_str:
                        match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
                        if match:
                            retry_seconds = int(float(match.group(1))) + 2  # 少し余裕を持たせる
                    
                    if attempt < max_retries - 1:
                        print(f"Gemini APIレート制限。{retry_seconds}秒待機してリトライします... (試行 {attempt + 1}/{max_retries})")
                        time.sleep(retry_seconds)
                        continue
                    else:
                        print(f"Gemini API Error (レート制限): {e}")
                        # エラー時は元のタイトルを返す（フォールバック）
                        return original_title
                else:
                    # その他のエラー
                    print(f"Gemini API Error: {e}")
                    return original_title
        
        return original_title

    def _clean_seo_title(self, title: str) -> str:
        """
        SEOタイトルから余計なテキストを除去する関数
        ハイフンより右側のタイトルのみを抽出
        
        Parameters
        ----------
        title : str
            元のタイトル
        
        Returns
        -------
        str
            クリーンアップされたタイトル
        """
        if not title:
            return title
        
        # 余計な説明文を除去
        patterns_to_remove = [
            r"以下に[、,]?要件を満たした記事タイトルを提案します[。.]?",
            r"以下[、,]?要件を満たした記事タイトルを提案します[。.]?",
            r"要件を満たした記事タイトルを提案します[。.]?",
            r"記事タイトルを提案します[。.]?",
            r"タイトルを提案します[。.]?",
            r"以下[、,]?タイトルを提案します[。.]?",
        ]
        
        for pattern in patterns_to_remove:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)
        
        # Markdown形式の太字記号を除去
        title = re.sub(r"\*\*([^*]+)\*\*", r"\1", title)  # **text** -> text
        title = re.sub(r"\*([^*]+)\*", r"\1", title)      # *text* -> text
        
        # ハイフン（-）より右側のタイトルのみを抽出するロジック
        if " - " in title:
            # " - " で分割して右側を取得
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                title = parts[1]
        elif "-" in title:
            # 単一のハイフンでも分割を試みる
            parts = title.split("-", 1)
            if len(parts) > 1:
                title = parts[1]
        
        # 先頭・末尾の空白、改行、句読点を除去
        title = title.strip()
        title = re.sub(r"^[。、\s]+", "", title)
        title = re.sub(r"[。、\s]+$", "", title)
        
        # 改行を除去
        title = re.sub(r"\n+", " ", title)
        title = title.strip()
        
        return title

