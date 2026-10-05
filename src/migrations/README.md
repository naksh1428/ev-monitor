# Legacy migrations (superseded by Alembic)

These hand-written `.sql` files predate Alembic. They exist only as a
historical record for databases that were manually upgraded with them before
`src/alembic/` was introduced (see `src/alembic/versions/..._baseline_schema.py`,
which captures the schema these files produce).

Do not add new files here. New schema changes go through Alembic:

```bash
cd src
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```
