"""
Vocab Master Pro — Topic Based Words Service.
36 ta tematik to'plam (901 ta so'z) bilan ishlash, db.sqlite3 va vocab.db
o'rtasidagi integratsiya, progressni hisoblash va to'plamni o'rganishga qo'shish xizmati.
"""
import sqlite3
from typing import Any
import database as db
import global_dict_service
import phonetics
from logger import get_logger

logger = get_logger("topic_service")

# 36 ta tematik mavzular bazasi
TOPICS_DATA = [
    {
        "id": "names",
        "title": "Names",
        "title_uz": "Ismlar va unvonlar",
        "description": "Words about names, titles, and how people are identified.",
        "emoji": "👤",
        "color": "#6366f1",
        "words": ["name", "title", "surname", "nickname", "alias", "pseudonym", "moniker", "initials", "signature", "label", "identity", "designation", "forename", "maiden", "prefix", "suffix", "honorific", "address", "call"]
    },
    {
        "id": "age",
        "title": "Age",
        "title_uz": "Yosh va hayot bosqichlari",
        "description": "Vocabulary describing stages of life and age groups.",
        "emoji": "⏰",
        "color": "#f59e0b",
        "words": ["young", "old", "infant", "toddler", "teenager", "adult", "elderly", "senior", "juvenile", "adolescent", "newborn", "youth", "mature", "ancient", "aged", "middle-aged", "grow", "age", "birth", "generation"]
    },
    {
        "id": "family",
        "title": "Family Relationships",
        "title_uz": "Oila va qarindoshlik",
        "description": "Words for family members and relationships between relatives.",
        "emoji": "👨‍👩‍👧‍👦",
        "color": "#ec4899",
        "words": ["mother", "father", "sister", "brother", "son", "daughter", "grandmother", "grandfather", "aunt", "uncle", "cousin", "nephew", "niece", "husband", "wife", "spouse", "parent", "sibling", "relative", "stepmother", "stepfather", "stepson", "stepdaughter", "twin", "ancestor", "descendant", "offspring", "guardian", "foster", "widow", "widower", "orphan", "kinship", "household"]
    },
    {
        "id": "marital",
        "title": "Marital Status",
        "title_uz": "Oilaviy holat va nikoh",
        "description": "Vocabulary about marriage, relationships, and civil status.",
        "emoji": "💍",
        "color": "#f43f5e",
        "words": ["married", "single", "divorced", "widowed", "engaged", "separated", "bachelor", "matrimony", "wedding", "bride", "groom", "proposal", "ceremony", "vow", "honeymoon", "anniversary", "remarry", "dating", "cohabit", "partner", "fiancé", "fiancée", "divorce"]
    },
    {
        "id": "location",
        "title": "Location",
        "title_uz": "Joylashuv va yo'nalishlar",
        "description": "Words for describing places, directions, and geographical positions.",
        "emoji": "📍",
        "color": "#10b981",
        "words": ["north", "south", "east", "west", "central", "nearby", "distant", "local", "abroad", "rural", "urban", "suburban", "coastal", "inland", "tropical", "arctic", "region", "territory", "zone", "district", "address", "location", "position", "place", "area", "direction"]
    },
    {
        "id": "build",
        "title": "Build & Physique",
        "title_uz": "Qaddi-qomat va jismoniy tuzilish",
        "description": "Words describing the physical build and appearance of a person.",
        "emoji": "💪",
        "color": "#3b82f6",
        "words": ["tall", "short", "slim", "fat", "muscular", "athletic", "stocky", "slender", "overweight", "underweight", "petite", "lanky", "broad", "lean", "plump", "stout", "thin", "heavy", "light", "strong", "weak", "fit", "healthy", "robust", "fragile", "physique"]
    },
    {
        "id": "senses",
        "title": "The Senses",
        "title_uz": "Sezgi a'zolari va his tuyg'ular",
        "description": "Words related to sight, hearing, smell, taste, and touch.",
        "emoji": "👁️",
        "color": "#8b5cf6",
        "words": ["sight", "hearing", "smell", "taste", "touch", "vision", "perception", "sensation", "stimulate", "observe", "detect", "feel", "listen", "watch", "sniff", "aroma", "texture", "sound", "color", "bright", "dark", "loud", "quiet", "soft", "rough", "sweet", "bitter", "sour"]
    },
    {
        "id": "character",
        "title": "Character & Personality",
        "title_uz": "Xarakter va shaxsiyat",
        "description": "Words describing the nature and character traits of people.",
        "emoji": "✨",
        "color": "#f97316",
        "words": ["kind", "cruel", "brave", "coward", "honest", "dishonest", "generous", "selfish", "patient", "impatient", "confident", "shy", "arrogant", "humble", "cheerful", "grumpy", "optimistic", "pessimistic", "stubborn", "flexible", "loyal", "jealous", "ambitious", "lazy", "diligent", "reliable", "creative", "curious", "sincere", "charming"]
    },
    {
        "id": "attitudes",
        "title": "Attitudes & Beliefs",
        "title_uz": "Qarashlar va e'tiqod",
        "description": "Words for describing personal beliefs, faith, and worldviews.",
        "emoji": "🧠",
        "color": "#06b6d4",
        "words": ["belief", "faith", "trust", "doubt", "skepticism", "conviction", "religion", "atheism", "ideology", "philosophy", "opinion", "perspective", "prejudice", "stereotype", "attitude", "value", "principle", "morality", "tradition", "culture", "respect", "tolerance", "bias", "assumption"]
    },
    {
        "id": "thinking",
        "title": "Thinking, Wanting, Knowing",
        "title_uz": "Fikrlash, xohish va bilim",
        "description": "Verbs and nouns about mental processes and knowledge.",
        "emoji": "💭",
        "color": "#84cc16",
        "words": ["think", "know", "understand", "imagine", "remember", "forget", "learn", "study", "decide", "choose", "wish", "want", "desire", "consider", "realize", "assume", "believe", "doubt", "guess", "wonder", "reflect", "reason", "analyze", "conclude"]
    },
    {
        "id": "moods",
        "title": "Moods",
        "title_uz": "Kayfiyat va hissiyotlar",
        "description": "Words for expressing emotions and temporary states of mind.",
        "emoji": "😊",
        "color": "#eab308",
        "words": ["happy", "sad", "angry", "anxious", "excited", "bored", "depressed", "content", "frustrated", "jealous", "embarrassed", "proud", "surprised", "worried", "calm", "nervous", "joy", "grief", "fear", "panic", "relief", "disgust", "hope", "despair", "mood", "emotion"]
    },
    {
        "id": "expressing",
        "title": "Expressing Oneself",
        "title_uz": "Fikr bildirish va muloqot",
        "description": "Words for communication, speech, and self-expression.",
        "emoji": "💬",
        "color": "#14b8a6",
        "words": ["speak", "shout", "whisper", "laugh", "cry", "smile", "express", "communicate", "articulate", "declare", "announce", "confess", "argue", "debate", "explain", "describe", "narrate", "quote", "protest", "agree", "disagree", "insist", "refuse", "suggest"]
    },
    {
        "id": "gesture",
        "title": "Gesture & Body Language",
        "title_uz": "Tana tili va imo-ishoralar",
        "description": "Words for non-verbal communication through movement.",
        "emoji": "🤝",
        "color": "#a78bfa",
        "words": ["wave", "nod", "shake", "point", "bow", "clap", "shrug", "wink", "frown", "gesture", "posture", "handshake", "hug", "embrace", "pat", "stretch", "cross", "fold", "lean", "stare", "glance"]
    },
    {
        "id": "sounds",
        "title": "Sounds People Make",
        "title_uz": "Inson tovushlari",
        "description": "Words for the sounds humans make in different situations.",
        "emoji": "🔊",
        "color": "#fb923c",
        "words": ["laugh", "cry", "scream", "whisper", "shout", "moan", "sigh", "cough", "sneeze", "yawn", "gasp", "grunt", "mumble", "groan", "snore", "hiss", "clap", "snap", "click", "stamp"]
    },
    {
        "id": "plants",
        "title": "The Plant World",
        "title_uz": "O'simliklar olami",
        "description": "Vocabulary about plants, trees, flowers, and botany.",
        "emoji": "🌿",
        "color": "#22c55e",
        "words": ["flower", "tree", "root", "leaf", "stem", "petal", "seed", "pollen", "fruit", "grass", "shrub", "bush", "vine", "forest", "bloom", "wilt", "photosynthesis", "chlorophyll", "oak", "pine", "rose", "tulip", "herb", "moss", "fern", "branch", "bark", "trunk", "jungle"]
    },
    {
        "id": "animals",
        "title": "The Animal World",
        "title_uz": "Hayvonot olami",
        "description": "Words about animals, their behaviors, and habitats.",
        "emoji": "🦁",
        "color": "#f59e0b",
        "words": ["mammal", "reptile", "bird", "fish", "insect", "amphibian", "predator", "prey", "habitat", "migration", "carnivore", "herbivore", "omnivore", "endangered", "extinct", "domestic", "wild", "cat", "dog", "horse", "elephant", "lion", "eagle", "whale", "snake", "frog", "butterfly"]
    },
    {
        "id": "food",
        "title": "Food & Drink",
        "title_uz": "Oziq-ovqat va ichimliklar",
        "description": "Words about food, beverages, meals, and cooking.",
        "emoji": "🍽️",
        "color": "#ef4444",
        "words": ["bread", "meat", "vegetable", "fruit", "soup", "rice", "pasta", "cheese", "milk", "water", "juice", "coffee", "tea", "meal", "breakfast", "lunch", "dinner", "dessert", "sweet", "salty", "bitter", "spicy", "fresh", "raw", "cooked", "delicious", "recipe"]
    },
    {
        "id": "buildings",
        "title": "Buildings & Rooms",
        "title_uz": "Binolar va xonalar",
        "description": "Words for types of buildings and rooms inside them.",
        "emoji": "🏠",
        "color": "#78716c",
        "words": ["house", "apartment", "kitchen", "bedroom", "bathroom", "office", "school", "hospital", "restaurant", "hotel", "church", "mosque", "library", "museum", "floor", "ceiling", "wall", "door", "window", "roof", "basement", "stairs", "corridor", "balcony", "garage"]
    },
    {
        "id": "vehicles",
        "title": "Vehicles",
        "title_uz": "Transport vositalari",
        "description": "Words for transportation vehicles on land, sea, and air.",
        "emoji": "🚗",
        "color": "#64748b",
        "words": ["car", "bus", "train", "airplane", "bicycle", "motorcycle", "truck", "ship", "boat", "helicopter", "taxi", "ambulance", "ferry", "subway", "tram", "van", "jeep", "scooter", "lorry", "vehicle", "engine"]
    },
    {
        "id": "clothes",
        "title": "Clothes",
        "title_uz": "Kiyim-kechak va poyabzal",
        "description": "Words for clothing items, fashion, and accessories.",
        "emoji": "👗",
        "color": "#d946ef",
        "words": ["shirt", "pants", "dress", "jacket", "coat", "shoes", "socks", "hat", "scarf", "gloves", "underwear", "suit", "tie", "skirt", "blouse", "sweater", "uniform", "boots", "sandals", "fashion", "wear", "outfit", "sleeve", "collar", "button", "zipper"]
    },
    {
        "id": "shapes",
        "title": "Shapes",
        "title_uz": "Shakllar va geometriya",
        "description": "Geometric shapes and words related to form and structure.",
        "emoji": "🔷",
        "color": "#0ea5e9",
        "words": ["circle", "square", "triangle", "rectangle", "oval", "diamond", "star", "heart", "cube", "sphere", "cylinder", "cone", "polygon", "angle", "edge", "vertex", "line", "curve", "parallel", "shape", "round", "flat", "sharp", "straight", "curved"]
    },
    {
        "id": "colors",
        "title": "Colors",
        "title_uz": "Ranglar va tuslar",
        "description": "Words for colors, shades, and how we describe them.",
        "emoji": "🎨",
        "color": "#f43f5e",
        "words": ["red", "blue", "green", "yellow", "orange", "purple", "pink", "black", "white", "brown", "gray", "gold", "silver", "light", "dark", "pale", "bright", "vivid", "shade", "tone", "hue", "tint", "color", "transparent", "opaque"]
    },
    {
        "id": "health",
        "title": "Health & Medicine",
        "title_uz": "Salomatlik va tibbiyot",
        "description": "Medical vocabulary, body parts, illness, and wellbeing.",
        "emoji": "❤️",
        "color": "#ef4444",
        "words": ["doctor", "hospital", "medicine", "disease", "pain", "fever", "cough", "cold", "headache", "surgery", "treatment", "cure", "symptom", "diagnosis", "healthy", "sick", "recover", "vaccine", "prescription", "pharmacy", "blood", "heart", "lung", "bone", "muscle", "nerve"]
    },
    {
        "id": "work",
        "title": "Work & Careers",
        "title_uz": "Ish, kasb va martaba",
        "description": "Professional vocabulary about careers, jobs, and the workplace.",
        "emoji": "💼",
        "color": "#475569",
        "words": ["job", "career", "profession", "employee", "employer", "salary", "office", "meeting", "deadline", "project", "colleague", "manager", "interview", "promotion", "resign", "hire", "skill", "experience", "task", "report", "teamwork", "leadership", "workshop", "training"]
    },
    {
        "id": "money",
        "title": "Money & Finance",
        "title_uz": "Pul, moliya va bank",
        "description": "Financial vocabulary about money, banking, and economics.",
        "emoji": "💰",
        "color": "#ca8a04",
        "words": ["bank", "cash", "credit", "debit", "loan", "salary", "wage", "tax", "budget", "invest", "save", "spend", "profit", "loss", "price", "cost", "expensive", "cheap", "afford", "debt", "currency", "exchange", "economy", "finance", "income", "payment"]
    },
    {
        "id": "sport",
        "title": "Sport & Fitness",
        "title_uz": "Sport va jismoniy tarbiya",
        "description": "Sports vocabulary including activities, competitions, and players.",
        "emoji": "⚽",
        "color": "#16a34a",
        "words": ["football", "basketball", "tennis", "swimming", "running", "cycling", "team", "player", "match", "score", "win", "lose", "competition", "training", "athlete", "coach", "stadium", "referee", "championship", "goal", "point", "game", "sport", "exercise"]
    },
    {
        "id": "games",
        "title": "Games & Play",
        "title_uz": "O'yinlar va bellashuvlar",
        "description": "Words about games, play, and competition.",
        "emoji": "🎮",
        "color": "#7c3aed",
        "words": ["chess", "card", "dice", "puzzle", "board", "play", "win", "lose", "strategy", "rule", "player", "score", "tournament", "competition", "move", "turn", "challenge", "level", "reward", "team"]
    },
    {
        "id": "music",
        "title": "Music & Sound",
        "title_uz": "Musiqa va san'at",
        "description": "Musical vocabulary covering instruments, styles, and performance.",
        "emoji": "🎵",
        "color": "#db2777",
        "words": ["song", "melody", "rhythm", "beat", "harmony", "instrument", "guitar", "piano", "drums", "violin", "singer", "musician", "concert", "album", "lyrics", "compose", "record", "band", "orchestra", "jazz", "classical", "pop", "rock", "tune", "sound"]
    },
    {
        "id": "cooking",
        "title": "Cooking & Kitchen",
        "title_uz": "Pazandalik va oshxona",
        "description": "Words about cooking methods, kitchen tools, and ingredients.",
        "emoji": "🍳",
        "color": "#b45309",
        "words": ["recipe", "ingredient", "cook", "bake", "fry", "boil", "grill", "roast", "chop", "mix", "season", "taste", "measure", "oven", "pan", "pot", "knife", "spice", "flour", "sugar", "oil", "butter", "stir", "blend", "serve"]
    },
    {
        "id": "travel",
        "title": "Travelling",
        "title_uz": "Sayohat va turizm",
        "description": "Vocabulary for tourism, journeys, and exploring the world.",
        "emoji": "✈️",
        "color": "#0284c7",
        "words": ["travel", "journey", "trip", "vacation", "passport", "visa", "airport", "hotel", "reservation", "tourist", "destination", "suitcase", "flight", "boarding", "immigration", "customs", "backpack", "guide", "map", "tour", "adventure", "explore", "ticket", "itinerary"]
    },
    {
        "id": "business",
        "title": "Business",
        "title_uz": "Biznes va boshqaruv",
        "description": "Corporate and entrepreneurial vocabulary for business contexts.",
        "emoji": "📊",
        "color": "#1d4ed8",
        "words": ["company", "market", "product", "service", "client", "customer", "brand", "strategy", "budget", "revenue", "profit", "loss", "investment", "startup", "entrepreneur", "meeting", "presentation", "contract", "negotiate", "sale", "demand", "supply", "trade"]
    },
    {
        "id": "law",
        "title": "Law & Justice",
        "title_uz": "Qonun va huquqshunoslik",
        "description": "Legal vocabulary about justice, rights, courts, and regulations.",
        "emoji": "⚖️",
        "color": "#374151",
        "words": ["legal", "illegal", "court", "judge", "lawyer", "police", "crime", "criminal", "punishment", "prison", "trial", "evidence", "witness", "verdict", "sentence", "constitution", "rights", "freedom", "justice", "regulation", "law", "attorney", "accusation", "defendant"]
    },
    {
        "id": "quality",
        "title": "Quality",
        "title_uz": "Sifat va baholash",
        "description": "Words for describing quality, standards, and evaluation.",
        "emoji": "⭐",
        "color": "#d97706",
        "words": ["good", "bad", "excellent", "poor", "high", "low", "best", "worst", "improve", "decline", "standard", "measure", "evaluate", "compare", "superior", "inferior", "average", "exceptional", "quality", "value", "perfect", "flawed", "accurate", "precise", "reliable"]
    },
    {
        "id": "time",
        "title": "Time",
        "title_uz": "Vaqt va davrlar",
        "description": "Vocabulary about time, duration, frequency, and scheduling.",
        "emoji": "⏱️",
        "color": "#0f766e",
        "words": ["morning", "afternoon", "evening", "night", "today", "yesterday", "tomorrow", "week", "month", "year", "hour", "minute", "second", "past", "present", "future", "early", "late", "always", "never", "sometimes", "often", "schedule", "deadline", "duration"]
    },
    {
        "id": "science",
        "title": "Science",
        "title_uz": "Ilm-fan va tadqiqot",
        "description": "Precise vocabulary from the world of scientific inquiry.",
        "emoji": "🔬",
        "color": "#0891b2",
        "words": ["hypothesis", "empirical", "axiom", "synthesis", "paradigm", "theorem", "catalyst", "entropy", "trajectory", "quantum", "variable", "inference", "magnitude", "velocity", "molecule", "chromosome", "ecosystem", "atom", "nucleus", "radiation", "mutation", "organism", "phenomenon", "experiment", "analysis", "correlation", "evolution", "gravity"]
    },
    {
        "id": "philosophy",
        "title": "Philosophy",
        "title_uz": "Falsafa va tafakkur",
        "description": "Foundational concepts from the history of philosophical thought.",
        "emoji": "📖",
        "color": "#7c3aed",
        "words": ["dialectic", "epistemology", "ontology", "metaphysics", "empiricism", "rationalism", "virtue", "ethics", "aesthetics", "phenomenology", "hermeneutics", "pragmatism", "solipsism", "syllogism", "logos", "consciousness", "perception", "cognition", "existence", "essence", "causality", "determinism", "morality", "justice", "liberty", "truth", "knowledge", "belief", "reason", "logic"]
    }
]

