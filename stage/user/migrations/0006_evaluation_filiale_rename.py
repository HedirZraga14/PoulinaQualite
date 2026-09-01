# Migration manuelle — correction du nom de colonne Evaluation
# Renomme branch_id -> filiale_id et supprime l'ancien champ filiale (char)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0005_snowflake_schema_refactor'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='evaluation',
            name='filiale',
        ),
        migrations.RenameField(
            model_name='evaluation',
            old_name='branch',
            new_name='filiale',
        ),
    ]
