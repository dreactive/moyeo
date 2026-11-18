"""Function descriptions and schemas for the five existing service contracts."""


def object_schema(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


STRING = {'type':'string'}
NULLABLE_STRING = {'type':['string','null']}
MONEY = {'type':['integer','null'], 'minimum':0}
VISIT = dict(type='object', properties=dict(
    item_id=STRING, place_ref=NULLABLE_STRING, date=dict(type='string',format='date'),
    preferred_start_at=dict(type=['string','null'],format='date-time'),
    stay_minutes=dict(type=['integer','null'],minimum=1),
    selected_menu_ids=dict(type='array',items=STRING),
    input_basis=dict(type='object',description='Canonical item version and opening-hours evidence fingerprint')),
    required=['item_id','place_ref','date','preferred_start_at','stay_minutes','selected_menu_ids'])
ROUTE = dict(type='object', properties=dict(
    from_ref=STRING, to_ref=STRING, distance_m=dict(type='integer',minimum=0),
    duration_seconds=dict(type='integer',minimum=0), toll_krw=MONEY, evidence_id=STRING),
    required=['from_ref','to_ref','distance_m','duration_seconds','toll_krw','evidence_id'])
COST_LINE = dict(type='object', properties=dict(
    id=STRING, description=STRING, category=dict(type='string',enum=['lodging','intercity_transport','meal','admission','car','other']),
    scope=dict(type='string',enum=['shared','per_person']), owner_id=NULLABLE_STRING,
    unit_price_krw=MONEY, quantity=dict(type='number',exclusiveMinimum=0), subtotal_krw=MONEY,
    paid=dict(type='boolean'), evidence_id=NULLABLE_STRING, assumption=NULLABLE_STRING),
    required=['id','category','scope','owner_id','description','unit_price_krw','quantity','subtotal_krw','paid','evidence_id','assumption'])

TOOL_DEFINITIONS = [
    dict(name='search_places', description='Find named places in the configured region and return observed place IDs, addresses and coordinates. Use a grounded place name; no existing place ID is required. Does not book, pay or confirm a visit.',
         parameters=object_schema(dict(query=dict(type='string',minLength=1,description='Grounded place name or search phrase'),
             region=dict(type='string',description='The actual trip region'),category=NULLABLE_STRING))),
    dict(name='get_place_details', description='Look up same-place admission/menu prices and opening hours for one observed place ID. Missing prices or hours remain unknown. Does not search an unidentified name or book tickets.',
         parameters=object_schema(dict(place_ref=dict(type='string',description='Observed place ID from the supplied place records')))),
    dict(name='get_car_route', description='Look up a driving route FROM from_ref TO to_ref, preserving that direction. Uses observed endpoint coordinates and returns distance, duration and possibly tolls. Does not calculate public transit or book transport.',
         parameters=object_schema(dict(from_ref=dict(type='string',description='Observed departure place/anchor ID'),
             to_ref=dict(type='string',description='Observed destination place/anchor ID'),
             departure_at=dict(type=['string','null'],format='date-time',description='Timezone-aware departure time; null means a current route, not an invented future-trip time')))),
    dict(name='build_itinerary', description='Calculate a draft timetable from the supplied canonical visits, anchors, conditions and observed driving legs. Only available sections can be scheduled; missing routes/hours and unplaced visits stay explicit. Does not confirm the plan for people.',
         parameters=object_schema(dict(visits=dict(type='array',items=VISIT),anchors=dict(type='object',description='Recorded origin, destination and lodging, including null when unknown'),
             constraints=dict(type='array',items=dict(type='object'),description='Recorded owner conditions and confirmation status'),route_legs=dict(type='array',items=ROUTE),
             trip_schedule=object_schema(dict(start_date=dict(type='string',format='date'),end_date=dict(type='string',format='date'),
                 day_start_time=STRING,day_end_time=STRING))))),
    dict(name='calculate_costs', description='Calculate known and unknown KRW costs, sharing and paid balances from the exact supplied canonical lines. Unknown unit prices remain null and prevent a complete final total; this is not a price lookup or payment.',
         parameters=object_schema(dict(lines=dict(type='array',items=COST_LINE),member_ids=dict(type='array',items=STRING),
             budget_by_user=dict(type='object',additionalProperties=MONEY,description='Confirmed personal or configured budgets keyed by member ID')))),
]
