import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0013_replace_evaluation_group_with_evaluation_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
IF COL_LENGTH('user_evaluation', 'row_id') IS NULL AND COL_LENGTH('user_evaluation', 'id') IS NOT NULL
    EXEC sp_rename 'user_evaluation.id', 'row_id', 'COLUMN';
IF COL_LENGTH('user_evaluation', 'evaluation_id') IS NOT NULL AND COL_LENGTH('user_evaluation', 'id') IS NULL
    EXEC sp_rename 'user_evaluation.evaluation_id', 'id', 'COLUMN';
""",
                    reverse_sql="""
IF COL_LENGTH('user_evaluation', 'evaluation_id') IS NULL AND COL_LENGTH('user_evaluation', 'id') IS NOT NULL
    EXEC sp_rename 'user_evaluation.id', 'evaluation_id', 'COLUMN';
IF COL_LENGTH('user_evaluation', 'id') IS NULL AND COL_LENGTH('user_evaluation', 'row_id') IS NOT NULL
    EXEC sp_rename 'user_evaluation.row_id', 'id', 'COLUMN';
""",
                ),
            ],
            state_operations=[
                migrations.DeleteModel(name='Evaluation'),
                migrations.CreateModel(
                    name='Evaluation',
                    fields=[
                        ('row_id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                        ('axe_evaluation', models.TextField(blank=True)),
                        ('criteres', models.TextField(blank=True)),
                        ('note', models.CharField(blank=True, max_length=50)),
                        ('ponderation', models.CharField(blank=True, max_length=50)),
                        ('observations', models.TextField(blank=True)),
                        ('moy_ponderation', models.CharField(blank=True, max_length=50)),
                        ('tx_conformite', models.CharField(blank=True, max_length=50)),
                        ('code', models.CharField(blank=True, max_length=50)),
                        ('filiale_name', models.CharField(blank=True, max_length=150)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('date', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='evaluations', to='user.datedim')),
                        ('filiale', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='evaluations', to='user.branch')),
                        ('laboratoire', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='evaluations', to='user.laboratoire')),
                        ('user', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='evaluations', to='user.user')),
                    ],
                    options={
                        'ordering': ['-created_at'],
                    },
                ),
            ],
        ),
    ]
