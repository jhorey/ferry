CREATE USER hiveuser WITH PASSWORD '1hiveuser2';
CREATE DATABASE metastore;
\c metastore
\i /service/sbin/hive-schema.sql
CREATE DATABASE hive_stats;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hiveuser;