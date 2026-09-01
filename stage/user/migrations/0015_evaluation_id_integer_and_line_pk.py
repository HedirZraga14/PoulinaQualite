import secrets

from django.db import migrations, models

from user.models import generate_random_evaluation_int


def fill_integer_evaluation_ids(apps, schema_editor):
    connection = schema_editor.connection
    used_ids = set()

    def next_id():
        candidate = generate_random_evaluation_int()
        while candidate in used_ids:
            candidate = 100000000 + secrets.randbelow(900000000)
        used_ids.add(candidate)
        return candidate

    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT CAST(id AS NVARCHAR(36)) FROM user_evaluation WHERE id IS NOT NULL")
        legacy_ids = [row[0] for row in cursor.fetchall()]

    with connection.cursor() as cursor:
        for legacy_id in legacy_ids:
            cursor.execute(
                "UPDATE user_evaluation SET id_tmp = %s WHERE CAST(id AS NVARCHAR(36)) = %s",
                [next_id(), legacy_id],
            )

        cursor.execute("SELECT row_id FROM user_evaluation WHERE id IS NULL")
        missing_rows = [row[0] for row in cursor.fetchall()]
        for row_id in missing_rows:
            cursor.execute(
                "UPDATE user_evaluation SET id_tmp = %s WHERE row_id = %s",
                [next_id(), row_id],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0014_row_id_primary_and_business_id_named_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE user_evaluation ADD id_tmp BIGINT NULL;",
                    reverse_sql="ALTER TABLE user_evaluation DROP COLUMN id_tmp;",
                ),
                migrations.RunPython(fill_integer_evaluation_ids, migrations.RunPython.noop),
                migrations.RunSQL(
                    sql="""
IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'user_evaluation_evaluation_id_b919b4b9'
      AND object_id = OBJECT_ID('user_evaluation')
)
    DROP INDEX [user_evaluation_evaluation_id_b919b4b9] ON [user_evaluation];
""",
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE user_evaluation DROP COLUMN id;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql="EXEC sp_rename 'user_evaluation.row_id', 'line_pk', 'COLUMN';",
                    reverse_sql="EXEC sp_rename 'user_evaluation.line_pk', 'row_id', 'COLUMN';",
                ),
                migrations.RunSQL(
                    sql="EXEC sp_rename 'user_evaluation.id_tmp', 'id', 'COLUMN';",
                    reverse_sql="EXEC sp_rename 'user_evaluation.id', 'id_tmp', 'COLUMN';",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE user_evaluation ALTER COLUMN id BIGINT NOT NULL;",
                    reverse_sql="ALTER TABLE user_evaluation ALTER COLUMN id BIGINT NULL;",
                ),
                migrations.RunSQL(
                    sql="CREATE INDEX [user_evaluation_id_bigint_idx] ON [user_evaluation] ([id]);",
                    reverse_sql="DROP INDEX [user_evaluation_id_bigint_idx] ON [user_evaluation];",
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name='evaluation',
                    old_name='row_id',
                    new_name='line_pk',
                ),
                migrations.AlterField(
                    model_name='evaluation',
                    name='id',
                    field=models.PositiveBigIntegerField(db_index=True, default=generate_random_evaluation_int),
                ),
            ],
        ),
    ]
