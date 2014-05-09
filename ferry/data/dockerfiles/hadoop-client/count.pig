/**
 * Simple Pig example
 * Counts the number of movies rated grouped by user id. 
 **/

movies = LOAD '/service/data/movielens/u.data' USING PigStorage() AS (userid:int, movieid:int, rating:int, unixtime:chararray);
g = GROUP movies BY userid;
c = FOREACH g GENERATE COUNT($1);