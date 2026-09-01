from django.db import migrations


def migrate_legacy_laboratoire_column(apps, schema_editor):
    Evaluation = apps.get_model('user', 'Evaluation')
    Laboratoire = apps.get_model('user', 'Laboratoire')

    connection = schema_editor.connection
    table_name = Evaluation._meta.db_table

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

        # Older databases can still contain the original text column `laboratoire`.
        # Backfill the FK from that text before removing the orphan column.
        if 'laboratoire' in columns:
            quoted_table = schema_editor.quote_name(table_name)
            quoted_column = schema_editor.quote_name('laboratoire')

            cursor.execute(
                f"""
                SELECT id, {quoted_column}
                FROM {quoted_table}
                WHERE laboratoire_id IS NULL
                  AND {quoted_column} IS NOT NULL
                  AND LTRIM(RTRIM({quoted_column})) <> ''
                """
            )
            legacy_rows = cursor.fetchall()

            for evaluation_id, raw_name in legacy_rows:
                clean_name = str(raw_name or '').strip()
                if not clean_name:
                    continue

                laboratoire = Laboratoire.objects.filter(name__iexact=clean_name).first()
                if laboratoire is None:
                    laboratoire = Laboratoire.objects.create(name=clean_name)

                Evaluation.objects.filter(pk=evaluation_id).update(laboratoire_id=laboratoire.pk)

            schema_editor.execute(
                f'ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}'
            )


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0009_user_avatar'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_laboratoire_column, migrations.RunPython.noop),
    ]
