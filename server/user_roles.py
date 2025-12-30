#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
user_roles.py

Family member configuration and role management for speedmathsgames.com.
Maps Google emails to user profiles with roles and permissions.
"""

from typing import Dict, Optional, List

# ============================================================================
# FAMILY MEMBER CONFIGURATION
# ============================================================================

FAMILY_MEMBERS = {
    # Admin (Parent)
    'k12arvind@gmail.com': {
        'user_id': 'arvind',
        'name': 'Arvind',
        'role': 'admin',
        'can_view_all_users': True,
        'can_edit_settings': True,
    },
    
    # Wife
    'deepay2019@gmail.com': {
        'user_id': 'deepa',
        'name': 'Deepa',
        'role': 'parent',
        'can_view_all_users': True,  # Parents can see children's data
        'can_edit_settings': True,
    },
    
    # Daughter 1
    '20saanvi12@gmail.com': {
        'user_id': 'saanvi',
        'name': 'Saanvi',
        'role': 'child',
        'can_view_all_users': False,
        'can_edit_settings': True,  # Can edit own math settings
    },
    
    # Daughter 2
    '20navya12@gmail.com': {
        'user_id': 'navya',
        'name': 'Navya',
        'role': 'child',
        'can_view_all_users': False,
        'can_edit_settings': True,  # Can edit own math settings
    },
}

# List of child user_ids (for admin dashboard)
CHILD_USER_IDS = ['saanvi', 'navya']

# List of all user_ids
ALL_USER_IDS = ['arvind', 'deepa', 'saanvi', 'navya']


def get_user_profile(email: str) -> Optional[Dict]:
    """
    Get user profile from email address.
    Returns None if email is not a registered family member.
    """
    return FAMILY_MEMBERS.get(email.lower())


def get_user_id_from_email(email: str) -> str:
    """
    Get user_id from email. Returns email prefix if not a registered member.
    """
    profile = get_user_profile(email)
    if profile:
        return profile['user_id']
    # For unregistered users, use email prefix as user_id
    return email.split('@')[0].lower().replace('.', '_')


def get_user_role(email: str) -> str:
    """Get user role from email. Defaults to 'guest' for unregistered."""
    profile = get_user_profile(email)
    return profile['role'] if profile else 'guest'


def can_view_all_users(email: str) -> bool:
    """Check if user can view all family members' data."""
    profile = get_user_profile(email)
    return profile.get('can_view_all_users', False) if profile else False


def can_edit_settings(email: str) -> bool:
    """Check if user can edit settings (topics, difficulty, etc.)."""
    profile = get_user_profile(email)
    return profile.get('can_edit_settings', False) if profile else False


def is_admin(email: str) -> bool:
    """Check if user is an admin."""
    return get_user_role(email) == 'admin'


def is_parent(email: str) -> bool:
    """Check if user is a parent (admin or parent role)."""
    role = get_user_role(email)
    return role in ['admin', 'parent']


def get_viewable_user_ids(email: str) -> List[str]:
    """
    Get list of user_ids this user can view.
    - Admin/Parent: All family members
    - Child: Only themselves
    """
    if can_view_all_users(email):
        return ALL_USER_IDS
    
    profile = get_user_profile(email)
    if profile:
        return [profile['user_id']]
    
    return [get_user_id_from_email(email)]


def get_all_family_members() -> Dict:
    """Get all family member profiles."""
    return FAMILY_MEMBERS.copy()


def get_children() -> List[Dict]:
    """Get list of children profiles for admin dashboard."""
    return [
        {**profile, 'email': email}
        for email, profile in FAMILY_MEMBERS.items()
        if profile['role'] == 'child'
    ]

