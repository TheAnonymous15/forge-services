# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Database Router
====================================
Routes database operations to the correct database.

Current Mode: SINGLE DATABASE
All apps use the same PostgreSQL database (forgeforth_main on Neon).
This preserves ForeignKey relationships and Django ORM features.
"""


class ForgeForthDBRouter:
    """
    Database router for ForgeForth Africa.
    Currently in single-database mode - all apps use 'default'.
    """

    def db_for_read(self, model, **hints):
        """Direct read operations to the default database."""
        return 'default'

    def db_for_write(self, model, **hints):
        """Direct write operations to the default database."""
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow all relations (single database)."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Allow migrations on default database."""
        return db == 'default'


class SingleDBRouter:
    """
    Simple router that uses a single database for all operations.
    This is the default for ForgeForth Africa.
    """

    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'
