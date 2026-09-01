# Migration manuelle — refactor du schéma en flocons
# Ajout des dimensions Laboratoire, DateDim et des FKs sur Evaluation
# + champs calculés moy_ponderation et tx_conformite

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_evaluation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) Création de Dim_laboratoire
        migrations.CreateModel(
            name='Laboratoire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
            ],
            options={
                'verbose_name': 'Laboratoire',
                'verbose_name_plural': 'Laboratoires',
                'ordering': ['name'],
            },
        ),

        # 2) Création de Dim_date
        migrations.CreateModel(
            name='DateDim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mois', models.CharField(max_length=50)),
                ('trimestre', models.CharField(blank=True, max_length=20)),
                ('annee', models.CharField(max_length=20)),
            ],
            options={
                'verbose_name': 'Date (dimension)',
                'verbose_name_plural': 'Dates (dimension)',
                'ordering': ['annee', 'mois'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='datedim',
            unique_together={('mois', 'annee')},
        ),

        # 3) Ajout des FKs vers les dimensions sur la table de faits Evaluation
        migrations.AddField(
            model_name='evaluation',
            name='date',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='evaluations',
                to='user.datedim',
            ),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='evaluations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='laboratoire',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='evaluations',
                to='user.laboratoire',
            ),
        ),

        # 4) Ajout des champs dénormalisés et des indicateurs calculés
        migrations.AddField(
            model_name='evaluation',
            name='filiale_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='moy_ponderation',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='tx_conformite',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
