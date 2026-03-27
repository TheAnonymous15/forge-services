# -*- coding: utf-8 -*-
"""
Management command: migrate_blogs_to_db

Migrates all hardcoded blog articles from blog_data.py into the database.
Assigns unique blog_id and proper slugs.
Safe to run multiple times - skips articles that already exist by slug.

Usage:
    python manage.py migrate_blogs_to_db
    python manage.py migrate_blogs_to_db --force   # re-import even if slug exists
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from datetime import datetime

from website.blog_data import ARTICLES
from website.models import BlogPost


# Map hardcoded category labels → model category keys
CATEGORY_MAP = {
    'Insights':      'insights',
    'Platform':      'news',
    'Mission':       'africa',
    'Technology':    'tech',
    'Stories':       'stories',
    'For Employers': 'insights',
    'Career Tips':   'tips',
    'Skills':        'skills',
}


def body_to_content(body: list) -> str:
    """
    Convert a list of (text, type) tuples back to a readable markdown-lite string
    so that parse_content_to_body() in views.py will reconstruct it correctly.

    - ('Heading', 'h2') → '## Heading'
    - ('paragraph', None) → 'paragraph'
    """
    lines = []
    for text, btype in body:
        if btype == 'h2':
            lines.append(f"## {text}")
        else:
            lines.append(text)
        lines.append('')  # blank line between blocks
    return '\n'.join(lines).strip()


def parse_date(date_str: str):
    """Parse 'Mar 3, 2026' style dates to datetime."""
    try:
        return timezone.make_aware(datetime.strptime(date_str.strip(), '%b %d, %Y'))
    except (ValueError, AttributeError):
        try:
            return timezone.make_aware(datetime.strptime(date_str.strip(), '%b. %d, %Y'))
        except Exception:
            return timezone.now()


class Command(BaseCommand):
    help = 'Migrate hardcoded blog articles from blog_data.py into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-import articles even if slug already exists in the DB',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without saving anything',
        )

    def handle(self, *args, **options):
        force = options['force']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN mode - nothing will be saved\n'))

        total = len(ARTICLES)
        imported = 0
        skipped = 0
        errors = 0

        self.stdout.write(f'Found {total} hardcoded articles to migrate...\n')

        for slug, article in ARTICLES.items():
            title = article.get('title', 'Untitled')
            self.stdout.write(f'  [{slug}] "{title[:55]}..."')

            # Check if already exists
            if not force and BlogPost.objects.filter(slug=slug).exists():
                self.stdout.write(self.style.WARNING(f'    SKIP - slug already in DB\n'))
                skipped += 1
                continue

            # Build content string from body tuples
            body = article.get('body', [])
            content = body_to_content(body)
            if not content:
                content = article.get('excerpt', '')

            # Map category
            raw_category = article.get('category', 'Insights')
            category = CATEGORY_MAP.get(raw_category, 'insights')

            # Parse publish date
            published_at = parse_date(article.get('date', ''))

            # Author info
            author_name = article.get('author', 'ForgeForth Team')
            author_initials = article.get('author_initials', 'FF')

            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f'    WOULD IMPORT → category={category}, '
                    f'published={published_at.strftime("%Y-%m-%d")}, '
                    f'content_lines={len(content.splitlines())}\n'
                ))
                imported += 1
                continue

            try:
                # Delete old version if force-reimporting
                if force:
                    BlogPost.objects.filter(slug=slug).delete()

                post = BlogPost(
                    slug=slug,
                    title=title,
                    excerpt=article.get('excerpt', ''),
                    content=content,
                    category=category,
                    tags=article.get('tags', []),
                    author_name=author_name,
                    author_bio='',
                    status='published',
                    is_featured=article.get('featured', False),
                    published_at=published_at,
                )
                post.save()

                self.stdout.write(self.style.SUCCESS(
                    f'    OK → blog_id={post.blog_id}, slug={post.slug}, '
                    f'share_url={post.share_url}\n'
                ))
                imported += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ERROR: {e}\n'))
                errors += 1

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'  Total articles: {total}')
        self.stdout.write(f'  Imported:       {imported}')
        self.stdout.write(f'  Skipped:        {skipped}')
        self.stdout.write(f'  Errors:         {errors}')
        if dry_run:
            self.stdout.write(self.style.WARNING('\n  DRY RUN - nothing was saved'))
        else:
            self.stdout.write(self.style.SUCCESS('\n  Migration complete!'))
        self.stdout.write('=' * 60)

