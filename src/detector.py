# Imports
import spacy
import pandas as pd

from .albert import AlbertNER, AlbertQA
from .endpoint_config import ASSETS_PATH, MODELS_PATH
from .logging_handler import init_logger, logger

import logging
import string
import re
import os


ACTOR = "actor"
DIRECTOR = "director"
CHARACETR = "character"

logger = init_logger()
logger.setLevel(logging.ERROR)

# NER Models
model = spacy.load("en_core_web_lg")
ner = AlbertNER(os.path.join(MODELS_PATH, "conll03"))

# QA Model to disambiguate
qa = AlbertQA(os.path.join(MODELS_PATH, "squad"))

# List of genres, actor, directors and titles
with open(os.path.join(ASSETS_PATH, "genres.list"), "r") as f:
    genres = f.read().split("\n")    
with open(os.path.join(ASSETS_PATH, "titles.list"), "r") as f:
    titles = f.read().split("\n")
with open(os.path.join(ASSETS_PATH, "actors.list"), "r") as f:
    actors = f.read().split("\n")
with open(os.path.join(ASSETS_PATH, "directors.list"), "r") as f:
    directors = f.read().split("\n")
    
# Regex
rates_l = [
   "g",
   "m",
   "gp",
   "pg\-7",
   "pg\-12",
   "pg\-13",
   "pg\-16",
   "pg\-18",
   "pg\-11",
   "pg 7",
   "pg 11",
   "pg 12",
   "pg 13",
   "pg 16",
   "pg 18",
   "pg\+7",
   "pg\+11",
   "pg\+12",
   "pg\+13",
   "pg\+16",
   "pg\+18",
   "pg",
   "r",
   "x",
   "nc\-17",
   "nr",
   "ur",
   "\+7",
   "\+12",
   "\+18",
   "General Audiences",
   "Parental Guidance Suggested",
   "Parents Strongly Cautioned",
   "Restricted",
   "Adults Only"
]
songs_l = [
   "song",
   "bso",
   "songs",
   "bsos",
   "music",
   "musical score",
   "track",
   "sound",
   "soundtrack",
   "soundtrac",
   "tracks",
   "soundtracks",
   "composition",
   "ost",
   "osts",
   "melody",
   "melodies",
   "lyric", 
   "lyrics", 
   "anthem",
   "anthems",
   "tune",
   "tunes",
   "sing",
   "piece", 
   "original soundtrack" 
]
trailers_l = [
   "trailer",
   "trailers",
   "corto",
   "cut",
   "advance",
   "announce"
]
awards_l = [
    "oscars",
    "sag",
    "sag award",
    "sag awards",
    "award",
    "awards",
    "Best Feature Film",
    "Best Actor",
    "Best Short Film",
    "Best British Short Film",
    "Special Jury Prize for Short Film",
    "Best Feature Documentary",
    "Best Student Film",
    "Best Music Video",
    "Best Short Documentary",
    "Best Animation",
    "Best First Film",
    "Best Picture",
    "Top Ten Films",
    "Best Director",
    "Best Actor",
    "Best Actress",
    "Best Supporting Actor",
    "Best Supporting Actress",
    "Best Ensemble Cast",
    "Best Original Screenplay",
    "Best Adapted Screenplay",
    "Best Cinematography",
    "Best Production Design",
    "Best Editing",
    "Best Original Score",
    "Best Visual Effects"
    "academy"
]

pat_songs = fr"\b(?:{'|'.join(songs_l)})\b"
pat_trailers = fr"\b(?:{'|'.join(trailers_l)})\b"
pat_rate = fr"\b(?:{'|'.join(rates_l)})\b(?:-rated| rated|)"
pat_year = "(?:since|before|after|)(?:1[8-9]{1}[0-9]{2}|2[0-9]{3})'?s?"
pat_director = "(?:directed|director|directed by)"
pat_awards = fr"\b(?:{'|'.join(awards_l)})\b"


# Check data with movie database
cols = ["original_title", "year", "genre", "director", "actors", "description"]
df_movies = pd.read_csv(os.path.join(ASSETS_PATH, "movies.csv"))
df_movies = df_movies.loc[df_movies.actors.notna()]

