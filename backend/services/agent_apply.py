def valid_result_base(db, result):
    run = db.get('run:' + result['run_id'])
    room = db.get('room:' + result['room_id'])
    return bool(
        run and room and not run.get('applied')
        and run['room_id'] == result['room_id']
        and run['base_versions'] == result['base_versions'] == room['versions']
    )
