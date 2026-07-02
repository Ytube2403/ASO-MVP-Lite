FILTER_POLICY = {
    "semantic_mode": "game_emulator",
    "risky_ip_terms": [
        # Specific character/game-title IP to drop (trademark platform/company names
        # moved to risky_platform_terms below -- they're functional vocabulary for a
        # multi-console emulator app, not a specific copyrighted game being claimed)
        "pokemon",
        # Modern, sports, and unrelated game titles to drop
        "nba", "fifa", "pes", "efootball", "dream league", "dream soccer", "dls", "fc 24",
        "fc mobile", "ea fc", "pelé", "peles", "bomba patch", "futsal", "winning eleven",
        "football", "soccer", "nfl", "wwe", "smackdown", "ufc", "ufl", "fortnite", "forza",
        "rocket league", "pubg", "free fire", "roblox", "minecraft", "minicraft", "call of duty",
        "cod", "bully", "burnout", "once human", "brawlhalla", "cuphead", "dead space",
        "def jam", "delta force", "nascar", "rdr2", "toy story", "garena", "mobile legends",
        "pubg mobile", "freefire"
    ],
    # Trademark platform/console-maker names: functional vocabulary for an emulator app
    # (e.g. "nintendo switch emulator"), so these get the softer risky_platform_terms
    # treatment (Consider, plus core_intent_override rescue when declared in
    # intent_core_terms/feature_terms/style_terms) instead of a hard risky_ip Drop.
    "risky_platform_terms": ["nintendo", "sony", "xbox", "playstation", "ps1", "ps2", "ps3", "ps4", "ps5", "3ds", "wii", "switch", "gamecube"],
    "ambiguous_brand_terms": ["dolphin", "delta", "play"],
    "platform_affiliation_terms": [],
    "truncation_policy": {
        "enabled": True,
        "min_prefix_length": 2,
        "allowed_partial_terms": [],
        "protect_complete_tokens": True,
        "ignore_inflection_prefix": True,
        "low_confidence_action": "manual_review",
        "dangling_action": "manual_review",
    },
    "risk_policy": {
        "competitor_brand_action": "drop",
        "ambiguous_brand_action": "consider",
        "risky_ip_action": "drop",
        "platform_context_action": "consider",
        "platform_only_action": "drop",
        "platform_affiliation_action": "drop",
        "style_only_action": "reserve",
        "core_intent_override": True,
    },
    "volume_score_policy": {
        "mode": "log_reach",
        "reach_reference": 100000.0,
        "max_low_tier_consider_keywords": 3,
        "exclude_low_tier_from_metadata_shortlist": True
    },
    "keyword_quota": {
        "main_file": {
            "core_intent": 25,
            "core_feature": 5,
            "broad_expansion": 5,
            "consider": 5,
        }
    },
    "main_shortlist_builder": {
        "fallback_buckets": {
            "Broad Expansion": ["Feature Keywords", "System Keywords"]
        }
    },
    "metadata_quality_gate": {
        "enabled": True,
        "exclude_risk_from_consider": True,
        "exclude_game_names": [
            "pokemon", "mario", "zelda", "sonic", "crash", "street fighter", "tetris",
            "pacman", "naruto", "dragon ball", "dbz", "gta", "god of war", "tekken",
            "super smash bros", "final fantasy", "metal slug", "killer instinct",
            "donkey kong", "mortal kombat", "bloody roar", "contra", "digimon",
            "dino crisis", "kirby", "kof", "king of fighters", "metal gear",
            "resident evil", "silent hill", "tomb raider", "yu gi oh", "yugioh",
            "monster hunter", "basara", "excite bike", "excitebike", "inazuma eleven",
            "kamen rider", "patapon", "pepsiman", "pepsi man", "prince of persia",
            "road fighter", "rygar", "sly cooper", "suikoden", "ultraman", "yoshi"
        ],
        "section_floors": {
            "Core Intent Final": {"min_relevancy": 0.50, "min_balanced_score": 0.35},
            "Feature Keywords": {"min_relevancy": 0.50, "min_balanced_score": 0.35},
            "Broad Expansion": {"min_relevancy": 0.55, "min_balanced_score": 0.35},
            "Consider Keywords": {"min_relevancy": 0.60, "min_balanced_score": 0.35},
        },
        "demand": {
            "enabled": True,
            "percentile": 0.50,
            "min_volume_n": 0.12,
            "min_relevancy_for_volume_n": 0.75,
            "allow_exact_core_terms": True,
            "exact_core_min_relevancy": 0.75,
            "exact_core_min_volume": 7,
        },
    },
    "user_overrides": {
        "force_drop_terms": [
            # Standalone console / IP terms (broad/misleading intent when alone)
            "ds", "psp", "ps", "playstation", "nintendo", "mario", "zelda", "gba", "gameboy", "snes", "nes", "n64",
            # Competitors & Unwanted terms
            "sboy", "sboy emulator", "ideas emulator", "gamer boy emulator", "manic emu", "naruto emulator",
            "ideas", "gamer boy", "manic", "naruto", "retro bowl", "boy"
        ]
    }
}