def check_data(actors, directors, years, titles, genres):
    new_actors = []
    new_directors = []
    new_characters = []
    
    df = df_movies.copy(deep=True)
    for actor in actors:
        actor_original = actor
        if "'" in actor:
            actor = actor[:actor.index("'")]
        if "`" in actor:
            actor = actor[:actor.index("`")]
        if "´" in actor:
            actor = actor[:actor.index("´")]
        df_tmp = df.copy(deep=True)
        df = filter_by_actor(df, actor)
        if not len(df):
            df = filter_by_director(df_tmp, actor)
            if len(df):
                new_directors.append(actor_original)
            else:
                df = df_tmp.copy(deep=True)
        else:
            new_actors.append(actor_original)
    
    for director in directors:
        director_original = director
        if "'" in director:
            director = director[:director.index("'")]
        if "`" in director:
            director = director[:director.index("`")]
        if "´" in director:
            director = director[:director.index("´")]
        df_tmp = df.copy(deep=True)
        df = filter_by_director(df, director)
        if not len(df):
            df = filter_by_actor(df_tmp, director)
            if len(df):
                new_actors.append(director_original)
            else:
                print(f"Outlier: {director}")
                df = df_tmp.copy(deep=True)
        else:
            new_directors.append(director_original)
    
    new_years = []
    for year in years:
        year_ = year.strip(string.punctuation).strip(string.ascii_letters)
        df_tmp = filter_by_year(df, year_)
        if not len(df_tmp):
            df = df.loc[df.year != year_]
        else:
            new_years.append(year)
            
    new_titles = []
    for title in titles:
        df_tmp = df.copy(deep=True)
        df = filter_by_title(df, title)
        if not len(df):
            df = df_tmp.copy(deep=True)
        else:
            new_titles.append(title)
            
    new_genres = []
    for genre in genres:
        df_tmp = df.copy(deep=True)
        df = filter_by_genre(df, genre)
        if not len(df):
            df = df_tmp.copy(deep=True)
        else:
            new_genres.append(genre)
    
        
    return new_actors, new_directors, new_years, new_titles, new_genres, df[cols]

def filter_by_director(df, director):
    return df.loc[df.director.str.lower() == director.lower()]

def filter_by_actor(df, actor):
    return pd.DataFrame([mov_ for mov_ in df.itertuples() if actor.lower() in mov_.actors.lower()])

def filter_by_genre(df, genre):
    return pd.DataFrame([mov_ for mov_ in df.itertuples() if genre.lower() in mov_.genre.lower()])

def filter_by_year(df, year):
    return df.loc[df.year == year]

def filter_by_title(df, title):
    return df.loc[df.original_title.str.lower() == title.lower()]


def get_titles(entities_albert):
    titles_tmp = []
    t = ""
    for ent in entities_albert:
        if ent[1] == "B-MISC":
            if t:
                titles_tmp.append(t)
            t = ent[0]
        elif ent[1] == "I-MISC":
            t += " " + ent[0]
        else:
            if t:
                titles_tmp.append(t)
            t = ""

    titles_tmp = list(set([t for t in titles_tmp]))
    titles_tmp = [t for t in titles_tmp if t.lower() in titles]
    
    return titles_tmp

def get_titles_from_re(text):
    text_words = text.split()
    if "film" in text_words:
        i = text_words.index("film")
        for j in reversed(range(4)):
            ent_tmp = " ".join(text_words[i+1:i+j+1])
            if ent_tmp in titles:
                return [ent_tmp]
    
    if "movie" in text_words:
        i = text_words.index("movie")
        for j in reversed(range(5)):
            ent_tmp = " ".join(text_words[i:i+j])
            if ent_tmp in titles:
                return [ent_tmp]
            
    return []
            
def get_titles_from_df(text, original_title):
    pat = fr"\b{original_title}\b"
    title = re.findall(pat, text, re.IGNORECASE)
    
    return title


def get_songs(text, characters):
    songs = re.findall(pat_songs, text, re.IGNORECASE)
    if not songs:
        return [], characters
    pat = fr"(?:{'|'.join(characters)}|)?\s?(?:{'|'.join([s.strip() for s in songs])})\s(?:by |of |from )?(?:{'|'.join(characters)}|)?"
    songs = re.findall(pat, text, re.IGNORECASE)
    new_characters = []
    for character in characters:
        add = True
        for song in songs:
            text_idx_tmp = text.index(song)
            text_tmp = text[text_idx_tmp-50:text_idx_tmp+len(song)+50]
            if character in text_tmp and re.findall("(?:by |of |from )", text_tmp):
                add = False
        if add:
            new_characters.append(character)
        else:
            songs.append(character)
    
    return songs, new_characters


