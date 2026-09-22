# Neon migration notes

Neon’s official Python guide recommends Psycopg 3 for new synchronous Python applications and a `DATABASE_URL` connection string with `sslmode=require` and `channel_binding=require`: <https://neon.com/docs/guides/python>.

Neon’s workflow primer documents isolated branches for migration testing and CI, with each branch having its own connection string: <https://neon.com/docs/get-started/workflow-primer>.

The GreyAI Neon project is `GreyAI` (project id `broad-dawn-51952268`) with default branch `br-ancient-band-av3egtlc`; the connection string is intentionally not stored in this file or repository.

The Fly app already uses `DB_PATH=/data/telescout.db` on the persistent `telescout_data` volume. The application bootstrap therefore reads that SQLite file once when `DATABASE_URL` is enabled, copies schema/data into Postgres, and records completion in `_greyai_sqlite_bootstrap`.
