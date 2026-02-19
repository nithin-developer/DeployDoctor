from datetime import datetime
from flask import Blueprint, jsonify
from routes.auth import token_required

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/super-admin', methods=['GET'])
@token_required
def user_dashboard():
    """Simple dashboard stats for user."""
    return jsonify({
        'stats': {
            'total_batches': 0,
            'total_trainers': 0,
            'total_students': 0,
            'events_this_month': 0,
            'sessions_today': 0,
            'sessions_completed_today': 0,
            'sessions_upcoming': 0,
            'sessions_past_no_attendance': 0,
            'attendance_completion_rate': 0
        },
        'recent_events': []
    })