def get_awards(text):
    awards = re.findall(pat_awards, text, re.IGNORECASE)
    
    return awards


def get_trailers(text):
    trailers = re.findall(pat_trailers, text, re.IGNORECASE)
    
    return trailers


def get_rate_avg(entities_spacy, text):
    ratings_avg = [ent[0] for ent in entities_spacy if ent[1] == "CARDINAL"]
    ratings_avg = list(set([t for t in ratings_avg]))
    
    real_ratings = []
    text_words = text.split()
    for rat in ratings_avg:
        w = rat.split()[-1]
        i = text_words.index(w)
        if len(text_words) > i+1:
            if text_words[i+1].strip(string.punctuation) == "stars":
                real_ratings.append(rat + " " + "stars")
        if "give" in text_words[i-5:i+5] or "/" in rat:
            real_ratings.append(rat)
    
    return real_ratings


def get_rate(text):
    rates = re.findall(pat_rate, text, re.IGNORECASE)
    
    return rates


def get_genre(text):
    genres_tmp = []
    for genre in genres:
        if genre in text:
            genres_tmp.append(genre)
    
    return genres_tmp

def get_genres_from_df(text, genre):
    genres = genre.split(",")
    pat = fr"\b(?:{'|'.join(genres)})\b"
    genres = re.findall(pat, text, re.IGNORECASE)
    
    return genres

def get_actors_from_df(text, actor):
    actors = actor.split(",")
    for i, person in enumerate(actors):
        if "'" in person:
            actors[i] = person[:person.index("'")]
        if "`" in person:
            actors[i] = person[:person.index("`")]
        if "´" in person:
            actors[i] = person[:person.index("´")]
            
    pat = fr"\b(?:{'|'.join(actors)})\b"
    actors = re.findall(pat, text, re.IGNORECASE)
    
    return actors

def get_directors_from_df(text, director):
    directors = director.split(",")
    for i, person in enumerate(directors):
        if "'" in person:
            directors[i] = person[:person.index("'")]
        if "`" in person:
            directors[i] = person[:person.index("`")]
        if "´" in person:
            directors[i] = person[:person.index("´")]
            
    pat = fr"\b(?:{'|'.join(directors)})\b"
    directors = re.findall(pat, text, re.IGNORECASE)
    
    return directors

def get_year(text):
    dates = re.findall(pat_year, text, re.IGNORECASE)
    dates = list(set([t for t in dates]))
    
    return dates


def get_persons(entities_spacy, entities_albert):
    persons = []
    for ent in entities_spacy:
        if ent[1] == "PERSON":
            persons.append(ent[0])

    p = ""
    for ent in entities_albert:
        if ent[1] == "B-PER":
            if p:
                persons.append(p)
            p = ent[0]
        elif ent[1] == "I-PER":
            p += " " + ent[0]
        else:
            if p:
                persons.append(p)
            p = ""
    persons = list(set([p.strip(string.punctuation) for p in persons]))
    
    return persons


def is_actor(person):
    if "'" in person:
        person = person[:person.index("'")]
    if "`" in person:
        person = person[:person.index("`")]
    if "´" in person:
        person = person[:person.index("´")]
    
    return person.lower() in actors


def is_director(person):
    if "'" in person:
        person = person[:person.index("'")]
    if "`" in person:
        person = person[:person.index("`")]
    if "´" in person:
        person = person[:person.index("´")]
        
    return person.lower() in directors


def disambiguate_person(person, text):
    if "'" in person:
        person = person[:person.index("'")]
    if "`" in person:
        person = person[:person.index("`")]
    if "´" in person:
        person = person[:person.index("´")]
        
    q_director = f"Is {person} a director?"
    q_actor = f"Is {person} an actor?"

    a_actor = qa.answer(q_actor, text)
    
    if a_actor:
        if re.findall(pat_director, a_actor, re.IGNORECASE):
            return DIRECTOR
        else:
            return ACTOR
    else:
        a_director = qa.answer(q_director, text)
        if a_director:
            return DIRECTOR
        else:
            if re.findall(pat_director, a_director, re.IGNORECASE):
                return DIRECTOR
            else:
                return ACTOR


def get_actors_from_df(text, actors):
    actors = actors.split(",")
    pat = fr"\b(?:{'|'.join([a.strip() for a in actors])})\b"
    actors = re.findall(pat, text, re.IGNORECASE)
    
    return actors

