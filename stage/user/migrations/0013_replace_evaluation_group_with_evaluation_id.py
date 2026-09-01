from django.db import migrations, models
import uuid


def copy_group_id_to_evaluation_id(apps, schema_editor):
    Evaluation = apps.get_model('user', 'Evaluation')
    for evaluation in Evaluation.objects.all().iterator(chunk_size=1000):
        value = getattr(evaluation, 'evaluation_group_id', None) or uuid.uuid4()
        Evaluation.objects.filter(pk=evaluation.pk).update(evaluation_id=value)


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0012_evaluation_group_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='evaluation_id',
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(copy_group_id_to_evaluation_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='evaluation',
            name='evaluation_id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
        ),
        migrations.RemoveField(
            model_name='evaluation',
            name='evaluation_group_id',
        ),
    ]
