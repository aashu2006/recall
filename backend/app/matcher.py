"""Decide whether an extracted item is a new order or an update, and to which order.

Returns the target order (or None) and a confidence. Low confidence or more than one
candidate means the item goes to pending_confirmations, never straight to orders.
"""
