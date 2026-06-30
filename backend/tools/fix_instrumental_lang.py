"""
扫描纯音乐占位文本的歌曲，用标题+歌手重判语言。
修改 scanner.detect_language 后，需重扫才能更新已有数据。本脚本用于批量修复已有数据。
"""
import sys
import os
import sqlite3
import io

# 修复 Windows GBK 编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scanner import detect_language

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'melodybox.db')

def fix():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # 查找所有含纯音乐占位文本的歌曲
    cur = db.execute("SELECT id, title, artist, lyrics, lang FROM songs WHERE lyrics LIKE '%纯音乐%请欣赏%'")
    rows = cur.fetchall()
    print(f'找到 {len(rows)} 首纯音乐歌曲需要检查')

    fixed = 0
    for row in rows:
        old_lang = row['lang']
        new_lang = detect_language(row['title'], row['lyrics'], row['artist'])
        if new_lang and new_lang != old_lang:
            db.execute('UPDATE songs SET lang = ? WHERE id = ?', (new_lang, row['id']))
            print(f'  修复: [{old_lang}]→[{new_lang}] {row["title"]} - {row["artist"]}')
            fixed += 1
        else:
            print(f'  保持: [{old_lang}] {row["title"]} - {row["artist"]}')

    if fixed > 0:
        db.commit()
        print(f'\n共修复 {fixed} 首歌曲的语言标注')
    else:
        print('\n无需修复')

    # 同时检查被误判为 ko 的纯音乐
    cur2 = db.execute("SELECT id, title, artist, lyrics, lang FROM songs WHERE lang = 'ko' AND lyrics LIKE '%纯音乐%'")
    ko_rows = cur2.fetchall()
    if ko_rows:
        print(f'\n额外检查 {len(ko_rows)} 首被标注为韩语的纯音乐:')
        for row in ko_rows:
            new_lang = detect_language(row['title'], row['lyrics'], row['artist'])
            if new_lang and new_lang != 'ko':
                db.execute('UPDATE songs SET lang = ? WHERE id = ?', (new_lang, row['id']))
                print(f'  修复: [ko]→[{new_lang}] {row["title"]} - {row["artist"]}')
                fixed += 1
        db.commit()

    db.close()

if __name__ == '__main__':
    fix()