# Maxsus plural va sinonim qidiruv mappingi (db.sqlite3 bilan 100% moslik uchun)
WORD_LOOKUP_FALLBACKS = {
    "initials": "initial",
    "shoes": "shoe",
    "socks": "sock",
    "gloves": "glove",
    "boots": "boot",
    "sandals": "sandal",
    "drums": "drum",
    "startup": "start-up",
    "rights": "right",
}


def get_all_topics() -> list[dict]:
    """Barcha 36 ta mavzular ro'yxatini qaytaradi."""
    return TOPICS_DATA


def get_topic_by_id(topic_id: str) -> dict | None:
    """ID bo'yicha mavzuni qaytaradi."""
    for t in TOPICS_DATA:
        if t["id"] == topic_id:
            return t
    return None


def get_topic_progress(topic_id: str) -> tuple[int, int]:
    """
    Mavzudagi o'zlashtirish progressini hisoblaydi.
    Qaytaradi: (shaxsiy bazada mavjud so'zlar soni, jami so'zlar soni)
    """
    topic = get_topic_by_id(topic_id)
    if not topic:
        return 0, 0

    total = len(topic["words"])
    in_study_count = 0

    for w in topic["words"]:
        if db.get_word_by_english(w):
            in_study_count += 1

    return in_study_count, total


