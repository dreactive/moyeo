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
