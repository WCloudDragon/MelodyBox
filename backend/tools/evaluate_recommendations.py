"""
推荐引擎离线评估（重构版新增）

方法：
- 按时间把播放历史切成 train（前 80%）/ test（后 20%）；
- 用 train 构建画像（加权平均向量 + 已听列表），调 recommend()；
- 统计 precision@k / recall@k / 多样性 / 覆盖率。

用法（安全：使用临时数据库副本，不碰真实数据）:
    cd Code/backend
    D:\\flask_env\\Scripts\\python.exe tools\\evaluate_recommendations.py [--limit 20] [--mode comprehensive]
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


def main():
    # Windows 控制台默认 GBK，强制 UTF-8 输出
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--mode', default='comprehensive',
                        choices=['comprehensive', 'hidden_gem', 'language'])
    parser.add_argument('--lang', default='zh')
    args = parser.parse_args()

    src_db = os.path.join(BACKEND_DIR, 'melodybox.db')
    tmpdir = tempfile.mkdtemp(prefix='melodybox_eval_')
    db_path = os.path.join(tmpdir, 'melodybox.db')
    if os.path.exists(src_db):
        shutil.copy2(src_db, db_path)
    else:
        print('未找到 melodybox.db，无法评估')
        return

    from config.config import Config
    Config.DB_PATH = db_path
    from app import create_app
    app = create_app()

    from services import recommender
    from services.vectors import VectorStore, _l2

    with app.app_context():
        db = app.get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT song_id, played_at FROM play_history '
            'WHERE song_id IS NOT NULL ORDER BY played_at'
        )
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()

        # 去重保序：每首歌只取第一次播放时间
        seen = set()
        ordered = []
        for r in rows:
            if r['song_id'] not in seen:
                seen.add(r['song_id'])
                ordered.append(r['song_id'])

        if len(ordered) < 10:
            print(f'历史歌曲太少（{len(ordered)}），无法评估')
            return

        split = int(len(ordered) * 0.8)
        train_ids = ordered[:split]
        test_ids = set(ordered[split:])

        vs = VectorStore.load(db)
        text_parts = [vs.text_embedding(sid) for sid in train_ids if vs.has_text(sid)]
        audio_parts = [vs.audio_embedding(sid) for sid in train_ids if vs.has_audio(sid)]

        if not text_parts:
            print('train 集合无向量，无法评估')
            return

        text_vec = _l2(np.mean(np.stack(text_parts), axis=0).astype(np.float32))
        audio_vec = (_l2(np.mean(np.stack(audio_parts), axis=0).astype(np.float32))
                     if audio_parts else None)

        # 写入评估用画像（version=99 标记，避免与真实画像混淆）
        cursor = db.cursor()
        cursor.execute(
            '''INSERT INTO user_profiles
               (user_id, text_vec, audio_vec, genre_dist, lang_dist,
                recent_ids, played_ids, version, updated_at)
               VALUES (1, ?, ?, '{}', '{}', ?, ?, 99, datetime('now','localtime'))
               ON CONFLICT(user_id) DO UPDATE SET
                 text_vec = excluded.text_vec,
                 audio_vec = excluded.audio_vec,
                 recent_ids = excluded.recent_ids,
                 played_ids = excluded.played_ids,
                 version = 99,
                 updated_at = datetime('now','localtime')''',
            (
                text_vec.tobytes(),
                audio_vec.tobytes() if audio_vec is not None else None,
                json.dumps(train_ids),
                json.dumps(train_ids),
            )
        )
        db.commit()
        cursor.close()

        kwargs = {}
        if args.mode == 'language':
            kwargs['lang'] = args.lang
        rec = recommender.recommend(
            db, user_id=1, mode=args.mode, limit=args.limit, seed=42, **kwargs
        )
        rec_ids = {r['song_id'] for r in rec}

        hits = rec_ids & test_ids
        precision = len(hits) / max(1, len(rec_ids))
        recall = len(hits) / max(1, len(test_ids))
        artists = {r['artist'] for r in rec if r.get('artist')}
        diversity = len(artists) / max(1, len(rec))
        coverage = len(rec_ids) / max(1, len(vs.text_song_set))

        print('=' * 60)
        print(f'评估模式        : {args.mode} (limit={args.limit})')
        print(f'train 歌曲数    : {len(train_ids)}')
        print(f'test  歌曲数    : {len(test_ids)}')
        print(f'precision@{args.limit} : {precision:.3f} ({len(hits)}/{len(rec_ids)})')
        print(f'recall@{args.limit}   : {recall:.3f} ({len(hits)}/{len(test_ids)})')
        print(f'多样性(歌手)    : {diversity:.3f}')
        print(f'覆盖率          : {coverage:.3f}')
        print('=' * 60)
        print('推荐 Top-10:')
        for r in rec[:10]:
            print(f'  {r["title"][:30]:<32} {r["artist"][:16]:<18} score={r["score"]:.3f} '
                  f'{"★命中" if r["song_id"] in test_ids else ""}')

        db.close()

    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    main()
