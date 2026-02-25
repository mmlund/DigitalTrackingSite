"""
Campaign management blueprint.

Serves campaign list/detail HTML pages and provides JSON API endpoints
for CRUD, link generation, spend tracking, and asset management.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, Response
from src.campaign_service import (
    create_campaign,
    get_campaign,
    list_campaigns,
    update_campaign,
    set_campaign_status,
    duplicate_campaign,
    generate_campaign_link,
    list_campaign_links,
    upsert_spend,
    list_spend,
    save_asset,
    list_assets,
    get_asset_file,
    VALID_CHANNELS,
    VALID_STATUSES,
    VALID_SITES,
)
from src.config import ALLOWED_ASSET_EXTENSIONS
import logging

logger = logging.getLogger(__name__)

campaigns_bp = Blueprint('campaigns', __name__)


# ── Page Routes ──────────────────────────────────────────────────────

@campaigns_bp.route('/campaigns')
def campaign_list_page():
    """Serve the Campaign List (front page)."""
    return render_template(
        'campaigns.html',
        channels=sorted(VALID_CHANNELS),
        statuses=sorted(VALID_STATUSES),
        sites=sorted(VALID_SITES),
    )


@campaigns_bp.route('/campaigns/new')
def campaign_new_page():
    """Serve Campaign Detail page in create mode."""
    return render_template(
        'campaign_detail.html',
        campaign=None,
        mode='create',
        channels=sorted(VALID_CHANNELS),
        statuses=sorted(VALID_STATUSES),
        sites=sorted(VALID_SITES),
    )


@campaigns_bp.route('/campaigns/<campaign_id>')
def campaign_detail_page(campaign_id):
    """Serve Campaign Detail page in edit mode."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('campaigns.campaign_list_page'))
    return render_template(
        'campaign_detail.html',
        campaign=campaign,
        mode='edit',
        channels=sorted(VALID_CHANNELS),
        statuses=sorted(VALID_STATUSES),
        sites=sorted(VALID_SITES),
    )


# ── Campaign CRUD API ────────────────────────────────────────────────

@campaigns_bp.route('/api/campaigns', methods=['GET'])
def api_list_campaigns():
    """List campaigns with optional filters."""
    filters = {}
    if request.args.get('site_id'):
        filters['site_id'] = request.args['site_id']
    if request.args.get('channel'):
        filters['channel'] = request.args['channel']
    if request.args.get('status'):
        filters['status'] = request.args['status']

    try:
        campaigns = list_campaigns(filters=filters)
        # Attach link count for each campaign
        for c in campaigns:
            links = list_campaign_links(c['campaign_id'])
            c['link_count'] = len(links)
            # Attach latest spend
            spend_entries = list_spend(c['campaign_id'])
            c['latest_spend'] = spend_entries[0] if spend_entries else None

        return jsonify({'success': True, 'campaigns': campaigns})
    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/campaigns', methods=['POST'])
def api_create_campaign():
    """Create a new campaign."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    try:
        campaign = create_campaign(data)
        return jsonify({'success': True, 'campaign': campaign}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>', methods=['GET'])
def api_get_campaign(campaign_id):
    """Get a single campaign."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({'success': False, 'error': 'Campaign not found'}), 404
    return jsonify({'success': True, 'campaign': campaign})


