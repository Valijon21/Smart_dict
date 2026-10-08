"""
Vocab Master — ma'lumotlar bazasi qatlami.
SQLite orqali so'zlar, progress va statistika saqlanadi.
Dublikatlarni oldini olish: english UNIQUE COLLATE NOCASE.
"""
import sys
import sqlite3
import datetime
import csv
import json
import re
import shutil
from pathlib import Path
from contextlib import contextmanager
try:
    from core import phonetics
except ImportError:
    import phonetics

try:
    from core.fsrs import FSRSv5, FSRSCard, Rating, CardState
except ImportError:
    try:
        from fsrs import FSRSv5, FSRSCard, Rating, CardState
    except ImportError:
        FSRSv5 = None
        FSRSCard = None
        Rating = None
        CardState = None

try:
    from utils.logger import get_logger, get_app_dir
    from utils import text_search_utils
except ImportError:
    from logger import get_logger, get_app_dir
    import text_search_utils

logger = get_logger("database")

# SQL ORDER BY whitelist — f-string injection xavfini bartaraf etadi.
# Yangi sort qiymati kerak bo'lsa, shu ro'yxatga qo'shing.
_ALLOWED_ORDER_BY: frozenset[str] = frozenset({
    "created_at DESC",
    "created_at ASC",
    "english ASC",
    "english DESC",
    "uzbek ASC",
    "uzbek DESC",
    "id ASC",
    "id DESC",
    "w.id ASC",
    "w.id DESC",
    "w.created_at DESC",
    "w.created_at ASC",
    "w.english ASC",
    "w.english DESC",
    "box_level ASC",
    "box_level DESC",
    "correct_count DESC",
    "wrong_count DESC",
    "status ASC",
    "status DESC",
})



def migrate_sm2_to_fsrs_if_needed(conn: sqlite3.Connection) -> int:
    """Mavjud SM-2 takrorlash parametrlarini FSRS v5 barqarorlik va qiyinlik ko'rsatkichlariga avtomatik o'tkazish."""
    if FSRSv5 is None:
        return 0
    try:
        rows = conn.execute(
            """
            SELECT word_id, ease_factor, interval_days, repetitions, wrong_count, last_reviewed
            FROM progress
            WHERE (fsrs_stability IS NULL OR fsrs_stability = 0.0)
              AND (repetitions > 0 OR interval_days > 0 OR (ease_factor IS NOT NULL AND ease_factor != 2.5))
            """
        ).fetchall()

        if not rows:
            return 0

        updates = []
        for r in rows:
            card = FSRSv5.from_sm2(
                ease_factor=r["ease_factor"] if r["ease_factor"] is not None else 2.5,
                interval_days=r["interval_days"] if r["interval_days"] is not None else 0,
                repetitions=r["repetitions"] if r["repetitions"] is not None else 0,
                wrong_count=r["wrong_count"] if r["wrong_count"] is not None else 0,
                last_reviewed_str=r["last_reviewed"],
            )
            updates.append((
                card.stability,
                card.difficulty,
                card.reps,
                card.lapses,
                int(card.state),
                r["word_id"],
            ))

        conn.executemany(
            """
            UPDATE progress SET
                fsrs_stability = ?,
                fsrs_difficulty = ?,
                fsrs_reps = ?,
                fsrs_lapses = ?,
                fsrs_state = ?
            WHERE word_id = ?
            """,
            updates,
        )
        logger.info(f"FSRS v5 migratsiyasi: {len(updates)} ta so'z SM-2 dan FSRS modeliga muvaffaqiyatli o'tkazildi.")
        return len(updates)
    except Exception as e:
        logger.warning(f"FSRS migratsiyasida xatolik: {e}")
        return 0


def backfill_phonetics(conn: sqlite3.Connection | None = None) -> int:
    """Mavjud bazadagi so'zlarga bo'sh bo'lgan fonetik va POS qiymatlarini avtomatik to'ldirish."""
    if conn is not None:
        return _do_backfill_phonetics(conn)
    with get_conn() as c:
        return _do_backfill_phonetics(c)


