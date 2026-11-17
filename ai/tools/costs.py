from decimal import Decimal


def allocate(line, member_ids):
    users = sorted(member_ids)
    owner = line.get("owner_id")
    unit = line.get("unit_price_krw")
    amount = None if unit is None else int(Decimal(str(unit)) * Decimal(str(line["quantity"])))
    if line["scope"] == "per_person":
        return {u: amount if owner in (None, u) else 0 for u in users}
    return {u: None if amount is None else amount // len(users) + (i < amount % len(users))
            for i, u in enumerate(users)}


def calculate_costs(lines, member_ids, budget_by_user):
    shares = [allocate(line, member_ids) for line in lines]
    per_user = {u: sum(s[u] for s in shares) for u in member_ids}
    paid = {u: sum(s[u] for line, s in zip(lines, shares) if line["paid"]) for u in member_ids}
    normalized = [dict(line, subtotal_krw=sum(share.values())) for line, share in zip(lines, shares)]
    total = sum(per_user.values())
    return dict(lines=normalized, known_total_krw=total, total_krw=total,
                per_person_krw=per_user, paid_krw=sum(paid.values()), paid_by_user_krw=paid,
                remaining_budget_krw={u: budget_by_user[u] - paid[u] for u in member_ids},
                planned_balance_krw={u: budget_by_user[u] - per_user[u] for u in member_ids},
                unknown_line_count=0, estimated_line_count=0)
