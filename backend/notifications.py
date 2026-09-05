"""
backend/notifications.py
Internal & Demo Notification / Email System for Control Tower (PS08).
Manages email templates, composition, and sent log audit trails.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection

TEMPLATES = {
    "supplier_disruption_notice": {
        "title": "Supplier Disruption Notice",
        "subject": "URGENT: Disruption Notice Received for Shipment {shipment_id}",
        "body": "Dear Operations Team,\n\nSupplier {supplier_name} has issued an operational disruption notice regarding shipment {shipment_id} containing {product_name}.\nExpected delay: {delay_days} days.\nReason: {reason}.\n\nPlease review Impact Graph and initiate mitigation plan."
    },
    "customer_delay_notification": {
        "title": "Customer Delay Notification",
        "subject": "Delivery Schedule Advisory — Order {order_id}",
        "body": "Dear Procurement Team at {company_name},\n\nWe are writing to advise that delivery of Order {order_id} ({product_name}) initially scheduled for {original_date} is currently affected by upstream transport delays.\n\nRevised Estimated Delivery: {new_date}.\nOur operations team has initiated expedited carrier routing to minimize delay."
    },
    "shipment_status_update": {
        "title": "Shipment Status Update",
        "subject": "Status Update: Shipment {shipment_id} — {status}",
        "body": "Control Tower Alert:\n\nShipment {shipment_id} (Origin: {origin}, Destination: {destination}) status has changed to {status}.\nQuantity: {quantity} units of {product_name}."
    },
    "management_escalation": {
        "title": "Escalation to Management",
        "subject": "MANAGEMENT ESCALATION: Disruption Incident {disruption_id}",
        "body": "Attention Executive Management,\n\nDisruption incident {disruption_id} requires human intervention.\nReason: {reason}.\nSeverity: {severity}.\n\nPlease review Evidence Dossier and issue decision."
    }
}

def create_notification(sender: str, recipient: str, subject: str, message: str, reason: str, related_shipment_id: Optional[str] = None, related_order_id: Optional[str] = None, status: str = "SENT") -> Dict[str, Any]:
    conn = get_db_connection()
    c = conn.cursor()
    notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
    INSERT INTO notifications (id, sender, recipient, subject, message, reason, related_shipment_id, related_order_id, status, sent_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (notif_id, sender, recipient, subject, message, reason, related_shipment_id, related_order_id, status, sent_at))
    conn.commit()

    c.execute("SELECT * FROM notifications WHERE id = ?", (notif_id,))
    row = c.execute("SELECT * FROM notifications WHERE id = ?", (notif_id,)).fetchone()
    conn.close()
    return dict(row)

def get_all_notifications() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM notifications ORDER BY sent_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_templates() -> Dict[str, Any]:
    return TEMPLATES
