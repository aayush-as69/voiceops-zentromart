from src.policy_rules import escalation_reason, refund_overdue

def test_high_value_damage_routes_to_priority_team():
    order={'damage_sku':'ELE-0001','items':[{'sku':'ELE-0001','unit_price_inr':12001,'qty':1}]}
    assert escalation_reason('The item arrived damaged and I want replacement.',order)=='high_value_damage'

def test_compensation_voucher_is_not_silently_promised_or_auto_ticketed():
    assert escalation_reason('Order was late, give me a 300 rupee voucher.',{'items':[]}) is None

def test_refund_overdue_uses_fixed_reference_date():
    order={'return_refund_initiated_on':'2026-09-01','return_refund_method':'UPI','return_refund_completed_on':''}
    assert refund_overdue(order,None)
