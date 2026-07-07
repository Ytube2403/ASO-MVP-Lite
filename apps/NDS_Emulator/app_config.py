# -*- coding: utf-8 -*-
"""
ASO Keyword Planner - App Configuration File
Version: 4.5
Purpose: Configuration file for deploying ASO Keyword Planner on SuperNDS Emulator (NDS & All-in-one).
"""

APP_CONFIG = {
    # =========================================================================
    # 1. IDENTITY & META (Thông tin định danh)
    # =========================================================================
    "app_id": "com.emulator.nds.super.game.console.handheld",      # Package ID / Bundle ID của ứng dụng
    "app_name": "SuperNDS: Retro Games Emulator",                 # Tên ứng dụng đầy đủ hiển thị trên Store
    "category": "Game Emulator",                                  # Danh mục ứng dụng
    "category_slug": "game_emulator",                             # Slug dùng cho đường dẫn (viết thường, không dấu)
    "market": "US_EN",                                            # Mã thị trường mặc định (thay đổi linh hoạt)
    "platform_mode": "google_play",                               # Nền tảng: 'google_play' hoặc 'app_store'
    "semantic_mode": "game_emulator",
    "ruleset_version": "2026-07-strict-v1",

    # =========================================================================
    # 2. MARKET LANGUAGE POLICY (Chính sách ngôn ngữ)
    # =========================================================================
    "market_language_policy": {
        "enabled": True,
        "required": True,
        "primary_languages": ["en"],              # Ngôn ngữ chính được phép xuất hiện trong Top 25 Core
        "secondary_languages": ["es", "es-MX"],   # Ngôn ngữ phụ (đối với thị trường Mỹ)
        "optional_secondary_languages": [],

        "primary_language_action": "keep",
        "secondary_language_action": "consider",
        "optional_secondary_action": "audit_or_consider",
        "foreign_language_action": "drop_to_audit",

        "allow_secondary_in_top25_core": False,
        "allow_secondary_in_broad_expansion": False,
        "secondary_max_quota_in_broad": 0,
        "secondary_max_quota_in_consider": 3,
        "allow_secondary_in_feature_file": False,
        "allow_secondary_in_style_file": False,

        "mixed_language_action": "manual_review",
        "unknown_language_action": "manual_review_if_high_score"
    },

    # =========================================================================
    # 3. PHÂN NHÓM TỪ KHÓA NGỮ NGHĨA (SEMANTIC GROUPS)
    # =========================================================================
    "agentic_keyword_classifier": {
        "enabled": True,
        "provider": "antigravity_subagent",
        "model": "subagent-cache-v1",
        "cache_only": True,
        "batch_size": 200,
        "prompt_version": "agentic-keyword-classifier-v1",
        "fail_on_api_error": True,
        "min_confidence": 0.55,
        "cache_path": ".cache/agentic_keyword_analysis.sqlite3",
        "pre_filter": {
            "enabled": True,
            "duplicate_strategy": "canonical_reuse",
            "preserve_if_matches_intent": True,
            "allow_possible_truncated_to_ai": True,
            "skip_rules": [
                "empty_keyword",
                "duplicate_keyword",
                "competitor_brand",
                "typo_blacklist",
                "truncated_keyword",
                "irrelevant_intent",
                "noise_only",
                "platform_affiliation",
                "platform_only"
            ]
        }
    },

    "intent_core_terms": [
        # Hệ máy NDS được ưu tiên tối đa
        "nds emulator", "ds emulator", "nintendo ds emulator", "nintendo ds emulador",
        "nds emulador", "ds emulador", "supernds", "super nds", "super nds emulator", 
        "nds emulator android", "ds emulator android", "nds console", "ds console",
        
        # Hỗ trợ All-in-one các hệ máy retro khác
        "all in one emulator", "multi emulator", "retro emulator", "retro game emulator", 
        "retro games emulator", "handheld emulator", "console emulator", "game emulator", 
        "games emulator", "classic emulator", "old games emulator"
    ],

    "feature_terms": [
        # Tính năng tay cầm skin đẹp (Differentiator mới)
        "controller skins", "gamepad skins", "custom buttons skins", "custom button skins",
        "beautiful skins", "virtual buttons skins", "retro controller skins", "gamepad layouts",
        
        # Các hệ máy khác ứng dụng hỗ trợ chơi game All-in-one
        "gba emulator", "gameboy emulator", "game boy emulator", "gbc emulator", "nes emulator", 
        "snes emulator", "n64 emulator", "psp emulator", "psx emulator",
        
        # Tính năng giả lập nâng cấp tương tự bản cũ
        "nds roms", "ds roms", "nds games", "ds games", "play nds games", "play ds games",
        "dual screen", "dual screen emulator", "save state", "load state", "fast forward",
        "cheat codes", "gamepad mapping", "bluetooth controller", "touch controls",
        "rom downloader", "rom scanner", "retro game library", "game hub", "save game state"
    ],

    "style_terms": [
        "retro", "nostalgia", "classic", "90s", "childhood", "pocket arcade", "vintage",
        "8-bit", "16-bit", "32-bit", "64-bit", "oldschool", "old school"
    ],

    "visual_terms": [
        "touch screen", "virtual buttons", "screen layout", "horizontal", "vertical", "portrait", "landscape",
        "button skins", "transparent buttons", "haptic feedback", "screen layout customization"
    ],

    # =========================================================================
    # 4. BỘ LỌC VÀ DANH SÁCH ĐEN (FILTERS & BLACKLIST)
    # =========================================================================
    "competitor_brands": [
        # Thêm các đối thủ cạnh tranh từ Game Emulator cũ
        "drastic", "melonds", "supernds", "lemuroid", "retroarch", "john gba", "my boy",
        "citra", "yuzu", "ryujinx", "dolphin", "nostalgia gba", "my oldboy", "pizza boy",
        "superds64", "super3ds", "moniqtap", "emulator pro",
        "ppsspp", "ppsspp gold", "dolphin emulator", "retroarch emulator",
        "delta emulator", "delta nintendo emulator", "citra emulator", "lime3ds", "lime3ds emulator",
        "aethersx2", "aethersx2 emulator", "lemuroid emulator", "my boy emulator", "my boy free",
        "my boy gba", "john gba lite", "john gba emulator", "gameboid", "gameboid emulator",
        "gba4ios", "gba4ios emulator", "vgbanext", "vgbanext emulator", "gamma emulator",
        "gamma game emulator", "drastic emulator", "drastic ds", "melon ds", "desmume",
        "snes9x", "snes9x ex", "zsnes", "nestopia", "fceux", "quicknes",
        "super retro 16", "super retro 16 plus", "epsxe", "epsxe emulator", "fpse", "fpse emulator",
        "pcsx2", "pcsx2 emulator", "damonps2", "damon ps2", "play emulator",
        "mupen64plus", "mupen64", "mupen", "project64", "project 64", "n64oid",
        "mame", "mame4droid", "mame4ios", "fba", "fbneo", "final burn alpha", "final burn neo",
        "kawaks", "classicboy", "classicboy lite", "retro game boy", "emu games", "emu paradise",
        "romsmania", "loveroms", "romhustler", "netboom", "netboom cloud gaming", "airconsole",
        "air console", "starparks", "chikii", "chikii cloud", "psplay", "psplay remote play",
        "xbplay", "xbplay remote play", "superpsx", "super psx", "bitboy", "bitboy emulator",
        "onecast", "onecast xbox", "happy chick", "happy chick emulator", "pizza emulator",
        "pizza boy gba", "easy emu", "mock emulator", "lucky emulator", "gk emulator",
        "gas emulator", "folium emulator", "jeans emulator", "emulsio", "emulator guia",
        "emulator md2", "emulator anak permainan", "emulator juegos pro", "retro game master",
        "retro game hub", "gb4", "gb4 emulator", "game boy 4"
    ],

    "noise_terms": [
        "app", "apps", "free", "download", "android", "for android", "new", "best", "top"
    ],

    "typo_blacklist": [
        "emulater", "emulatr", "emlator", "imulator", "ndsemu", "dsemu", "ndsrom", "emuladors"
    ],

    "irrelevant_intent_terms": [
        "widget", "widgets", "launcher", "theme launcher", "calculator", "keyboard", "font", "fonts",
        "video editor", "photo editor", "vpn", "antivirus", "cleaner", "booster"
    ],

    "risky_platform_terms": [
        # Thương hiệu HỆ MÁY/NHÀ SẢN XUẤT (phần cứng): là từ vựng mô tả chức năng bắt buộc
        # của app giả lập (vd "NDS emulator", "PSP emulator") -> rủi ro thấp hơn nhiều so với
        # nhắc tên tựa game cụ thể, nên chỉ đưa vào Consider Keywords (platform_context_action)
        # thay vị Drop cứng. "nintendo" thuộc nhóm này (nhà sản xuất), không phải risky_ip_terms.
        "nintendo", "iphone", "ios", "ipad", "apple", "switch", "3ds", "wii", "gamecube", "dsi",
        "playstation", "psp", "ps", "psx", "psx2", "ps1", "ps2", "ps3", "ps4", "ps5", "xbox", "sony", "sega", "microsoft"
    ],

    "risky_ip_terms": [
        # Thương hiệu NHÂN VẬT/TỰA GAME cụ thể (bản quyền sáng tạo): dùng từ này ngụ ý app
        # cho chơi ĐÚNG tựa game đó -> rủi ro vi phạm bản quyền game cao, luôn Drop cứng.
        # KHÔNG để tên nhà sản xuất/hệ máy (Nintendo, Sony, Sega...) vào đây - xem risky_platform_terms.
        "pokemon", "mario", "zelda", "metroid", "fire emblem", "donkey kong",
        "kirby", "animal crossing", "sonic", "gta", "grand theft auto", "megaman", "mega man",
        "harvest moon", "castlevania", "chrono trigger", "dragon quest", "dragon ball",

        # Nhà PHÁT HÀNH game (game publisher): nhắc tên hãng ngụ ý cho chơi kho game bản quyền
        # của hãng đó -> rủi ro IP như tựa game. Dùng ROOT (word-boundary) nên tự bắt mọi biến thể:
        # "rockstar" -> "rockstar games/emulator/classic"; "2k" -> "2k games/sports". Nhờ vậy KHÔNG
        # phải liệt kê từng chuỗi thủ công trong user_overrides.force_drop_terms mỗi lần xuất hiện biến thể mới.
        "rockstar", "2k", "take two", "square enix", "squaresoft", "enix",
        "capcom", "konami", "taito", "snk", "bandai namco", "namco", "bandai",
        "ea sports", "electronic arts", "ubisoft", "activision", "bethesda"
    ],
    "truncation_policy": {
        "enabled": True,
        "min_prefix_length": 2,
        "allowed_partial_terms": [],
        "protect_complete_tokens": True,
        "ignore_inflection_prefix": True,
        "low_confidence_action": "manual_review",
        "dangling_action": "manual_review"
    },

    # =========================================================================
    # 5. RISK HANDLING & PRECEDENCE (Chính sách rủi ro & Thứ tự ưu tiên)
    # =========================================================================
    "risk_policy": {
        "competitor_brand_action": "drop",      # Loại khỏi mô tả chính, giữ lại ở trang nghiên cứu đối thủ
        "ambiguous_brand_action": "consider",
        "risky_ip_action": "drop",              # Loại khỏi mô tả chính để tránh quét bản quyền IP game
        "platform_context_action": "consider",
        "platform_only_action": "drop",
        "platform_affiliation_action": "drop",
        "style_only_action": "reserve",
        "core_intent_override": True  
    },

    # =========================================================================
    # 6. KEYWORD QUOTA (Hạn ngạch phân bổ từ khóa)
    # =========================================================================
    "keyword_quota": {
        # LƯU Ý: "main_file" KHÔNG được dùng cho Main Keyword Shortlist nữa.
        # Từ khi metadata_selector.enabled=True, danh sách 40 từ khoá chính được
        # xếp hạng toàn cục theo UtilityScore (xem "metadata_selector" bên dưới),
        # không theo quota cứng theo section như dưới đây. Giữ lại khối này chỉ để
        # tương thích ngược cho _legacy_bucket_quota_build (khi enabled=False).
        "main_file": {
            "core_intent": 25,       # Số lượng keyword core chính (Top 25)
            "core_feature": 5,       # Số lượng keyword feature (Top 5)
            "broad_expansion": 5,    # Số lượng keyword mở rộng rộng hơn (Top 5)
            "consider": 5,           # Số lượng keyword đưa vào danh sách Consider
        },
        "feature_file": {
            "max_keywords": 30,
            "core_feature": 20,
            "feature_expansion": 5,
            "feature_test": 5
        },
        "style_file": {
            "max_keywords": 30,
            "intent_linked_style": 15,
            "broad_style": 10,
            "platform_style_consider": 5
        },
        "fallback_policy": {
            "allow_under_quota": True,
            "fill_from_next_best_eligible_bucket": True,
            "do_not_force_weak_keywords": True,
            "min_relevancy_for_fill": 0.45,
            "add_fill_reason_column": True
        }
    },

    "metadata_selector": {
        "enabled": True,
        "target_count": 40,
        "cluster_cap": 10,
        "quality_min_balanced_score": 0.35,
        "quality_min_relevancy": 0.45,
        "quality_min_volume": 6.0,
        "quality_min_reach": 1.0,
        "generic_safe_descriptors": ["retro", "classic"],
        # Loại từ đơn (1-token) generic khỏi Main Shortlist (01) — head term rộng,
        # không ra đúng app khi search & đốt tiền ads. Chỉ ảnh hưởng sheet 01; không
        # đổi phân loại, không đụng Feature file. Từ đơn đã khai báo trong
        # intent_core_terms (vd "supernds") vẫn được giữ; thêm vào single_token_keep
        # nếu muốn giữ thêm (vd "nds", "ds").
        "exclude_single_token_from_main": True,
        "single_token_keep": ["nds", "ds", "gba", "snes", "psp", "3ds", "n64", "supernds"],
    },

    "metadata_suitability": {
        "enabled": True,
        "single_token_policy": {
            "enabled": True,
            "default_action": "research_only",
            "keep_terms": ["nds", "ds", "gba", "snes", "psp", "3ds", "n64", "supernds"],
            "block_terms": ["arcade", "pizza", "moonlight", "turbospeed", "portable", "games", "game"],
        },
    },

    # =========================================================================
    # 7. LANGUAGE NATURALNESS (Độ tự nhiên ngôn ngữ)
    # =========================================================================
    "language_naturalness": {
        "enabled": True,
        "penalty_unnatural": -0.35,      
        "auto_drop_score_below": 0.15,   
        "rules": {
            "grammar_violation": {
                "patterns": [
                    r"\b(emulator emulator|rom rom|game game)\b",
                    r"\b(what is|how to|why do|when is|where is)\b"
                ],
                "flag": "UNNATURAL"
            },
            "redundancy": {
                "max_word_repeat_ratio": 0.5,
                "flag": "STUFFING"
            },
            "length_anomaly": {
                "max_natural_words": 6,
                "exception_if_contains_core": True,
                "flag": "TOO_LONG"
            },
            "cross_language_bleed": {
                "note": "Chỉ dùng để loại bỏ ngôn ngữ lạ, không flag nhầm secondary language",
                "forbidden_foreign_in_market": {},
                "flag": "LANGUAGE_BLEED"
            }
        }
    },

    # =========================================================================
    # 8. SCORING WEIGHTS (Trọng số Relevancy & Balanced Score)
    # =========================================================================
    "relevancy_weights": {
        "base": 0.30,
        "intent_core": 0.45,             
        "feature_specific": 0.15,
        "style_theme": 0.05,
        "visual_extra": 0.05,
        "penalty_competitor": -0.30,
        "penalty_noise": -0.20,
        "penalty_language_mismatch": -0.35,
        "penalty_unnatural": -0.35
    },

    "balanced_weights": {
        "VolumeN": 0.35,          
        "DifficultyN": 0.15,      
        "RelevancyScore": 0.30,   
        "CurrentRankN": 0.10,     
        "ExpansionValue": 0.10    
    },

    "scoring_normalization": {
        "volume": "maximum_reach_or_exponential_search_popularity",
        "difficulty": "inverse_0_100",
        "kei": "log_minmax",
        "rank": "tiered_rank_score",
        "unranked_rank_score": 0.0
    },

    "volume_score_policy": {
        "mode": "log_reach",
        "reach_reference": 100000.0,
        "search_popularity_floor": 5.0,
        "search_popularity_ceiling": 100.0,
        "exponential_curve_factor": 4.0,
        "current_volume_weight": 0.85,
        "historical_max_volume_weight": 0.15,
        "low_tier_threshold": 5.0,
        "low_tier_score_cap": 0.05,
        "exclude_low_tier_from_metadata_shortlist": False,
        "max_low_tier_consider_keywords": 999
    },

    # =========================================================================
    # 9. METADATA SLOTS & OUTPUT (Phân bổ & Định dạng đầu ra)
    # =========================================================================
    "metadata_slots": {
        "google_play": {
            "Title": 2,
            "Short Description": 7,
            "Full Description": 21
        },
        "app_store": {
            "Title": 2,
            "Subtitle": 5,
            "Keyword Field": 15,
            "Promotional Text": 5
        }
    },

    "max_word_overlap": 0.5,  
    "dedup_policy": {
        "auto_merge_token_bag": False,
        "review_overlap_threshold": 0.80,
        "accent_fold_auto_merge_locales": [],
        "enable_review_log": True,
    },
    "output_prefix": "ASO_Keyword_Planner",
    "output_mode": "excel_workbook",
    "output_workbook": {
        "enabled": True,
        "filename_pattern": "ASO_Keyword_Planner_{app_name}_{market}.xlsx",
        "export_csv_package": False,
        "export_markdown_report": False,
        "include_all_candidates_sheet": True,
        "include_optional_audit_sheets": True,
        "freeze_header_rows": True,
        "enable_filters": True,
        "format_as_tables": True,
        "wrap_text_columns": ["Keyword", "Reason", "DecisionReason", "LanguageReason", "FillReason"],
        "required_sheets": [
            "00_README_CONFIG",
            "01_Main_Keyword_Shortlist",
            "02_Feature_Keywords",
            "03_Style_Keywords",
            "04_Dropped_Audit",
            "05_Report_Summary",
            "06_All_Candidates",
            "13_Top_By_Volume"
        ],
        "optional_sheets": [
            "07_Language_Mismatch",
            "08_Generic_Style_Reserve",
            "09_Manual_Review",
            "10_Top_By_Score",
            "11_Secondary_Language"
        ]
    },

    # =========================================================================
    # 10. USER OVERRIDES (Ghi đè thủ công từ User)
    # =========================================================================
    "user_overrides": {
        "do_not_auto_drop_terms": [],
        "force_consider_terms": [],
        "suitability_keep_terms": ["retro game", "console emulator"],
        "force_drop_terms": [
            # Standalone console / IP terms (broad/misleading intent when alone)
            "80s", "1980s", "1990s", "ds", "gameboy", "gba", "mario", "n64", "nes", "nintendo", "playstation", "ps", "psp", "snes", "zelda",
            
            # Competitors & Unwanted apps
            "boy", "game remote", "gamer boy", "gamer boy emulator", "ideas", "ideas emulator", "manic", "manic emu", "naruto", "naruto emulator", "pspad", "retro bowl", "sboy", "sboy emulator", "xb",
            
            # Trademarked / Misleading brand/platform terms
            "my nintendo", "nitendo switch", "nintendo switch", "ps game emulator", "psx2",
            
            # Publisher & Store Brands / Irrelevant terms
            "2k", "2k games", "fsp", "google play", "google play games", "pp games", "rockstar", "rockstar games",
            # Broad / Standalone Generic single terms
            "games", "game", "play", "portable", "portátil", "jogos", "juegos", "emulator", "emulador"
        ],
        "force_top30_terms": [],
        "notes": []
    }
}
