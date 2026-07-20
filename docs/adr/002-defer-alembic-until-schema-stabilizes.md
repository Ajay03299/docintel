
## Resolution (Day 9)

Alembic adopted; `create_all` removed. The deferral cost five manual DROP TABLEs
between Day 5 and Day 8 — an acceptable price while the schema changed hourly and
all data was disposable, a deliberate trade rather than an oversight. The trigger
for adoption was the schema stabilising across four tables, plus the first change
(DocumentStatus gaining REJECTED) that required dropping a Postgres ENUM type
rather than just a table.

Note on baselining an existing DB: the first autogenerate produced an EMPTY
migration, because autogenerate diffs models against the LIVE schema and the
tables already existed. A replayable baseline requires generating against an
empty database, so the migration actually contains the CREATE statements.
