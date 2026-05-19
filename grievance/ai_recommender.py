# ai_recommender.py

KEYWORD_MAP = {

    "ac": [
        "technical",
        "electrician",
        "maintenance",
        "ac repair"
    ],

    "wifi": [
        "technical",
        "network",
        "internet"
    ],

    "light": [
        "electrician",
        "technical",
        "maintenance"
    ],

    "clean": [
        "cleaner",
        "cleaning"
    ],

    "security": [
        "security",
        "guard",
        "cctv"
    ],

    "water": [
        "plumber",
        "maintenance"
    ],

    "bench": [
        "worker",
        "carpenter"
    ]
}


def get_matching_keywords(text):

    text = text.lower()

    matched = []

    for keyword, staff_types in KEYWORD_MAP.items():

        if keyword in text:

            matched.extend(staff_types)

    return list(set(matched))