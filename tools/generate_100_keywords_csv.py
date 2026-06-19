import csv

keywords = [
    # 1. TikTok & Social Media Trends
    ("tiktok funny face filters", 72, 24),
    ("unicorn head filter", 55, 12),
    ("tiktok face filters", 70, 22),
    ("funny face viral challenge", 40, 4),
    ("viral face filters", 51, 10),
    ("tiktok effects", 78, 30),
    ("unicorn filter", 45, 10),
    ("time warp scan", 64, 20),
    ("warp scan filter", 58, 15),
    ("time warp scan app", 50, 12),
    ("time warp filter", 55, 14),
    ("tiktok funny filters", 65, 18),
    ("viral tiktok filters", 60, 16),
    ("funny face challenge", 44, 6),
    ("funny filter tiktok", 58, 15),
    ("trending face filters", 48, 8),
    ("trending tiktok filters", 55, 12),
    ("capcut templates funny", 68, 28),
    ("wiggle effect filter", 38, 3),
    ("waterfall warp filter", 35, 2),

    # 2. Animal Morphs & Head Filters
    ("animal face filter", 59, 14),
    ("animal morph filter", 45, 8),
    ("brown horse morph", 35, 3),
    ("horse morph filter", 38, 4),
    ("platypus face filter", 30, 2),
    ("camel face filter", 32, 2),
    ("rat face filter", 36, 3),
    ("dragon head filter", 34, 2),
    ("husky head filter", 33, 2),
    ("funny animal filters", 46, 8),
    ("animal head filters", 40, 5),
    ("animal face swap", 50, 12),
    ("dog face filter", 65, 24),
    ("cat face filter", 62, 20),
    ("funny dog filter", 48, 8),
    ("funny cat filter", 45, 6),
    ("monkey face filter", 42, 5),
    ("lion face filter", 38, 4),
    ("tiger face filter", 36, 3),
    ("animal camera filters", 40, 6),

    # 3. Funny Face Filters & Silly Camera Effects
    ("funny face filters", 72, 24),
    ("funny face filter", 68, 20),
    ("face filter", 82, 40),
    ("face filters", 85, 44),
    ("funny filters", 69, 18),
    ("funny filter", 65, 15),
    ("silly face filter", 54, 10),
    ("weird face filters", 54, 11),
    ("crazy face filters", 50, 8),
    ("funny camera effects", 60, 22),
    ("funny face camera", 58, 18),
    ("silly face camera", 42, 5),
    ("funny camera filters", 62, 20),
    ("best face filter", 58, 18),
    ("top funny filters", 48, 10),
    ("camera effects funny", 50, 12),
    ("funny face maker", 44, 6),
    ("silly selfie camera", 38, 3),
    ("funny selfie filters", 46, 8),
    ("ugly face filter", 50, 12),

    # 4. Face Swap & Face Changer
    ("face swap", 80, 42),
    ("face swap filter", 71, 25),
    ("face changer", 58, 16),
    ("face changer app", 55, 14),
    ("funny face changer", 48, 8),
    ("face swap app", 74, 35),
    ("face swap online", 65, 25),
    ("free face swap", 68, 22),
    ("face morph", 58, 15),
    ("face morph filter", 52, 11),
    ("face transformation", 46, 8),
    ("gender swap filter", 64, 22),
    ("boy to girl filter", 60, 20),
    ("old face filter", 70, 28),
    ("young face filter", 54, 12),
    ("baby face filter", 58, 14),
    ("fat face filter", 48, 8),
    ("cartoon face filter", 62, 20),
    ("caricature filter", 42, 5),
    ("funny morphing app", 38, 3),

    # 5. Face Distortion & Comedic Styles
    ("distorted face", 48, 8),
    ("distorted face filter", 46, 7),
    ("face distortion filter", 44, 6),
    ("face stretch filter", 42, 5),
    ("face warp filter", 45, 7),
    ("face warp scanner", 38, 4),
    ("big nose filter", 46, 8),
    ("cry face filter", 58, 14),
    ("sad face filter", 54, 12),
    ("angry face filter", 44, 6),
    ("laughing filter", 50, 10),
    ("smile filter", 55, 12),
    ("alien face filter", 42, 5),
    ("monster face filter", 38, 4),
    ("zombie face filter", 46, 8),
    ("ghost face filter", 48, 10),
    ("anime face filter", 60, 22),
    ("comic face filter", 42, 5),
    ("sketch face filter", 40, 4),
    ("funny expression filter", 36, 2),
]

csv_path = r"c:\Users\VOLIO\Documents\ASO_MVP\apps\FunVid\Input\062026\FunVid_100_Keywords_US_EN.csv"
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Keyword", "Volume", "Difficulty", "KEI", "Rank", "Rank Status", "Maximum Reach"
    ])
    for kw, vol, diff in keywords:
        kei = round((vol * vol) / max(1, diff), 1)
        writer.writerow([
            kw, vol, diff, kei, "Unranked", "unranked", vol * 100
        ])

print("Successfully written 100 keywords to apps/FunVid/Input/062026/FunVid_100_Keywords_US_EN.csv")
