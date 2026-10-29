"""A Song's profile text: AcousticBrainz labels written as words, plus instruments."""

from collections.abc import Mapping

THRESHOLD = 0.6

# (classifier, class) -> words. Only labels that describe how a Song sounds; negative
# classes ("not_happy") and the weakest classifiers (moods_mirex clusters, ismir04
# rhythm, tzanetakis genres) are left out.
WORDS = {
    ("mood_relaxed", "relaxed"): "relaxed, calm",
    ("mood_happy", "happy"): "happy",
    ("mood_sad", "sad"): "sad",
    ("mood_aggressive", "aggressive"): "aggressive",
    ("mood_party", "party"): "party",
    ("mood_acoustic", "acoustic"): "acoustic",
    ("mood_electronic", "electronic"): "electronic",
    ("danceability", "danceable"): "danceable",
    ("voice_instrumental", "instrumental"): "instrumental",
    ("voice_instrumental", "voice"): "vocals",
    ("gender", "female"): "female voice",
    ("gender", "male"): "male voice",
    ("timbre", "dark"): "dark",
    ("timbre", "bright"): "bright",
    ("genre_dortmund", "alternative"): "alternative",
    ("genre_dortmund", "blues"): "blues",
    ("genre_dortmund", "electronic"): "electronic music",
    ("genre_dortmund", "folkcountry"): "folk, country",
    ("genre_dortmund", "funksoulrnb"): "funk, soul, r&b",
    ("genre_dortmund", "jazz"): "jazz",
    ("genre_dortmund", "pop"): "pop",
    ("genre_dortmund", "raphiphop"): "rap, hip hop",
    ("genre_dortmund", "rock"): "rock",
    ("genre_rosamerica", "cla"): "classical",
    ("genre_rosamerica", "dan"): "dance",
    ("genre_rosamerica", "hip"): "hip hop",
    ("genre_rosamerica", "jaz"): "jazz",
    ("genre_rosamerica", "pop"): "pop",
    ("genre_rosamerica", "rhy"): "rhythm and blues",
    ("genre_rosamerica", "roc"): "rock",
}


def profile_text(
    acousticbrainz: Mapping[str, Mapping[str, float]], instruments: list[str]
) -> str:
    words: list[str] = []
    for (classifier, label), text in WORDS.items():
        if acousticbrainz.get(classifier, {}).get(label, 0) > THRESHOLD:
            words.extend(w for w in text.split(", ") if w not in words)
    profile = ", ".join(words)
    if instruments:
        profile += ". Instruments: " + ", ".join(instruments)
    return profile