def _do_backfill_phonetics(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT id, english FROM words WHERE phonetic IS NULL OR phonetic = ''"
    ).fetchall()
    if not rows:
        return 0
    updates = []
    for r in rows:
        info = phonetics.get_word_info(r["english"])
        updates.append((info["phonetic"], info["part_of_speech"], r["id"]))
    conn.executemany(
        "UPDATE words SET phonetic = ?, part_of_speech = ? WHERE id = ?",
        updates,
    )
    updated = len(updates)
    if updated > 0:
        logger.info(f"{updated} ta so'zga IPA transkripsiya va so'z turkumlari muvaffaqiyatli kiritildi.")
    return updated


def get_words_with_progress(order_by: str = "w.id ASC") -> list[sqlite3.Row]:
    """So'zlar va ularning progress ma'lumotlarini 1 ta tezkor JOIN so'rovi bilan qaytaradi (N+1 yo'q).

    order_by parametri whitelist orqali SQL injection'dan himoyalangan.
    """
    safe_order = _safe_order_by(order_by, default="w.id ASC")
    with get_conn() as conn:
        return conn.execute(
            f"""
            SELECT w.id, w.english, w.uzbek, w.status, w.example, w.created_at,
                   COALESCE(p.box_level, 0) as box_level,
                   COALESCE(p.correct_count, 0) as correct_count,
                   COALESCE(p.wrong_count, 0) as wrong_count
            FROM words w
            LEFT JOIN progress p ON p.word_id = w.id
            ORDER BY {safe_order}
            """
        ).fetchall()


def get_practice_batch(mode_status: str = None, limit: int = 15, word_ids: list[int] = None) -> list[sqlite3.Row]:
    """Mashq uchun so'zlar: agar word_ids berilsa, aynan o'sha so'zlar qaytariladi.
    Aks holda eng avval muddati o'tgan so'zlar (Leitner box) va kerak bo'lsa partiya to'ldiriladi.
    Agar bazadagi so'zlar soni limitdan kam bo'lsa, foydalanuvchi so'ragan limit to'liq bajarilishi uchun
    so'zlar takrorlanib to'liq limit miqdoriga yetkaziladi."""
    if word_ids:
        return get_words_by_ids(word_ids)
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        rows = list(
            conn.execute(
                """
                SELECT w.*, 
                       COALESCE(p.box_level, 0) as box_level, 
                       COALESCE(p.next_review, ?) as next_review, 
                       COALESCE(p.correct_count, 0) as correct_count, 
                       COALESCE(p.wrong_count, 0) as wrong_count
                FROM words w 
                LEFT JOIN progress p ON p.word_id = w.id
                WHERE p.next_review <= ? OR p.next_review IS NULL
                ORDER BY p.next_review ASC
                LIMIT ?
                """,
                (today, today, limit),
            ).fetchall()
        )
        if len(rows) < limit:
            exclude_ids = [r["id"] for r in rows]
            if exclude_ids:
                placeholders = ",".join("?" for _ in exclude_ids)
                extra = conn.execute(
                    f"""
                    SELECT w.*, 
                           COALESCE(p.box_level, 0) as box_level, 
                           COALESCE(p.next_review, ?) as next_review, 
                           COALESCE(p.correct_count, 0) as correct_count, 
                           COALESCE(p.wrong_count, 0) as wrong_count
                    FROM words w 
                    LEFT JOIN progress p ON p.word_id = w.id
                    WHERE w.id NOT IN ({placeholders})
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    (today, *exclude_ids, limit - len(rows)),
                ).fetchall()
            else:
                extra = conn.execute(
                    """
                    SELECT w.*, 
                           COALESCE(p.box_level, 0) as box_level, 
                           COALESCE(p.next_review, ?) as next_review, 
                           COALESCE(p.correct_count, 0) as correct_count, 
                           COALESCE(p.wrong_count, 0) as wrong_count
                    FROM words w 
                    LEFT JOIN progress p ON p.word_id = w.id
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    (today, limit),
                ).fetchall()
            rows.extend(extra)

        # Agar bazada so'zlar soni so'ralgan limitdan kam bo'lsa ham,
        # foydalanuvchi belgilagan kunlik reja mashqini to'liq bajarish uchun
        # so'zlarni (avvalo past box_level va ko'p xato bo'lganlarni) takrorlab partiyani to'ldiramiz:
        if rows and len(rows) < limit:
            pool = sorted(
                rows,
                key=lambda r: (
                    r["box_level"] if r["box_level"] is not None else 0,
                    -(r["wrong_count"] if r["wrong_count"] is not None else 0)
                )
            )
            idx = 0
            while len(rows) < limit:
                rows.append(pool[idx % len(pool)])
                idx += 1

        return rows


