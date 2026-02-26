"""
Reconciliation service — Phase 3B Hardening

Interim solution for ensuring cancellation coverage.
"""

import logging

logger = logging.getLogger(__name__)

def run_reconciliation():
    """
    Periodic reconciliation job (interim stub).
    
    Future implementation:
    - Query EA for appointments with status=cancelled.
    - Emit booking_cancelled events for missing appointment_ids.
    """
    logger.info("Reconciliation job triggered (currently not implemented — EA API integration pending)")
    return {"status": "not_implemented", "message": "EA API integration pending"}
