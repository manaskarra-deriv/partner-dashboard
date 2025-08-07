"""
Shared utilities and constants used across all modules
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Tier movement scores - shared across all modules
TIER_MOVEMENT_SCORES = {
    ('Bronze', 'Silver'): 1,
    ('Silver', 'Gold'): 2,
    ('Gold', 'Platinum'): 5,
    ('Platinum', 'Gold'): -5,
    ('Gold', 'Silver'): -2,
    ('Silver', 'Bronze'): -1,
    # Additional movements for completeness
    ('Bronze', 'Gold'): 3,  # Bronze to Gold (Bronze->Silver + Silver->Gold = 1+2)
    ('Silver', 'Platinum'): 7,  # Silver to Platinum (Silver->Gold + Gold->Platinum = 2+5)
    ('Bronze', 'Platinum'): 8,  # Bronze to Platinum (Bronze->Silver + Silver->Gold + Gold->Platinum = 1+2+5)
    ('Platinum', 'Silver'): -7,  # Platinum to Silver (Platinum->Gold + Gold->Silver = -5-2)
    ('Gold', 'Bronze'): -3,  # Gold to Bronze (Gold->Silver + Silver->Bronze = -2-1)
    ('Platinum', 'Bronze'): -8,  # Platinum to Bronze (Platinum->Gold + Gold->Silver + Silver->Bronze = -5-2-1)
    # Movements to/from Inactive tier
    ('Inactive', 'Bronze'): 1,
    ('Inactive', 'Silver'): 3,
    ('Inactive', 'Gold'): 6,
    ('Inactive', 'Platinum'): 11,
    ('Bronze', 'Inactive'): -1,
    ('Silver', 'Inactive'): -3,
    ('Gold', 'Inactive'): -6,
    ('Platinum', 'Inactive'): -11,
    # Same-tier movements (no change)
    ('Bronze', 'Bronze'): 0,
    ('Silver', 'Silver'): 0,
    ('Gold', 'Gold'): 0,
    ('Platinum', 'Platinum'): 0,
    ('Inactive', 'Inactive'): 0,
}

def get_tier_movement_score(from_tier, to_tier):
    """Get the score for a tier movement"""
    return TIER_MOVEMENT_SCORES.get((from_tier, to_tier), 0)

def validate_partner_data(partner_data):
    """Validate that partner data is available"""
    if partner_data is None:
        return False, {'error': 'No data available'}, 400
    return True, None, None