def get_topic_words_details(topic_id: str) -> list[dict]:
    """
    Mavzudagi barcha so'zlarni db.sqlite3 va vocab.db ma'lumotlari bilan boyitib qaytaradi.
    Har bir element:
    {
        'english': str,
        'uzbek': str,
        'phonetic': str,
        'pos': str,
        'example': str,
        'is_in_study_list': bool,
        'box_level': int,
        'word_id': int (agar mavjud bo'lsa)
    }
    """
    topic = get_topic_by_id(topic_id)
    if not topic:
        return []

    results = []

    for w in topic["words"]:
        # 1. Shaxsiy bazadagi holati
        local_row = db.get_word_by_english(w)
        local_dict = dict(local_row) if local_row else None
        is_in_study = local_dict is not None
        box_lvl = local_dict.get("box_level", 0) if local_dict else 0

        # 2. Global lug'atdan ma'lumotlar
        lookup_term = WORD_LOOKUP_FALLBACKS.get(w.lower(), w)
        details = global_dict_service.get_word_full_details(english=lookup_term)

        # Fonetika
        ph_info = phonetics.get_word_info(w)
        phonetic_val = ph_info.get("phonetic", "")
        pos_val = (details.get("pos", "") if details else "") or ph_info.get("part_of_speech", "")

        # O'zbekcha tarjima
        if local_dict and local_dict.get("uzbek"):
            uzbek_val = local_dict["uzbek"]
        elif details and details.get("uzbek_str"):
            uzbek_val = details["uzbek_str"]
        else:
            uzbek_val = "Tarjimasi belgilanmagan"

        # Misol gap
        if local_dict and local_dict.get("example"):
            example_val = local_dict["example"]
        elif details and details.get("examples"):
            example_val = details["examples"][0]
        else:
            example_val = ""

        results.append({
            "english": w,
            "uzbek": uzbek_val,
            "phonetic": phonetic_val,
            "pos": pos_val,
            "example": example_val,
            "is_in_study_list": is_in_study,
            "box_level": box_lvl,
            "local_id": local_dict["id"] if local_dict else None,
        })

    return results


def batch_add_topic_to_study(topic_id: str) -> tuple[int, int]:
    """
    Mavzudagi barcha hali shaxsiy bazada yo'q so'zlarni 1-bosishda vocab.db ga qo'shadi.
    Qaytaradi: (qo'shilgan so'zlar soni, jami so'zlar soni)
    """
    words_data = get_topic_words_details(topic_id)
    added_count = 0

    for item in words_data:
        if not item["is_in_study_list"]:
            success, _, _ = global_dict_service.add_to_study_list(
                english=item["english"],
                uzbek=item["uzbek"],
                example=item["example"]
            )
            if success:
                added_count += 1

    logger.info(f"Mavzudan so'zlar paketli qo'shildi: topic_id='{topic_id}', qo'shildi={added_count}/{len(words_data)}")
    return added_count, len(words_data)
