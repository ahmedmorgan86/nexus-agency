#!/bin/bash
# Starts a throwaway local Postgres 16 for tests (port 5433). Needs root to su to postgres.
set -e
D=/tmp/pgdata
BIN=/usr/lib/postgresql/16/bin
if su postgres -c "$BIN/pg_ctl -D $D status" >/dev/null 2>&1; then echo "already running"; exit 0; fi
rm -rf $D; mkdir -p $D; chown postgres $D
su postgres -c "$BIN/initdb -D $D -A trust >/dev/null"
su postgres -c "$BIN/pg_ctl -D $D -o '-p 5433 -k /tmp' -l /tmp/pg.log start >/dev/null"
sleep 3
su postgres -c "psql -h /tmp -p 5433 -c \"create role nexus_owner login superuser\" -c \"create database nexus_test owner nexus_owner\""
echo "postgres ready on 5433"
