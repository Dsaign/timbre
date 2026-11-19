"""One-off: write the generated Benchmark (ticket 20) from the local Catalog.

The database port is not published, so run it in the worker container, from back/:

    docker compose exec -T worker python - < scripts/generate_benchmark.py \\
        > src/timbre_back/benchmark_generated.json

Each Description crosses a frequent genre tag with an AcousticBrainz mood or voice
label, phrased the way a visitor types it, one in pt-BR and one in English per pair.
Its expected Songs have the genre among their 3 most-voted tags and the label above its
threshold, most listened first (at most 2 per artist). Its accept_tags are tag keys (no
tags are committed, ADR 0002) of the genre and its close relatives. One Description of
each pair uses a paraphrase instead of the genre's name, so the Benchmark does not only
test tag lookup. A Description within train.NEAR of a drafted training Description is
dropped, so the Benchmark keeps none of them out of training. Deterministic: fixed
seed, rows read in id order. Statistics go to stderr.
"""

import json
import random
import re
import sys
import unicodedata
from collections import Counter
from typing import Any

import numpy as np
import psycopg

from timbre_back import train
from timbre_back.benchmark import FILES
from timbre_back.db import conninfo
from timbre_back.embed import embed_query
from timbre_back.feedback import normalize
from timbre_back.search import MAIN_ARTIST

SEED = 20
SONGS = 5  # expected Songs per Description, at least benchmark.MIN_SONGS
PER_ARTIST = 2