def get_directors_from_df(text, directors):
    directors = directors.split(",")
    pat = fr"\b(?:{'|'.join([d.strip() for d in directors])})\b"
    directors = re.findall(pat, text, re.IGNORECASE)
    
    return directors


def get_entities(text):
    doc = model(text)
    entities_spacy = [(ent.text, ent.label_) for ent in doc.ents]
    entities_albert = ner.extract(text)
    
    return entities_spacy, entities_albert


def parse_entity(text, label):
    words = text.split(" ")
    entities = [(words[0], f"B-{label}")]
    entities += [(w, f"I-{label}") for w in words[1:]]
    
    return entities


def merge_entities(entities, new_entities):
    for ent in new_entities:
        ent_tmp = (ent[0].strip().strip(string.punctuation), "O")
        if ent_tmp in entities:
            idxs = [i for i, x in enumerate(entities) if x == ent_tmp]
            for i in idxs:
                if ent[1].startswith("I"):
                    if i != 0 and (entities[i-1][1] == ent[1].replace("I-", "B-") or entities[i-1][1] == ent[1]):
                        entities[i] = ent
                else:
                    entities[i] = ent

    return entities


def extract(text):
    words = text.split(" ")
    entities = [(w.strip().strip(string.punctuation), "O") for w in words]
    
    entities_spacy, entities_albert = get_entities(text)
    
    persons = get_persons(entities_spacy, entities_albert)
    actors = []
    directors = []
    characters = []
    for person in persons:
        actor_tmp = is_actor(person)
        director_tmp = is_director(person)
        if actor_tmp and not director_tmp:
            actors.append(person)
        elif not actor_tmp and director_tmp:
            directors.append(person)
        elif not actor_tmp and not director_tmp:
            characters.append(person)
        else:
            amb = disambiguate_person(person, text)
            if amb == DIRECTOR:
                directors.append(person)
            else:
                actors.append(person)
                
    titles = get_titles(entities_albert) + get_titles_from_re(text)
    genres = get_genre(text)
    years = get_year(text)
    rate_avg = get_rate_avg(entities_spacy, text)
    rate = get_rate(text)
    songs, characters = get_songs(text, characters)
    awards = get_awards(text)
    trailers = get_trailers(text)
    
    actors, directors, years_, titles, genres_, df = check_data(actors, directors, years, titles, genres)
    
    genres = genres_
    years += years_
    
    if len(df) == 1:
        titles = get_titles_from_df(text, df.original_title.values[0])
        genre = get_genres_from_df(text, df.genre.values[0])
        actors = list(set(actors+get_actors_from_df(text, df.actors.values[0])))
        directors = get_directors_from_df(text, df.director.values[0])
    
    new_entities = []
    titles_parsed = []
    for title in titles:
        titles_parsed += parse_entity(title.strip(), "TITLE")
    years_parsed = []
    for year in years:
        years_parsed += parse_entity(year.strip(), "YEAR")
    ratings_avg_parsed = []
    for rating_average in rate_avg:
        ratings_avg_parsed += parse_entity(rating_average.strip(), "RATINGS_AVERAGE")
    awards_parsed = []
    for award in awards:
        awards_parsed += parse_entity(award.strip(), "AWARD")
    songs_parsed = []
    for song in songs:
        songs_parsed += parse_entity(song.strip(), "SONG")
    trailers_parsed = []
    for trailer in trailers:
        trailers_parsed += parse_entity(trailer.strip(), "TRAILER")
    rate_parsed = []
    for rating in rate:
        rate_parsed += parse_entity(rating.strip(), "RATING")
    genres_parsed = []
    for genre in genres:
        genres_parsed += parse_entity(genre.strip(), "GENRE")
    actors_parsed = []
    for actor in actors:
        actors_parsed += parse_entity(actor.strip(), "ACTOR")
    directors_parsed = []
    for director in directors:
        directors_parsed += parse_entity(director.strip(), "DIRECTOR")
    characters_parsed = []
    for character in characters:
        characters_parsed += parse_entity(character.strip(), "CHARACTER")
    
    
    new_entities = titles_parsed + years_parsed + ratings_avg_parsed + trailers_parsed + rate_parsed + genres_parsed + directors_parsed + actors_parsed + characters_parsed + songs_parsed + awards_parsed
    entities = merge_entities(entities, new_entities)
                      
    if len(df) == 1:
        return entities, df
    else:    
        return entities, None
