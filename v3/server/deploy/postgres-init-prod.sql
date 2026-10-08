-- 本番の PostgreSQL に置くデータベース。正本（v3）は POSTGRES_DB で作られる。
-- 1つのサーバーにまとめるのは、控え（backup.sh の pg_basebackup）を全部同じ時点で1回で取るため。
CREATE DATABASE openfga;
CREATE DATABASE keycloak;
CREATE DATABASE temporal;
CREATE DATABASE temporal_visibility;