BOX_INTERVALS_DAYS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}

def _apply_progress_update(conn: sqlite3.Connection, word_id: int, box: int, is_correct: bool, next_review: str):
    """Progress va so'z holatini xavfsiz yangilash (DRY)."""
    status = "mastered" if box >= 4 else ("learning" if box >= 1 else "new")
    today = datetime.date.today().isoformat()
    conn.execute(
        """
        UPDATE progress SET
            correct_count = correct_count + ?,
            wrong_count = wrong_count + ?,
            box_level = ?,
            last_reviewed = ?,
            next_review = ?
        WHERE word_id = ?
        """,
        (
            1 if is_correct else 0,
            0 if is_correct else 1,
            box,
            today,
            next_review,
            word_id,
        ),
    )
    conn.execute("UPDATE words SET status=? WHERE id=?", (status, word_id))


def record_fsrs_review(word_id: int, rating: int, desired_retention: float = 0.90) -> dict:
    """
    FSRS v5 (Free Spaced Repetition Scheduler) algoritmi orqali so'zni takrorlash va baholash.
    rating:
      1: AGAIN  (Eslay olmadi / xato)
      2: HARD   (Qiyinchilik bilan esladi)
      3: GOOD   (Yaxshi, o'z vaqtida esladi)
      4: EASY   (Juda oson va tez esladi)
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.ease_factor, p.interval_days, p.repetitions, p.box_level, 
                   p.correct_count, p.wrong_count, p.last_reviewed,
                   p.fsrs_stability, p.fsrs_difficulty, p.fsrs_reps, p.fsrs_lapses, p.fsrs_state
            FROM progress p WHERE p.word_id = ?
            """,
            (word_id,),
        ).fetchone()
        if not row:
            return {}

        ef = row["ease_factor"] if row["ease_factor"] is not None else 2.5
        interval = row["interval_days"] if row["interval_days"] is not None else 0
        repetitions = row["repetitions"] if row["repetitions"] is not None else 0
        box = row["box_level"] if row["box_level"] is not None else 0
        c_cnt = row["correct_count"] or 0
        w_cnt = row["wrong_count"] or 0
        last_rev = row["last_reviewed"]

        # Rating tekshirish (1..4)
        r_val = int(rating)
        if r_val < 1:
            r_val = 1
        elif r_val > 4:
            r_val = 4

        card_s = row["fsrs_stability"]
        card_d = row["fsrs_difficulty"]
        card_reps = row["fsrs_reps"] or 0
        card_lapses = row["fsrs_lapses"] or 0
        card_st = row["fsrs_state"] or 0

        now = datetime.datetime.now()
        now_iso = now.isoformat()

        if FSRSv5 is not None:
            if (card_s is None or card_s == 0.0) and (repetitions > 0 or interval > 0 or (card_reps == 0 and repetitions > 0)):
                card = FSRSv5.from_sm2(
                    ease_factor=ef,
                    interval_days=interval,
                    repetitions=repetitions,
                    wrong_count=w_cnt,
                    last_reviewed_str=last_rev,
                )
            else:
                last_dt = None
                if last_rev:
                    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            last_dt = datetime.datetime.strptime(last_rev.strip(), fmt)
                            break
                        except Exception:
                            pass
                card = FSRSCard(
                    stability=float(card_s or 0.0),
                    difficulty=float(card_d if card_d is not None else 5.0),
                    reps=int(card_reps),
                    lapses=int(card_lapses),
                    state=CardState(card_st) if card_st in (0, 1, 2, 3) else CardState.NEW,
                    last_review=last_dt,
                )

            scheduler = FSRSv5(desired_retention=desired_retention)
            new_card, next_interval = scheduler.review_card(card, Rating(r_val), review_time=now)
        else:
            next_interval = max(1, interval * 2) if r_val >= 3 else 1
            new_card = FSRSCard(
                stability=float(next_interval),
                difficulty=5.0,
                reps=card_reps + (1 if r_val >= 3 else 0),
                lapses=card_lapses + (0 if r_val >= 3 else 1),
                state=CardState.REVIEW if r_val >= 3 else CardState.LEARNING,
            )

        # SM-2 ko'rsatkichlarini ham sinxron saqlash (To'liq teskari muvofiqlik)
        is_correct = (r_val >= 2)
        if r_val == 1:  # AGAIN
            new_reps = 0
            new_box = max(0, box - 1)
            w_cnt += 1
            new_ef = max(1.3, round(ef - 0.2, 2))
        else:
            new_reps = repetitions + 1
            new_box = min(5, box + 1)
            c_cnt += 1
            q_equiv = 3 if r_val == 2 else (4 if r_val == 3 else 5)
            ef_prime = ef + (0.1 - (5 - q_equiv) * (0.08 + (5 - q_equiv) * 0.02))
            new_ef = max(1.3, round(ef_prime, 2))

        next_date = (datetime.date.today() + datetime.timedelta(days=next_interval)).isoformat()
        is_mastered = (new_card.stability >= 21.0 or new_card.reps >= 5 or new_box >= 5)

        conn.execute(
            """
            UPDATE progress SET
                fsrs_stability = ?,
                fsrs_difficulty = ?,
                fsrs_reps = ?,
                fsrs_lapses = ?,
                fsrs_state = ?,
                ease_factor = ?,
                interval_days = ?,
                repetitions = ?,
                box_level = ?,
                correct_count = ?,
                wrong_count = ?,
                last_reviewed = ?,
                next_review = ?
            WHERE word_id = ?
            """,
            (
                round(new_card.stability, 4),
                round(new_card.difficulty, 2),
                new_card.reps,
                new_card.lapses,
                int(new_card.state),
                new_ef,
                next_interval,
                new_reps,
                new_box,
                c_cnt,
                w_cnt,
                now_iso,
                next_date,
                word_id,
            ),
        )

        status = "mastered" if is_mastered else ("learning" if (new_card.reps > 0 or new_box > 0) else "new")
        conn.execute("UPDATE words SET status=? WHERE id=?", (status, word_id))

    bump_daily_stat(practiced=1, correct=1 if is_correct else 0, wrong=0 if is_correct else 1)
    _invalidate_cache()
    return {
        "word_id": word_id,
        "rating": r_val,
        "fsrs_stability": round(new_card.stability, 2),
        "fsrs_difficulty": round(new_card.difficulty, 2),
        "fsrs_reps": new_card.reps,
        "fsrs_lapses": new_card.lapses,
        "fsrs_state": int(new_card.state),
        "ease_factor": new_ef,
        "interval_days": next_interval,
        "repetitions": new_reps,
        "box_level": new_box,
        "next_review": next_date,
        "status": status,
    }