# key: (English name, pt-BR name, English paraphrase, pt-BR paraphrase, relatives).
# The key is the tag the expected Songs carry; key and relatives are the accept_tags.
GENRES: dict[str, tuple[str, str, str, str, list[str]]] = {
    "rock": (
        "rock",
        "rock",
        "loud guitar band music",
        "som de banda com guitarra",
        ["classic rock", "hard rock", "alternative rock", "indie rock", "pop rock"],
    ),
    "pop": (
        "pop",
        "pop",
        "catchy radio hits",
        "hits chiclete de rádio",
        ["dance pop", "pop rock", "synth pop", "electropop", "teen pop", "indie pop"],
    ),
    "electronic": (
        "electronic music",
        "música eletrônica",
        "synth and drum machine music",
        "som de sintetizador e batida",
        ["electronica", "electro", "house", "techno", "downtempo", "idm", "edm"],
    ),
    "alternative rock": (
        "alternative rock",
        "rock alternativo",
        "90s college radio guitar bands",
        "bandas de guitarra dos anos 90 fora do mainstream",
        ["alt rock", "alternative", "indie rock", "grunge", "post grunge", "britpop"],
    ),
    "hip hop": (
        "hip hop",
        "rap",
        "rhymes over beats",
        "rima em cima de batida",
        ["rap", "hip hop rap", "rap hip hop", "pop rap", "trap", "east coast hip hop"],
    ),
    "indie rock": (
        "indie rock",
        "rock indie",
        "guitar music from small independent bands",
        "som de banda independente com guitarra",
        ["indie", "alternative rock", "indie pop", "post punk revival", "garage rock"],
    ),
    "metal": (
        "metal",
        "metal",
        "heavy distorted guitars with double bass drums",
        "som pesado e agressivo",
        ["heavy metal", "thrash metal", "death metal", "alternative metal", "nu metal"],
    ),
    "heavy metal": (
        "heavy metal",
        "heavy metal",
        "80s headbanging music with screaming solos",
        "som pra bater cabeça dos anos 80",
        ["metal", "thrash metal", "power metal", "speed metal", "british metal"],
    ),
    "hard rock": (
        "hard rock",
        "hard rock",
        "loud riffs and big choruses for stadiums",
        "riff alto e refrão de estádio",
        ["heavy metal", "classic rock", "arena rock", "glam rock", "blues rock"],
    ),
    "classic rock": (
        "classic rock",
        "rock clássico",
        "old school guitar anthems from the 70s",
        "som das antigas dos anos 70 com guitarra",
        ["album rock", "hard rock", "blues rock", "psychedelic rock", "soft rock"],
    ),
    "punk": (
        "punk",
        "punk",
        "fast three chord rebel songs",
        "som rápido e rebelde de três acordes",
        ["punk rock", "hardcore punk", "pop punk", "post punk", "garage rock"],
    ),
    "indie pop": (
        "indie pop",
        "pop indie",
        "quirky bedroom songs",
        "som fofinho de quarto",
        ["indie", "dream pop", "jangle pop", "twee pop", "chamber pop", "indie rock"],
    ),
    "synth pop": (
        "synthpop",
        "synthpop",
        "80s keyboard driven songs",
        "som de teclado dos anos 80",
        ["synthpop", "new wave", "electropop", "dance rock", "synthwave"],
    ),
    "r&b": (
        "r&b",
        "r&b",
        "smooth sensual grooves",
        "som suave e sensual",
        ["contemporary r&b", "r b", "soul", "neo soul", "alternative r&b"],
    ),
    "soul": (
        "soul",
        "soul",
        "classic motown style music",
        "som estilo motown das antigas",
        ["neo soul", "funk", "r&b", "deep soul", "pop soul", "funk soul"],
    ),
    "downtempo": (
        "downtempo",
        "downtempo",
        "slow laid back electronic beats",
        "batida eletrônica lenta e tranquila",
        ["trip hop", "chillout", "ambient", "nu jazz", "electronica", "chillwave"],
    ),
    "folk": (
        "folk",
        "folk",
        "songs with acoustic guitar and harmonica",
        "música de violão e gaita",
        ["folk rock", "indie folk", "singer songwriter", "folk pop", "americana"],
    ),
    "progressive rock": (
        "progressive rock",
        "rock progressivo",
        "long complex epics with odd time signatures",
        "músicas longas e complexas cheias de solo",
        ["prog rock", "art rock", "symphonic rock", "progressive metal"],
    ),
    "ambient": (
        "ambient",
        "música ambiente",
        "atmospheric soundscapes",
        "paisagens sonoras atmosféricas",
        ["dark ambient", "new age", "drone", "downtempo", "post rock"],
    ),
    "soundtrack": (
        "movie soundtrack",
        "trilha sonora de filme",
        "music from films",
        "música de cinema",
        ["score", "movie soundtrack", "video game music", "vgm", "musical"],
    ),
    "new wave": (
        "new wave",
        "new wave",
        "80s synths with jangly guitars",
        "som oitentista com sintetizador",
        ["synth pop", "synthpop", "post punk", "dance rock", "power pop"],
    ),
    "trip hop": (
        "trip hop",
        "trip hop",
        "dark moody bristol beats",
        "batida sombria e chapada",
        ["downtempo", "electronica", "acid jazz", "big beat"],
    ),
    "jazz": (
        "jazz",
        "jazz",
        "saxophone music for a smoky club",
        "som de saxofone de barzinho",
        ["vocal jazz", "cool jazz", "hard bop", "nu jazz", "acid jazz", "swing"],
    ),
    "house": (
        "house music",
        "house",
        "four on the floor club beats",
        "batida de pista de balada",
        ["deep house", "electro house", "progressive house", "dance", "club dance"],
    ),
    "trap": (
        "trap",
        "trap",
        "808 bass with fast hi hats",
        "grave de 808 com chimbal rápido",
        ["hip hop", "rap", "cloud rap", "southern hip hop", "emo rap"],
    ),
    "death metal": (
        "death metal",
        "death metal",
        "brutal music with growled vocals",
        "som brutal com vocal gutural",
        ["melodic death metal", "black metal", "thrash metal", "metal"],
    ),
    "metalcore": (
        "metalcore",
        "metalcore",
        "breakdowns and screamed choruses",
        "breakdown e gritaria no refrão",
        ["melodic metalcore", "post hardcore", "screamo", "deathcore"],
    ),
    "post rock": (
        "post rock",
        "post rock",
        "long instrumental crescendos",
        "crescendos instrumentais longos",
        ["math rock", "ambient", "shoegaze", "post metal", "experimental rock"],
    ),
    "blues rock": (
        "blues rock",
        "blues rock",
        "dirty slide guitar grooves",
        "guitarra suja com slide",
        ["blues", "hard rock", "classic rock", "southern rock"],
    ),
    "power metal": (
        "power metal",
        "power metal",
        "epic songs about dragons with high pitched vocals",
        "som épico de dragão e fantasia",
        ["symphonic metal", "heavy metal", "speed metal", "folk metal"],
    ),
    "thrash metal": (
        "thrash metal",
        "thrash",
        "fast aggressive riffing",
        "riff rápido e agressivo",
        ["thrash", "speed metal", "heavy metal", "death metal"],
    ),
    "grunge": (
        "grunge",
        "grunge",
        "90s seattle sound",
        "som de seattle dos anos 90",
        ["alternative rock", "post grunge", "alternative metal"],
    ),
    "post punk": (
        "post punk",
        "pós punk",
        "cold gloomy bass driven songs",
        "som frio e sombrio com baixo marcado",
        ["new wave", "gothic rock", "goth rock", "post punk revival", "darkwave"],
    ),
    "psychedelic rock": (
        "psychedelic rock",
        "rock psicodélico",
        "trippy 60s music",
        "som lisérgico dos anos 60",
        ["psychedelic", "neo psychedelia", "acid rock", "stoner rock", "space rock"],
    ),
    "industrial": (
        "industrial",
        "industrial",
        "mechanical noisy beats",
        "som mecânico e barulhento",
        ["industrial metal", "industrial rock", "ebm", "electro industrial"],
    ),
    "funk": (
        "funk",
        "funk setentista",
        "slap bass grooves",
        "groove de baixo com slap",
        ["soul", "funk rock", "p funk", "disco", "funk soul", "g funk"],
    ),
    "classical": (
        "classical music",
        "música clássica",
        "orchestra pieces",
        "peças de orquestra",
        ["modern classical", "contemporary classical", "baroque", "romantic"],
    ),
    "nu metal": (
        "nu metal",
        "nu metal",
        "angsty 2000s heavy music with dj scratches",
        "som pesado dos anos 2000 com vocal raivoso",
        ["alternative metal", "rap metal", "rap rock", "industrial metal"],
    ),
    "post hardcore": (
        "post hardcore",
        "post hardcore",
        "screamy emotional guitar music",
        "som emotivo cheio de grito",
        ["emo", "screamo", "metalcore", "pop punk"],
    ),
    "emo": (
        "emo",
        "emo",
        "emotional guitar songs about heartbreak",
        "som de franjinha pra quem sofre por amor",
        ["emo pop", "screamo", "post hardcore", "pop punk", "punk pop", "midwest emo"],
    ),
    "pop punk": (
        "pop punk",
        "pop punk",
        "bouncy teen angst skate songs",
        "som de skatista adolescente",
        ["punk pop", "emo", "emo pop", "skate punk", "punk rock"],
    ),
    "country": (
        "country",
        "country",
        "cowboy songs",
        "música de caubói",
        ["country rock", "country pop", "americana", "outlaw country", "bluegrass"],
    ),
    "dubstep": (
        "dubstep",
        "dubstep",
        "wobbly bass drops",
        "grave pesado com drop",
        ["brostep", "drum and bass", "electro house", "future bass", "edm"],
    ),
    "disco": (
        "disco",
        "disco",
        "70s dancefloor music with strings",
        "som de discoteca dos anos 70",
        ["funk", "nu disco", "post disco", "dance", "boogie"],
    ),
    "shoegaze": (
        "shoegaze",
        "shoegaze",
        "dreamy walls of guitar noise",
        "paredão de guitarra sonhador",
        ["dream pop", "noise pop", "blackgaze", "post rock"],
    ),
    "dream pop": (
        "dream pop",
        "dream pop",
        "hazy ethereal songs",
        "som etéreo e nebuloso",
        ["shoegaze", "ethereal wave", "indie pop", "chillwave"],
    ),
    "lo fi": (
        "lo-fi",
        "lo-fi",
        "dusty mellow beats",
        "batidinha relaxante e chiada",
        ["lofi", "lo fi hip hop", "chillhop", "bedroom pop", "chillwave"],
    ),
    "britpop": (
        "britpop",
        "britpop",
        "90s british guitar bands",
        "bandas inglesas dos anos 90",
        ["alternative rock", "indie rock", "madchester"],
    ),
    "techno": (
        "techno",
        "techno",
        "pounding warehouse beats",
        "batida de galpão",
        ["minimal techno", "detroit techno", "house", "electro", "acid house"],
    ),
    "trance": (
        "trance",
        "trance",
        "euphoric rave synths",
        "sintetizador eufórico de rave",
        ["progressive trance", "psytrance", "uplifting trance", "eurodance"],
    ),
    "reggae": (
        "reggae",
        "reggae",
        "jamaican offbeat grooves",
        "som jamaicano de praia",
        ["roots reggae", "dancehall", "dub", "ska", "rocksteady"],
    ),
    "drum and bass": (
        "drum and bass",
        "drum and bass",
        "very fast beats with deep bass",
        "batida muito rápida com grave",
        ["jungle", "liquid funk", "breakbeat", "neurofunk"],
    ),
    "black metal": (
        "black metal",
        "black metal",
        "raw grim music from norway",
        "som cru e sombrio da noruega",
        ["death metal", "blackgaze", "atmospheric black metal", "doom metal"],
    ),
    "doom metal": (
        "doom metal",
        "doom",
        "slow crushing heavy riffs",
        "riff lento e esmagador",
        ["doom", "stoner rock", "sludge metal", "stoner metal", "gothic metal"],
    ),
    "gothic rock": (
        "goth rock",
        "rock gótico",
        "dark romantic songs for the night",
        "som sombrio e romântico pra noite",
        ["goth rock", "post punk", "darkwave", "deathrock", "gothic metal"],
    ),
    "reggaeton": (
        "reggaeton",
        "reggaeton",
        "latin perreo beats",
        "batida de perreo",
        ["latin", "latin pop", "latin trap", "dancehall"],
    ),
    "k pop": (
        "k-pop",
        "k-pop",
        "korean idol groups",
        "grupos de idol coreano",
        ["korean", "j pop", "dance pop"],
    ),
    "latin": (
        "latin music",
        "música latina",
        "songs in spanish",
        "som em espanhol",
        ["latin pop", "reggaeton", "salsa", "bachata", "latin rock"],
    ),
    "singer songwriter": (
        "singer-songwriter",
        "cantor e compositor",
        "intimate songs with just a voice and a guitar",
        "voz e violão intimista",
        ["folk", "indie folk", "acoustic", "folk pop"],
    ),
    "synthwave": (
        "synthwave",
        "synthwave",
        "retro neon synths from an 80s movie",
        "sintetizador retrô neon de filme oitentista",
        ["outrun", "retrowave", "synth pop", "darksynth", "vaporwave"],
    ),
    "video game music": (
        "video game music",
        "música de videogame",
        "music from games",
        "trilha de jogo",
        ["vgm", "chiptune", "soundtrack", "score"],
    ),
    "soft rock": (
        "soft rock",
        "rock suave",
        "mellow 70s radio songs",
        "som tranquilo de rádio dos anos 70",
        ["adult contemporary", "yacht rock", "classic rock", "pop rock"],
    ),
    "gangsta rap": (
        "gangsta rap",
        "rap gangsta",
        "street rhymes about the hood",
        "rimas sobre a quebrada",
        ["hardcore hip hop", "west coast hip hop", "g funk", "thug rap", "hip hop"],
    ),
    "indie folk": (
        "indie folk",
        "folk indie",
        "cozy cabin songs with banjo",
        "som aconchegante de cabana",
        ["folk", "singer songwriter", "chamber folk", "folk pop", "americana"],
    ),
    "stoner rock": (
        "stoner rock",
        "stoner rock",
        "fuzzy desert riffs",
        "riff chapado de deserto",
        ["stoner metal", "doom metal", "desert rock", "psychedelic rock"],
    ),
    "edm": (
        "edm",
        "eletrônica de festival",
        "festival bangers",
        "som de festival",
        ["electro house", "progressive house", "big room", "dubstep", "dance"],
    ),
    "christmas music": (
        "christmas songs",
        "música de natal",
        "songs for the holidays",
        "som pra ceia de fim de ano",
        ["christmas", "holiday", "xmas"],
    ),
    "symphonic metal": (
        "symphonic metal",
        "metal sinfônico",
        "operatic heavy music with an orchestra",
        "som pesado com orquestra e vocal lírico",
        ["gothic metal", "power metal", "symphonic rock"],
    ),
    "garage rock": (
        "garage rock",
        "rock de garagem",
        "raw scrappy guitar songs",
        "som cru e sujo de garagem",
        ["garage punk", "garage rock revival", "punk", "indie rock"],
    ),
}

