import uuid

from django.db import migrations, models


def populate_evaluation_group_ids(apps, schema_editor):
    Evaluation = apps.get_model('user', 'Evaluation')
    grouped_ids = {}

    for evaluation in Evaluation.objects.all().order_by('created_at', 'id').iterator(chunk_size=1000):
        filiale_name = (evaluation.filiale_name or '').strip().lower()
        key = (
            evaluation.date_id or 0,
            evaluation.filiale_id or 0,
            filiale_name,
            evaluation.laboratoire_id or 0,
            evaluation.user_id or 0,
        )
        group_id = grouped_ids.get(key)
        if group_id is None:
            group_id = uuid.uuid4()
            grouped_ids[key] = group_id
        Evaluation.objects.filter(pk=evaluation.pk).update(evaluation_group_id=group_id)


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0011_user_sector'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='evaluation_group_id',
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_evaluation_group_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='evaluation',
            name='evaluation_group_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
        ),
    ]
