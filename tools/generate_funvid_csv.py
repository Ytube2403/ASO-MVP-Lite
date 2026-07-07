import csv

keywords = [
    # Core intents (Funny face filters, TikTok effects, face swap, morphing)
    ("unicorn head filter", 55, 12, "Core filter from user request (TikTok Unicorn Head 647537)"),
    ("unicorn filter", 45, 10, "Core filter from user request"),
    ("tiktok funny face filters", 62, 18, "Tiktok funny filters category"),
    ("tiktok face filters", 70, 22, "Tiktok face filters category"),
    ("tiktok effects", 78, 30, "Tiktok effects platform term"),
    ("funny face filter", 68, 20, "Funny face filter primary core intent"),
    ("funny face filters", 72, 24, "Funny face filters primary core intent"),
    ("funny filter", 65, 15, "Funny filter core intent"),
    ("funny filters", 69, 18, "Funny filters core intent"),
    ("face swap", 80, 42, "Face swap core intent"),
    ("face swap filter", 71, 25, "Face swap filter core intent"),
    ("face morph", 58, 15, "Face morph core intent"),
    ("face morph filter", 52, 11, "Face morph filter core intent"),
    ("animal face filter", 59, 14, "Animal face filter core intent"),
    ("character face filter", 50, 10, "Character face filter core intent"),
    ("weird face filters", 54, 11, "Weird face filters core intent"),
    ("distorted face", 48, 8, "Distorted face core intent"),
    ("distorted face filter", 46, 7, "Distorted face filter core intent"),
    ("silly camera effects", 42, 5, "Silly camera effects core intent"),
    ("camera effects", 60, 22, "Camera effects core intent"),
    ("face changer", 58, 16, "Face changer core intent"),
    ("face changer app", 55, 14, "Face changer app core intent"),
    ("funny face changer", 48, 8, "Funny face changer core intent"),
    ("funny face viral challenge", 40, 4, "Tiktok funny face viral challenge (from user request)"),
    ("funny face challenge", 44, 6, "Funny face challenge core intent"),
    ("viral face filters", 51, 10, "Viral face filters core intent"),
    
    # Specific morph filters (from App_Profile / user description)
    ("brown horse morph", 35, 3, "Specific horse morph filter name"),
    ("horse morph filter", 38, 4, "Horse morph filter name"),
    ("platypus face filter", 30, 2, "Specific platypus face filter name"),
    ("camel face filter", 32, 2, "Specific camel face filter name"),
    ("rat face filter", 36, 3, "Specific rat face filter name"),
    ("dragon head filter", 34, 2, "Specific dragon head filter name"),
    ("husky head filter", 33, 2, "Specific husky head filter name"),
    ("animal morph filter", 45, 8, "Animal morph filter name"),
    ("animal head filters", 40, 5, "Animal head filters name"),
    ("funny animal filters", 46, 8, "Funny animal filters name"),

    # Competitor Brands
    ("snapchat filters", 85, 50, "Competitor brand Snapchat"),
    ("snapchat face filters", 76, 35, "Competitor brand Snapchat"),
    ("instagram filters", 82, 48, "Competitor brand Instagram"),
    ("faceapp", 80, 45, "Competitor brand FaceApp"),
    ("reface", 70, 32, "Competitor brand Reface"),
    ("facelab", 55, 18, "Competitor brand FaceLab"),
    ("time warp scan", 64, 20, "Competitor brand Time Warp Scan"),
    ("warp scan filter", 58, 15, "Competitor brand Time Warp Scan"),
    ("talking tom cat 2", 72, 38, "Competitor brand Talking Tom"),
    ("talking tom filters", 48, 12, "Competitor brand Talking Tom"),
    ("lensa ai", 65, 25, "Competitor brand Lensa"),

    # General / Noise / Platform
    ("free apps", 75, 40, "General noise term"),
    ("funny videos", 82, 52, "General video category term"),
    ("download app", 70, 35, "General noise term"),
    ("best face filter", 58, 18, "Generic noise term (best)"),
    ("top funny filters", 48, 10, "Generic noise term (top)"),
    ("free face swap", 68, 22, "Noise term combined with core"),
    ("android camera", 62, 28, "Platform/device related"),
    ("camera app free", 68, 30, "Generic noise term"),
    
    # Irrelevant
    ("widget maker", 54, 18, "Irrelevant category widget"),
    ("custom widgets", 58, 22, "Irrelevant category widget"),
    ("home screen launcher", 60, 28, "Irrelevant category launcher"),
    ("game emulator", 65, 30, "Irrelevant category game"),
    ("prank sounds", 68, 32, "Irrelevant category prank sounds"),
    ("taser simulator", 55, 15, "Irrelevant category simulator"),
    ("wallpapers hd 4k", 74, 42, "Irrelevant category wallpaper"),
    ("cute koala wallpaper", 50, 12, "Irrelevant category wallpaper"),
    ("ringtones free", 70, 35, "Irrelevant category ringtone"),
    ("calculator hide app", 58, 20, "Irrelevant category calculator"),
]

# Write to CSV
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(PROJECT_ROOT, "data", "seeds", "FunVid_US_EN.csv")
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    # Header
    writer.writerow([
        "Keyword", "Volume", "Difficulty", "KEI", "Rank", "Rank Status", "Maximum Reach"
    ])
    for kw, vol, diff, reason in keywords:
        kei = round((vol * vol) / max(1, diff), 1)
        writer.writerow([
            kw, vol, diff, kei, "Unranked", "unranked", vol * 100
        ])

print("Successfully generated FunVid_US_EN.csv with", len(keywords), "keywords.")