def record_sm2_review(word_id: int, quality: int) -> dict:
    """
    Anki SM-2 Spaced Repetition algoritmi (FSRS v5 ga silliq yo'naltirilgan):
    quality:
      5: Easy (Juda oson) -> FSRS Easy (4)
      4: Good (Yaxshi)    -> FSRS Good (3)
      3: Hard (Qiyin)     -> FSRS Hard (2)
      0..2: Again (Xato)  -> FSRS Again (1)
    """
    if quality >= 5:
        r = 4
    elif quality == 4:
        r = 3
    elif quality == 3:
        r = 2
    else:
        r = 1
    return record_fsrs_review(word_id, rating=r)


def record_answer(word_id: int, correct: bool):
    """FSRS v5 ga muvofiqlashtirilgan javob yozish."""
    return record_fsrs_review(word_id, rating=3 if correct else 1)


def record_flashcard_answer(word_id: int, quality: str):
    """
    Flashcard javobini FSRS v5 reytingi bo'yicha yozish:
    - 'again' / 'wrong': xato (Rating.AGAIN = 1)
    - 'hard': qiyin (Rating.HARD = 2)
    - 'good': yaxshi (Rating.GOOD = 3)
    - 'easy': oson (Rating.EASY = 4)
    """
    q_map = {"again": 1, "wrong": 1, "hard": 2, "good": 3, "easy": 4}
    r_val = q_map.get(str(quality).lower(), 3)
    return record_fsrs_review(word_id, rating=r_val)


