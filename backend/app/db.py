"""Supabase client (service key, server side only).

Rule: never update orders without inserting a matching order_changes row in the same
transaction.
"""
