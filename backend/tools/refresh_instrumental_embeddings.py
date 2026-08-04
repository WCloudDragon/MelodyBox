"""
仅重刷纯音乐歌曲的 embedding 向量（lang 字段已修正后，向量前缀需同步）。

运行方式：cd backend && python tools/refresh_instrumental_embeddings.py
"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.embedding import build_song_text, encode_songs_batch, embedding_to_blob, is_available
from config.recommend_config import TEXT_VECTOR_VERSION

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'melodybox.db')

def main():
    if not is_available():
        print('错误: fastembed 未安装，请先运行: pip install fastembed')
        sys.exit(1)

    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row

    # 查找所有纯音乐占位文本的歌曲
    cursor = db.execute(
        "SELECT id, title, artist, genre, year, lyrics, lang FROM songs "
        "WHERE lyrics LIKE '%纯音乐%请欣赏%' AND EXISTS ("
        "  SELECT 1 FROM song_vectors v WHERE v.song_id = songs.id "
        "  AND v.source = 'local' AND v.text_vec IS NOT NULL"
        ")"
    )
    songs = [dict(row) for row in cursor.fetchall()]
    cursor.close()

    if not songs:
        print('没有需要重刷的纯音乐歌曲')
        db.close()
        return

    print(f'需要重刷 {len(songs)} 首纯音乐歌曲的 embedding...')

    batch_size = 32
    updated = 0
    cursor = db.cursor()

    for offset in range(0, len(songs), batch_size):
        batch = songs[offset:offset + batch_size]
        embeddings = encode_songs_batch(batch, progress_callback=None)

        for song, emb in zip(batch, embeddings):
            blob = embedding_to_blob(emb)
            cursor.execute(
                '''INSERT INTO song_vectors (song_id, source, text_vec, text_version, updated_at)
                   VALUES (?, 'local', ?, ?, datetime('now','localtime'))
                   ON CONFLICT(song_id, source) DO UPDATE SET
                     text_vec = excluded.text_vec,
                     text_version = excluded.text_version,
                     updated_at = datetime('now','localtime')''',
                (song['id'], blob, TEXT_VECTOR_VERSION)
            )
            # 同步旧列，保持兼容
            cursor.execute('UPDATE songs SET embedding = ? WHERE id = ?', (blob, song['id']))

        db.commit()
        updated += len(batch)
        print(f'  进度: {updated}/{len(songs)}')

    cursor.close()
    db.close()
    from services.vectors import invalidate
    invalidate()
    print(f'完成: 已重刷 {updated} 首歌曲的 embedding（向量缓存已失效）')

if __name__ == '__main__':
    main()