def get_fsrs_card(word_id: int):
    """Berilgan word_id bo'yicha FSRSCard xotira modelini qaytarish."""
    if FSRSCard is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state,
                   last_reviewed, next_review, ease_factor, interval_days, repetitions, wrong_count
            FROM progress WHERE word_id = ?
            """,
            (word_id,),
        ).fetchone()
        if not row:
            return None

        card_s = row["fsrs_stability"]
        if (card_s is None or card_s == 0.0) and (row["repetitions"] or 0) > 0:
            return FSRSv5.from_sm2(
                ease_factor=row["ease_factor"] or 2.5,
                interval_days=row["interval_days"] or 0,
                repetitions=row["repetitions"] or 0,
                wrong_count=row["wrong_count"] or 0,
                last_reviewed_str=row["last_reviewed"],
            )

        last_dt = None
        if row["last_reviewed"]:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    last_dt = datetime.datetime.strptime(row["last_reviewed"].strip(), fmt)
                    break
                except Exception:
                    pass

        due_dt = None
        if row["next_review"]:
            try:
                due_dt = datetime.datetime.strptime(row["next_review"].strip(), "%Y-%m-%d")
            except Exception:
                pass

        return FSRSCard(
            stability=float(card_s or 0.0),
            difficulty=float(row["fsrs_difficulty"] if row["fsrs_difficulty"] is not None else 5.0),
            reps=int(row["fsrs_reps"] or 0),
            lapses=int(row["fsrs_lapses"] or 0),
            state=CardState(row["fsrs_state"]) if row["fsrs_state"] in (0, 1, 2, 3) else CardState.NEW,
            last_review=last_dt,
            due=due_dt,
        )


def get_fsrs_stats() -> dict:
    """FSRS v5 bo'yicha global xotira tahlili va samaradorlik statistikasi."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state, last_reviewed
            FROM progress
            WHERE fsrs_reps > 0 OR fsrs_stability > 0
            """
        ).fetchall()

        if not rows:
            return {
                "total_learned": 0,
                "avg_stability_days": 0.0,
                "avg_difficulty": 5.0,
                "avg_retention_pct": 100.0,
                "relearning_count": 0,
                "review_count": 0,
            }

        stabs = [r["fsrs_stability"] or 0.0 for r in rows if r["fsrs_stability"] and r["fsrs_stability"] > 0]
        diffs = [r["fsrs_difficulty"] or 5.0 for r in rows if r["fsrs_difficulty"]]
        relearn = sum(1 for r in rows if r["fsrs_state"] == 3)
        review = sum(1 for r in rows if r["fsrs_state"] == 2)

        scheduler = FSRSv5() if FSRSv5 else None
        now = datetime.datetime.now()
        retentions = []

        if scheduler:
            for r in rows:
                if r["fsrs_stability"] and r["fsrs_stability"] > 0 and r["last_reviewed"]:
                    last_dt = None
                    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            last_dt = datetime.datetime.strptime(r["last_reviewed"].strip(), fmt)
                            break
                        except Exception:
                            pass
                    if last_dt:
                        card = FSRSCard(stability=r["fsrs_stability"], last_review=last_dt, state=CardState.REVIEW)
                        ret = scheduler.get_retrievability(card, now)
                        retentions.append(ret)

        avg_s = sum(stabs) / len(stabs) if stabs else 0.0
        avg_d = sum(diffs) / len(diffs) if diffs else 5.0
        avg_r = (sum(retentions) / len(retentions) * 100.0) if retentions else 92.0

        return {
            "total_learned": len(rows),
            "avg_stability_days": round(avg_s, 1),
            "avg_difficulty": round(avg_d, 1),
            "avg_retention_pct": round(avg_r, 1),
            "relearning_count": relearn,
            "review_count": review,
        }


def get_due_words(limit: int = 50) -> list[sqlite3.Row]:
    """Anki SM-2 bo'yicha bugun takrorlash muddati kelgan so'zlar ro'yxati."""
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count, p.ease_factor, p.interval_days
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.next_review <= ? OR p.next_review IS NULL
            ORDER BY p.next_review ASC, p.box_level ASC
            LIMIT ?
            """,
            (today, limit),
        ).fetchall()


def get_due_count() -> int:
    """Bugun takrorlash muddati kelgan so'zlar soni."""
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM progress WHERE next_review <= ? OR next_review IS NULL",
            (today,),
        ).fetchone()
        return row["cnt"] if row else 0


