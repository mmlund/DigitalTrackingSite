"""
Reports blueprint — Phase 2B

Four JSON-only endpoints for UI-ready rollups and LLM report packets.
"""

from flask import Blueprint, request, jsonify
from src.report_service import (
    build_overview_report,
    build_funnel_report,
    build_value_report,
    build_campaign_packet,
)
import logging

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/api/reports/overview', methods=['GET'])
def overview_report():
    """
    GET /api/reports/overview?days=90&rollup=week

    Returns KPI tiles + weekly time series for all active outreach.
    """
    try:
        days = int(request.args.get('days', 90))
        rollup = request.args.get('rollup', 'week')
        result = build_overview_report(days=days, rollup=rollup)
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        logger.error(f"Error in overview report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route('/api/reports/funnels', methods=['GET'])
def funnels_report():
    """
    GET /api/reports/funnels?days=90&scope=active_only&group_by=campaign

    Returns array of funnel objects, one per active campaign.
    """
    try:
        days = int(request.args.get('days', 90))
        scope = request.args.get('scope', 'active_only')
        group_by = request.args.get('group_by', 'campaign')
        result = build_funnel_report(days=days, scope=scope, group_by=group_by)
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        logger.error(f"Error in funnels report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route('/api/reports/value', methods=['GET'])
def value_report():
    """
    GET /api/reports/value?days=90

    Returns long-term/value analysis: ratings, LTV, new vs repeat,
    loss points, touchpoints.
    """
    try:
        days = int(request.args.get('days', 90))
        result = build_value_report(days=days)
        return jsonify({"success": True, **result}), 200
    except Exception as e:
        logger.error(f"Error in value report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route('/api/reports/campaign/<campaign_id>', methods=['GET'])
def campaign_packet(campaign_id):
    """
    GET /api/reports/campaign/<campaign_id>?days=90

    Returns per-campaign LLM-ready report packet.
    """
    try:
        days = int(request.args.get('days', 90))
        result = build_campaign_packet(campaign_id=campaign_id, days=days)
        return jsonify({"success": True, "packet": result}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error in campaign packet: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
