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
How closely a Song suits a Description, as judged by timbre's model.
_Avoid_: Similarity, score, relevance

**Match**:
A Song whose Fit with a Description passes the cutoff. The number of Matches is the count shown for a search.
_Avoid_: Result, recommendation, hit

**Popularity**:
How widely a Song is listened to, taken from open listening data.
_Avoid_: Plays, streams, hotness

**Feedback**:
A visitor's vote that one Match does or does not fit the Description it was returned for.
_Avoid_: Rating, review, like

**Benchmark**:
The fixed set of 100 Descriptions, each with the Songs that should be Matches, used to score the model. It is never used for training.
_Avoid_: Test set, eval set, golden set

**Preview**:
Listening to a Match through Spotify. Spotify's only role in timbre is Preview: it never decides which Songs are Matches.
_Avoid_: Play, sample, listen