@campaigns_bp.route('/api/campaigns/<campaign_id>', methods=['PUT'])
def api_update_campaign(campaign_id):
    """Update a campaign."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    try:
        campaign = update_campaign(campaign_id, data)
        return jsonify({'success': True, 'campaign': campaign})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating campaign: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/status', methods=['PATCH'])
def api_set_status(campaign_id):
    """Quick-set campaign status."""
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'success': False, 'error': 'status field is required'}), 400

    try:
        campaign = set_campaign_status(campaign_id, data['status'])
        return jsonify({'success': True, 'campaign': campaign})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error setting status: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/duplicate', methods=['POST'])
def api_duplicate_campaign(campaign_id):
    """Duplicate a campaign."""
    try:
        campaign = duplicate_campaign(campaign_id)
        return jsonify({'success': True, 'campaign': campaign}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error duplicating campaign: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ── Campaign Links API ───────────────────────────────────────────────

@campaigns_bp.route('/api/campaigns/<campaign_id>/links', methods=['POST'])
def api_generate_link(campaign_id):
    """Generate and save a tracking link for a campaign."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    try:
        link = generate_campaign_link(campaign_id, data)
        return jsonify({'success': True, 'link': link}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating link: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/links', methods=['GET'])
def api_list_links(campaign_id):
    """List links for a campaign."""
    try:
        links = list_campaign_links(campaign_id)
        return jsonify({'success': True, 'links': links})
    except Exception as e:
        logger.error(f"Error listing links: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Campaign Spend API ───────────────────────────────────────────────

@campaigns_bp.route('/api/campaigns/<campaign_id>/spend', methods=['POST'])
def api_upsert_spend(campaign_id):
    """Upsert monthly spend for a campaign."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    month = data.get('month')
    amount = data.get('amount')
    if not month or amount is None:
        return jsonify({'success': False, 'error': 'month and amount are required'}), 400

    try:
        spend = upsert_spend(
            campaign_id,
            month=month,
            amount=float(amount),
            currency=data.get('currency', 'USD'),
            source=data.get('source', 'manual'),
            note=data.get('note'),
        )
        return jsonify({'success': True, 'spend': spend}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error upserting spend: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/spend', methods=['GET'])
def api_list_spend(campaign_id):
    """List spend entries for a campaign."""
    try:
        entries = list_spend(campaign_id)
        return jsonify({'success': True, 'spend': entries})
    except Exception as e:
        logger.error(f"Error listing spend: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Campaign Assets API ──────────────────────────────────────────────

@campaigns_bp.route('/api/campaigns/<campaign_id>/assets', methods=['POST'])
def api_upload_asset(campaign_id):
    """Upload an asset for a campaign (multipart form or JSON text)."""
    try:
        asset_type = request.form.get('asset_type') or (request.get_json() or {}).get('asset_type', 'creative_notes')

        # Check for file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in ALLOWED_ASSET_EXTENSIONS:
                    return jsonify({
                        'success': False,
                        'error': f'File type .{ext} not allowed. Allowed: {", ".join(sorted(ALLOWED_ASSET_EXTENSIONS))}'
                    }), 400

                asset = save_asset(
                    campaign_id,
                    asset_type=asset_type,
                    filename=file.filename,
                    file_data=file.read(),
                    content_type=file.content_type or 'application/octet-stream',
                )
                return jsonify({'success': True, 'asset': asset}), 201

        # Text-based asset
        data = request.get_json() or {}
        raw_text = data.get('raw_text', '')
        filename = data.get('filename')

        asset = save_asset(
            campaign_id,
            asset_type=asset_type,
            filename=filename,
            raw_text=raw_text,
            content_type='text/plain',
        )
        return jsonify({'success': True, 'asset': asset}), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error uploading asset: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/assets', methods=['GET'])
def api_list_assets(campaign_id):
    """List asset metadata for a campaign."""
    try:
        assets = list_assets(campaign_id)
        return jsonify({'success': True, 'assets': assets})
    except Exception as e:
        logger.error(f"Error listing assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaigns_bp.route('/api/campaigns/<campaign_id>/assets/<asset_id>/download', methods=['GET'])
def api_download_asset(campaign_id, asset_id):
    """Download an asset file from GridFS."""
    result = get_asset_file(asset_id)
    if not result:
        return jsonify({'success': False, 'error': 'Asset file not found'}), 404

    file_data, filename, content_type = result
    return Response(
        file_data,
        mimetype=content_type,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
