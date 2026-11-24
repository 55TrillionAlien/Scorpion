import json
import time
import re
import html
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode, unquote

BASE = "https://aion2.plaync.com"
SERVER_ID = 2011
RACE = 2

NAMES = [
    "어둠의염화",
    "시크한허니",
    "할만해진",
    "뺏뙈지",
    "파멸의염화",
    "할만헤진",
    "보조허니",
    "심판의염화",
    "공허의염화",
    "짬뙈지",
    "할만해지",
    "솜주먹허니",
    "심연의염화",
    "뒤통수허니",
    "꽃뙈지",
    "할만해요"
]

KNOWN_IDS = {
    "뺏뙈지": "qkievOI_8Q3CkS_kBcpkiCI3QSJ0q3FdY__bx9VZsNE="
}

FILE = Path("players.json")

def now():
    return datetime.now(
        timezone(timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M:%S KST")

def get_json(path, params):
    url = BASE + path + "?" + urlencode(params)
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "ScorpionRanking/1.0",
        "Accept-Language": "ko-KR"
    })
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read())

def find_id(name):
    data = get_json(
        "/ko-kr/api/search/aion2/search/v2/character",
        {
            "keyword": name,
            "race": RACE,
            "serverId": SERVER_ID
        }
    )

    for item in data.get("list", []):
        found = html.unescape(
            re.sub("<[^>]+>", "", item.get("name", ""))
        )
        if found == name and item.get("characterId"):
            return unquote(item["characterId"])

    raise ValueError("캐릭터 검색 실패")

def get_player(name, cid):
    data = get_json(
        "/api/character/info",
        {
            "lang": "ko",
            "characterId": cid,
            "serverId": SERVER_ID
        }
    )

    profile = data["profile"]

    if profile["characterName"] != name:
        raise ValueError("닉네임 불일치")

    if int(profile["serverId"]) != SERVER_ID:
        raise ValueError("서버 불일치")

    if int(profile["raceId"]) != RACE:
        raise ValueError("종족 불일치")

    power = int(profile["combatPower"])
    job = profile["className"]

    item_level = next(
        (
            int(str(s["value"]).replace(",", ""))
            for s in data["stat"]["statList"]
            if s.get("type") == "ItemLevel"
        ),
        None
    )

    if item_level is None or not job:
        raise ValueError("필수 정보 누락")

    return {
        "name": name,
        "job": job,
        "power": power,
        "itemLevel": item_level,
        "characterId": cid,
        "updatedAt": now(),
        "status": "success"
    }

def main():
    previous = {}

    if FILE.exists():
        old = json.loads(
            FILE.read_text(encoding="utf-8")
        )
        previous = {
            p["name"]: p
            for p in old.get("players", [])
        }

    results = []
    success = 0

    for name in NAMES:
        old = previous.get(name, {})
        try:
            cid = (
                old.get("characterId")
                or KNOWN_IDS.get(name)
                or find_id(name)
            )

            player = get_player(name, cid)
            results.append(player)
            success += 1

            print(
                f"SUCCESS: {name} | "
                f"{player['job']} | "
                f"{player['power']:,} | "
                f"{player['itemLevel']:,}"
            )

        except Exception as e:
            results.append({
                "name": name,
                **old,
                "status": "failed"
            })
            print(f"FAILED: {name} | {e}")

            if getattr(e, "code", None) in (403, 429):
                print("Access restricted. Stopping requests.")
                break

        time.sleep(2)

    if success == 0:
        raise SystemExit("No successful updates")

    collected = {p["name"]: p for p in results}

    results = [
        collected.get(name, {
            "name": name,
            **previous.get(name, {}),
            "status": "skipped"
        })
        for name in NAMES
    ]

    output = {
        "updatedAt": now(),
        "source": "NC AION2",
        "successCount": success,
        "totalCount": len(NAMES),
        "players": results
    }

    FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(f"COMPLETED: {success}/{len(NAMES)}")

if __name__ == "__main__":
    main()
