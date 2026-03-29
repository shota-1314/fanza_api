import subprocess
import sys
import os

def run_script(script_name):
    """
    指定されたPythonスクリプトをサブプロセスとして実行する
    """
    if not os.path.exists(script_name):
        print(f"エラー: ファイルが見つかりません: {script_name}")
        return

    print(f"\n{'='*20}")
    print(f"実行開始: {script_name}")
    print(f"{'='*20}\n")
    
    try:
        # 現在のPythonインタプリタを使ってスクリプトを実行
        result = subprocess.run([sys.executable, script_name], check=False)
        
        if result.returncode != 0:
            print(f"\n[!] {script_name} はエラー終了しました (Exit Code: {result.returncode})")
        else:
            print(f"\n[OK] {script_name} は正常に終了しました")
            
    except Exception as e:
        print(f"\n[!] 実行中に予期せぬエラーが発生しました: {e}")

def main():
    print("バッチ処理を開始します...")
    
    # 1. FANZAランキング取得
    run_script("fetch_fanza_rank.py")
    
    # 2. アンテナサイトRSS取得
    run_script("fetch_antenna_rss.py")
    
    run_script("fetch_fc2_videos.py")
    
    print(f"\n{'='*20}")
    print("全てのバッチ処理が完了しました")
    print(f"{'='*20}")

if __name__ == "__main__":
    main()