# name: (classifier, class, threshold, English templates, pt-BR templates)
LABELS: dict[str, tuple[str, str, float, list[str], list[str]]] = {
    "sad": (
        "mood_sad",
        "sad",
        0.7,
        ["sad {g}", "{g} to cry to", "{g} for a breakup", "melancholic {g}"],
        ["{g} pra chorar", "{g} triste", "{g} pra sofrer na bad", "{g} de fossa"],
    ),
    "happy": (
        "mood_happy",
        "happy",
        0.7,
        ["happy {g}", "feel good {g}", "upbeat {g} to cheer me up"],
        ["{g} pra cima", "{g} pra ficar feliz", "{g} de alto astral"],
    ),
    "aggressive": (
        "mood_aggressive",
        "aggressive",
        0.7,
        ["aggressive {g}", "{g} for the gym", "angry {g} to scream along"],
        ["{g} pra treinar", "{g} pra academia", "{g} com raiva pra gritar junto"],
    ),
    "relaxed": (
        "mood_relaxed",
        "relaxed",
        0.9,
        ["chill {g}", "relaxing {g} to unwind", "{g} for a lazy sunday"],
        ["{g} pra relaxar", "{g} de boa pra descansar", "{g} pra domingo de manhã"],
    ),
    "party": (
        "mood_party",
        "party",
        0.7,
        ["{g} for a party", "{g} to get the party started", "{g} for a night out"],
        ["{g} pra festa", "{g} pra balada", "{g} pra animar a festa"],
    ),
    "acoustic": (
        "mood_acoustic",
        "acoustic",
        0.7,
        ["acoustic {g}", "unplugged {g}"],
        ["{g} de violão", "{g} acústico e intimista", "{g} só no violão"],
    ),
    "danceable": (
        "danceability",
        "danceable",
        0.9,
        ["danceable {g}", "{g} to dance to"],
        ["{g} pra dançar", "{g} dançante"],
    ),
    "female": (
        "gender",
        "female",
        0.9,
        ["{g} with female vocals", "{g} sung by a woman"],
        ["{g} com vocal feminino", "{g} com voz de mulher"],
    ),
    "male": (
        "gender",
        "male",
        0.9,
        ["{g} with male vocals", "{g} with a deep male voice"],
        ["{g} com vocal masculino", "{g} com voz grave de homem"],
    ),
    "instrumental": (
        "voice_instrumental",
        "instrumental",
        0.9,
        ["instrumental {g}", "{g} without vocals", "{g} with no singing to focus"],
        ["{g} instrumental", "{g} sem voz", "{g} sem vocal pra estudar"],
    ),
}
# A sung label also needs a voice: AcousticBrainz guesses a gender for any Song.
SUNG = {"female", "male"}

