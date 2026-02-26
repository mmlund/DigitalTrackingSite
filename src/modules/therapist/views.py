"""
Therapist view routes — serves HTML pages for schedule and ratings.
"""

from datetime import datetime, timedelta
from flask import render_template
from . import therapist_bp


@therapist_bp.route('/', methods=['GET'])
def therapist_home():
    """Redirect to schedule page."""
    return render_template("therapist/schedule.html")


@therapist_bp.route('/schedule-view', methods=['GET'])
def schedule_view():
    """Render the schedule table page."""
    return render_template("therapist/schedule.html")


@therapist_bp.route('/ratings-view', methods=['GET'])
def ratings_view():
    """Render the ratings input page."""
    return render_template("therapist/ratings.html")
