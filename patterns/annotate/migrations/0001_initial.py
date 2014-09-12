# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        migrations.swappable_dependency(settings.WQ_ANNOTATIONTYPE_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('object_id', models.PositiveIntegerField(db_index=True)),
                ('value', models.TextField(blank=True, null=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
                'db_table': 'wq_annotation',
                'swappable': 'WQ_ANNOTATION_MODEL',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AnnotationType',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('contenttype', models.ForeignKey(blank=True, null=True, to='contenttypes.ContentType')),
            ],
            options={
                'db_table': 'wq_annotationtype',
                'swappable': 'WQ_ANNOTATIONTYPE_MODEL',
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='annotationtype',
            unique_together=set([('name',)]),
        ),
        migrations.AddField(
            model_name='annotation',
            name='type',
            field=models.ForeignKey(to=settings.WQ_ANNOTATIONTYPE_MODEL),
            preserve_default=True,
        ),
    ]
