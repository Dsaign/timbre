# timbre

A music finder: a person describes the music they want in their own words, and timbre returns songs that fit that description.

## Language

**Description**:
The free text a person types to say what they want to hear: a preference, a mood, an instrument, or a mix of these.
_Avoid_: Query, prompt, search term

**Song**:
A single recorded piece of music in the Catalog, identified by its title and artist.
_Avoid_: Track, music, recording

**Catalog**:
The full set of Songs timbre can return, built only from open music data, never from Spotify.
_Avoid_: Library, database, dataset

**Fit**:
How closely a Song suits a Description, as judged by timbre's model. After a name match, Fit is measured against the Description averaged with the named Songs, so the Description's own meaning always counts.
_Avoid_: Similarity, score, relevance

**Match**:
A Song returned for a Description, for one of three reasons: a name match, a Fit that passes the cutoff, or a tag that matches the Description and is among the Song's 3 most-voted tags. Name matches come first. The rest are ordered by fusing two rankings, by Fit and by tag, with the tag ranking counting more the more of the Description its tag covers (filler words such as "pra", "com" or "the" aside). After name matches, only the first 60 related Songs are Matches. The number of Matches is the count shown for a search.
_Avoid_: Result, recommendation, hit

**Name match**:
A Song whose whole main artist name (guests after "feat."/"ft." don't count), or whole title of two words or more, matches the Description, typos and accents allowed. One word of a longer name never matches.
_Avoid_: Artist search, title search

**Tag**:
A genre or mood label on a Song, from open music data, most-voted first. A tag matches a Description when it appears in it as a phrase.
_Avoid_: Genre, label, category

**Popularity**:
How widely a Song is listened to, taken from open listening data.
_Avoid_: Plays, streams, hotness

**Feedback**:
A visitor's vote that one Match does or does not fit the Description it was returned for.
_Avoid_: Rating, review, like

**Benchmark**:
Descriptions, each with the Songs that should be Matches, used to score the model through the same search visitors get (name matches, tags and Fit). Three files: the owner's hand-written ones, Bob's drafted ones (both reviewed by the owner) and ones generated from the Catalog (not reviewed). Its score is the share of each Description's Songs among its first 24 Matches. A Description may also list accept tags, the tags that make any Match count as on target for it; precision is then how many of its first 16 Matches carry one, out of 16. It is never used for training, and no Description close to one of its Descriptions is either.
_Avoid_: Test set, eval set, golden set

**Preview**:
Listening to a Match through Spotify. Spotify's only role in timbre is Preview: it never decides which Songs are Matches.
_Avoid_: Play, sample, listen