NAMED_SQL = r"""
SELECT EXISTS (
  SELECT FROM catalog.songs, (SELECT catalog.unaccented(%(d)s) AS u) d
  WHERE {artist} %% u AND similarity({artist}, u) >= 0.6
    OR catalog.unaccented(title) %% u
      AND similarity(catalog.unaccented(title), u) >= 0.7 AND title ~ '\S\s+\S'
)""".replace("{artist}", MAIN_ARTIST)


def key(text: str) -> str:
    """catalog.tag_keys in Python: lowercase, no accents, words joined by one space."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z&]+", " ", plain).split())


def literal(description: str, accept: list[str]) -> bool:
    """Whether any accept tag is a phrase of the Description, word for word."""
    padded = f" {key(description)} "
    return any(f" {tag} " in padded for tag in accept)


def label(song: dict[str, Any], name: str) -> float:
    classifier, cls, *_ = LABELS[name]
    p = float(song["acousticbrainz"].get(classifier, {}).get(cls, 0))
    if name in SUNG:
        p = min(p, float(song["acousticbrainz"]["voice_instrumental"]["voice"]))
    return p


def expected(songs: list[dict[str, Any]], genre: str, name: str) -> list[Any]:
    threshold = LABELS[name][2]
    per_artist: Counter[str] = Counter()
    picked = []
    for song in songs:  # most listened first
        if genre in song["top3"] and label(song, name) >= threshold:
            if per_artist[song["artist"]] < PER_ARTIST:
                per_artist[song["artist"]] += 1
                picked.append(song)
                if len(picked) == SONGS:
                    break
    return picked


def main() -> None:
    rng = random.Random(SEED)  # noqa: S311 - a reproducible file, not a secret
    taken = {
        normalize(e["description"])
        for f in FILES
        if f.exists() and "generated" not in f.name
        for e in json.loads(f.read_text())
    }
    training = np.array(
        # As the train job embeds them: normalized, once each.
        [embed_query(d) for d in train.examples(train.drafted())],
        dtype=np.float32,
    )
    with psycopg.connect(conninfo("ml_worker")) as conn:
        rows = conn.execute(
            "SELECT id::text, title, artist, acousticbrainz, tag_keys[1:3]"
            " FROM catalog.songs"
            " WHERE vector IS NOT NULL AND acousticbrainz IS NOT NULL"
            " ORDER BY listens DESC, id"
        ).fetchall()
        songs = [
            {"id": i, "title": t, "artist": a, "acousticbrainz": ab, "top3": k or []}
            for i, t, a, ab, k in rows
        ]
        entries = []
        dropped = Counter[str]()
        for genre, (en, pt, en_para, pt_para, relatives) in GENRES.items():
            accept = sorted({genre, *relatives})
            for name, (*_, en_templates, pt_templates) in LABELS.items():
                picked = expected(songs, genre, name)
                if len(picked) < 3:
                    dropped["fewer than 3 Songs"] += 1
                    continue
                pt_uses_paraphrase = rng.random() < 0.5
                for templates, g in (
                    (pt_templates, pt_para if pt_uses_paraphrase else pt),
                    (en_templates, en if pt_uses_paraphrase else en_para),
                ):
                    description = rng.choice(templates).format(g=g)
                    if normalize(description) in taken:
                        dropped["duplicate"] += 1
                        continue
                    row = conn.execute(
                        NAMED_SQL, {"d": normalize(description)}
                    ).fetchone()
                    if row and row[0]:
                        dropped["names a Song"] += 1
                        continue
                    near = training @ np.array(embed_query(description), np.float32)
                    if near.max() >= train.NEAR:
                        dropped["near a training Description"] += 1
                        continue
                    taken.add(normalize(description))
                    entries.append(
                        {
                            "description": description,
                            "source": "generated",
                            "reviewed": False,
                            "accept_tags": accept,
                            "songs": [
                                {k: s[k] for k in ("id", "title", "artist")}
                                for s in picked
                            ],
                        }
                    )
    literal_share = sum(literal(e["description"], e["accept_tags"]) for e in entries)
    print(
        f"{len(entries)} Descriptions, {literal_share} with an accept tag word for"
        f" word, dropped {dict(dropped)}",
        file=sys.stderr,
    )
    # The ticket's rule: at least half are paraphrases or translations.
    if literal_share > len(entries) / 2:
        raise SystemExit("too many Descriptions name their tag word for word")
    json.dump(entries, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
