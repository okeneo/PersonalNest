# Generated by Django 5.0 on 2023-12-25 03:55

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        choices=[("Technology", "Technology"), ("Life", "Life")],
                        max_length=20,
                        unique=True,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Categories",
            },
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        choices=[
                            ("Software Engineering", "Software Engineering"),
                            ("Django", "Django"),
                            ("Grit", "Grit"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255, unique=True)),
                ("subtitle", models.CharField(blank=True, max_length=255)),
                ("slug", models.SlugField(blank=True, max_length=255, unique=True)),
                ("body", models.TextField()),
                ("meta_description", models.CharField(blank=True, max_length=150)),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("date_modified", models.DateTimeField(auto_now=True)),
                ("publish_date", models.DateTimeField(blank=True, null=True)),
                ("published", models.BooleanField(default=False)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="post.category"
                    ),
                ),
                ("tags", models.ManyToManyField(blank=True, to="post.tag")),
            ],
            options={
                "ordering": ["-publish_date"],
            },
        ),
    ]
