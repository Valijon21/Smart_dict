"""
Vocab Master — ma'lumotlar bazasi qatlami Facade (v2).
Hamma ma'lumotlar qatlami core/db/* papkasiga ajratilgan.
Bu fayl faqat eski importlar buzilmasligi uchun ko'prik (Facade) vazifasini bajaradi.
Kelajakda UI va Service'lar bevosita core.db.* yoki maxsus Servicelarga ulanishi kerak.
"""

from core.db.connection import (
    _safe_order_by, _ALLOWED_ORDER_BY, _determine_db_path, get_db_path, get_db_dir, 
    _ensure_dir, get_conn, init_db, DB_PATH
)
from core.db.word_repo import (
    normalize, add_word, bulk_add_words, bulk_import_pack, 
    get_imported_pack_counts, get_words_by_ids, get_last_import_word_ids, 
    get_last_imported_words, get_latest_added_words, get_total_word_count, 
    get_all_words, get_words, get_word_by_english, get_words_by_english_batch, 
    search_words, get_words_by_status, update_word, delete_word, word_count, 
    get_random_distractors, get_random_smart_word
)
from core.db.progress_repo import (
    _apply_progress_update, record_fsrs_review, record_sm2_review, 
    record_answer, record_flashcard_answer, get_fsrs_card, get_fsrs_stats, 
    get_due_words, get_due_count, get_weak_words, get_weak_words_count, 
    get_weakest_words, get_words_with_progress, get_practice_batch, 
    get_accuracy_stats, get_box_distribution, migrate_sm2_to_fsrs_if_needed, 
    backfill_phonetics, _do_backfill_phonetics, record_blitz_score
)
from core.db.stats_repo import (
    get_today_progress, bump_daily_stat, get_last_n_days, 
    get_current_streak, get_daily_activity_heatmap
)
from core.db.settings_repo import (
    get_setting, set_setting, get_daily_goal, set_daily_goal
)
from core.db.achievements_repo import (
    get_xp, add_xp, init_default_achievements, get_all_achievements, 
    unlock_achievement, update_achievement_progress, get_achievement
)
from core.db.backup_repo import (
    get_backup_dir, backup_database, restore_database, 
    auto_backup_daily, list_local_backups, export_to_csv, export_to_json
)
from core.db.irregular_verbs_repo import (
    seed_irregular_verbs_from_json, get_irregular_verbs, 
    get_all_irregular_verbs_for_practice, get_irregular_verb_by_id, 
    add_irregular_verb, update_irregular_verb, delete_irregular_verb, 
    toggle_irregular_verb_favorite, toggle_irregular_verb_learned, 
    record_irregular_verb_practice, get_irregular_verbs_stats
)
from core.db.cache import _invalidate_cache
