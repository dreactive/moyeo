from decimal import Decimal


def complete_sum(values):
    values = list(values)
    return None if None in values else sum(values)


def balance(budget, amount):
    return None if budget is None or amount is None else budget - amount


def allocate(line, member_ids):
    users = sorted(member_ids)
    owner = line.get("owner_id")
    unit = line.get("unit_price_krw")
    amount = None if unit is None else Decimal(str(unit)) * Decimal(str(line["quantity"]))
    if amount is not None:
        if amount != amount.to_integral_value():
            raise ValueError("User quantity produces a fractional KRW amount")
        amount = int(amount)
    if line["scope"] == "per_person":
        return {u: amount if owner in (None, u) else 0 for u in users}
    return {u: None if amount is None else amount // len(users) + (i < amount % len(users))
            for i, u in enumerate(users)}


def calculate_costs(lines, member_ids, budget_by_user):
    shares = [allocate(line, member_ids) for line in lines]
    per_user = {u: complete_sum(s[u] for s in shares) for u in member_ids}
    paid = {u: complete_sum(s[u] for line, s in zip(lines, shares) if line["paid"]) for u in member_ids}
    normalized = [dict(line, subtotal_krw=complete_sum(share.values())) for line, share in zip(lines, shares)]
    return dict(lines=normalized, known_total_krw=sum(l["subtotal_krw"] or 0 for l in normalized),
                total_krw=complete_sum(per_user.values()), per_person_krw=per_user,
                paid_krw=complete_sum(paid.values()), paid_by_user_krw=paid,
                remaining_budget_krw={u: balance(budget_by_user.get(u), paid[u]) for u in member_ids},
                planned_balance_krw={u: balance(budget_by_user.get(u), per_user[u]) for u in member_ids},
                unknown_line_count=sum(l["subtotal_krw"] is None for l in normalized),
                estimated_line_count=sum(l.get("estimated", False) for l in lines))
