import csv

keywords = [
    # Animals Face specifics
    ("animals face", 68, 14),
    ("animal face test", 52, 6),
    ("what animal do i look like", 62, 10),
    ("what animal do i look like filter", 58, 8),
    ("animal look alike", 55, 8),
    ("animal look alike filter", 52, 7),
    ("animal face shape", 46, 5),
    ("animal face type", 45, 4),
    ("cat face shape", 48, 6),
    ("fox face shape", 42, 3),
    ("deer face shape", 40, 2),
    ("bunny face shape", 41, 3),
    ("puppy face shape", 43, 3),
    ("filter bạn giống con gì", 35, 1),
    ("filter khuôn mặt động vật", 38, 2),
    ("filter test khuôn mặt động vật", 32, 1),
    
    # Generic
    ("animals face filter", 64, 12),
    ("animal face filter", 62, 11),
    ("animals face tiktok", 55, 8),
    ("animals face filter tiktok", 52, 7),
    ("animal face app", 58, 10),
    ("animal face swap", 50, 8),
    ("face to animal filter", 45, 4),
    ("feline face filter", 36, 2),
    ("what animal are you filter", 48, 5),
]

csv_path = r"c:\Users\VOLIO\Documents\ASO_MVP\FunVid_AnimalFace_US_EN.csv"
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

print("Generated FunVid_AnimalFace_US_EN.csv")