def get_accuracy_stats() -> dict:
    """Umumiy aniqlik statistikasi (to'g'ri / xato nisbati foizda)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT SUM(correct_count) as total_c, SUM(wrong_count) as total_w FROM progress"
        ).fetchone()
        c = row["total_c"] or 0
        w = row["total_w"] or 0
        total = c + w
        pct = round((c / total * 100), 1) if total > 0 else 0
        return {"correct": c, "wrong": w, "total": total, "percent": pct}


def get_box_distribution() -> dict:
    """Leitner Box 0 dan Box 5 gacha so'zlar soni taqsimoti."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT box_level, COUNT(*) as cnt FROM progress GROUP BY box_level"
        ).fetchall()
        dist = {i: 0 for i in range(6)}
        for r in rows:
            b = r["box_level"]
            if b in dist:
                dist[b] = r["cnt"]
        return dist


def get_weak_words(limit: int = 50) -> list[sqlite3.Row]:
    """
    Foydalanuvchi ko'p xato qilgan so'zlar (kamida 2 marta xato va to'g'ri/xato nisbati < 60%).
    Xatosi ko'p bo'lganlar birinchi bo'lib chiqadi.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.wrong_count >= 2 
              AND (p.correct_count = 0 OR (CAST(p.correct_count AS FLOAT) / (p.correct_count + p.wrong_count)) < 0.6)
            ORDER BY (p.wrong_count - p.correct_count) DESC, p.wrong_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_weak_words_count() -> int:
    """Karantindagi zaif so'zlar soni."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.wrong_count >= 2 
              AND (p.correct_count = 0 OR (CAST(p.correct_count AS FLOAT) / (p.correct_count + p.wrong_count)) < 0.6)
            """
        ).fetchone()
        return row["cnt"] if row else 0


def get_weakest_words(limit: int = 10) -> list[dict]:
    """Eng ko'p xato qilingan va unutilish ehtimoli yuqori zaif so'zlarni qaytaradi."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.english, w.uzbek, w.phonetic, w.part_of_speech, w.example,
                   COALESCE(p.wrong_count, 0) as wrong_count,
                   COALESCE(p.correct_count, 0) as correct_count,
                   COALESCE(p.ease_factor, 2.5) as ease_factor
            FROM words w
            LEFT JOIN progress p ON w.id = p.word_id
            WHERE COALESCE(p.wrong_count, 0) > 0 OR w.status = 'learning'
            ORDER BY wrong_count DESC, ease_factor ASC, w.id ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def record_blitz_score(score: int, correct: int, wrong: int) -> dict:
    """Blitz marafoni natijasini qayd etadi, agar yangi rekord bo'lsa yangilaydi."""
    prev_best = int(get_setting("blitz_best_score", "0") or "0")
    is_new_best = score > prev_best
    if is_new_best:
        set_setting("blitz_best_score", str(score))

    # Daily stats yangilash
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO daily_stats (date, practiced, correct, wrong)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                practiced = practiced + ?,
                correct = correct + ?,
                wrong = wrong + ?
            """,
            (today, correct + wrong, correct, wrong, correct + wrong, correct, wrong),
        )

    return {
        "score": score,
        "is_new_best": is_new_best,
        "best_score": max(score, prev_best),
        "correct": correct,
        "wrong": wrong,
    }

