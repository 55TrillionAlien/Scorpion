"""Use the existing, previously working update.py API helpers."""
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from update import find_id, get_player, KNOWN_IDS

KST = timezone(timedelta(hours=9))
FILE = Path('players.json')

def stamp():
    return datetime.now(KST).isoformat(timespec='seconds')

def parse_time(value):
    try:
        d = datetime.fromisoformat(value.replace(' KST', '+09:00'))
        return d.astimezone(KST) if d.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None

def read_roster():
    names = json.loads(Path('members.json').read_text(encoding='utf-8'))
    if not isinstance(names, list) or any(not isinstance(n, str) or not n.strip() for n in names):
        raise ValueError('members.json must be an array of non-empty names')
    names = [n.strip() for n in names]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate names in members.json')
    return names

def sample(p):
    t = parse_time(p.get('updatedAt'))
    if t is None or not isinstance(p.get('power'), int) or not isinstance(p.get('itemLevel'), int):
        return None
    return {'at': t.isoformat(timespec='seconds'), 'power': p['power'], 'itemLevel': p['itemLevel']}

def retain_hourly(points, current):
    cutoff = current - timedelta(days=9)
    buckets = {}
    for p in points:
        t = parse_time(p.get('at'))
        if t is None or t < cutoff or t > current or not isinstance(p.get('power'), int) or not isinstance(p.get('itemLevel'), int):
            continue
        key = t.replace(minute=0, second=0, microsecond=0)
        if key not in buckets or t >= parse_time(buckets[key]['at']):
            buckets[key] = p
    return [buckets[k] for k in sorted(buckets)]

def main():
    names = read_roster()
    old = json.loads(FILE.read_text(encoding='utf-8')) if FILE.exists() else {}
    previous = {p['name']: p for p in old.get('players', [])}
    history = old.get('history', {})
    result, new_history = [], {}
    success = 0
    blocked = False
    for name in names:
        prior = previous.get(name, {})
        points = list(history.get(name, []))
        # Migrate only a genuine, timestamped previously successful record.
        if not points and prior.get('status') == 'success':
            s = sample(prior)
            if s:
                points.append(s)
        if blocked:
            player = {**prior, 'name': name, 'status': 'skipped'}
        else:
            try:
                cid = prior.get('characterId') or KNOWN_IDS.get(name) or find_id(name)
                player = get_player(name, cid)
                player['updatedAt'] = stamp()
                player['status'] = 'success'
                s = sample(player)
                if s is None:
                    raise ValueError('Invalid power/item data')
                points.append(s)
                success += 1
                print(f"SUCCESS {name}: {player['job']} | {player['power']} | {player['itemLevel']}")
            except Exception as e:
                player = {**prior, 'name': name, 'status': 'failed'}
                print(f'FAILED {name}: {e}')
                if getattr(e, 'code', None) in (403, 429):
                    blocked = True
                    print('Access restricted: stopping further requests.')
            if not blocked:
                time.sleep(2)
        result.append(player)
        new_history[name] = retain_hourly(points, datetime.now(KST))
    out = {
        'source': 'NC AION2', 'updatedAt': stamp() if success else old.get('updatedAt'),
        'lastAttemptAt': stamp(), 'successCount': success, 'totalCount': len(names),
        'players': result, 'history': new_history
    }
    temp = FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(FILE)
    print(f'COMPLETED: {success}/{len(names)}')
    if names and success == 0:
        print('::warning::No successful NC updates; last known values retained.')
    elif success < len(names):
        print('::warning::Some NC updates failed; last known values retained.')

if __name__ == '__main__':
    main()
