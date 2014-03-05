CREATE TABLE  movielens_users_text (
       userid INT,
       movieid INT,
       rating INT,
       unixtime STRING
) 
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE;

CREATE TABLE movielens_users (
       userid INT,
       movieid INT,
       rating INT,
       unixtime STRING
) STORED AS RCFILE;

LOAD DATA INPATH '/service/data/movielens/u.data'
OVERWRITE INTO TABLE movielens_users_text;

INSERT INTO TABLE movielens_users SELECT * FROM movielens_users_text;
DROP TABLE movielens_users_text;