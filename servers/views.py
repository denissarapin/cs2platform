from django.shortcuts import render, redirect
from django.templatetags.static import static

MAPS = ["de_mirage", "de_dust2", "de_ancient", "de_overpass", "de_train", "de_inferno", "de_nuke"]

MODES = [
    ("dm",       "DM",        "brand",   16),
    ("1v1",      "1 vs 1",    "muted",    2),
    ("retake",   "Retake",    "warn",    10),
    ("hsdm",     "HSDM",      "danger",  16),   
    ("pistoldm", "Pistol DM", "success", 16),
    ("surf",     "Surf",      "muted",   32),
    ("bhop",     "Bhop",      "success", 24),
    ("kz",       "KZ",        "warn",    24),
    ("execute",  "Execute",   "brand",   10),
    ("multicfg", "Multicfg",  "danger",  16),
]

def _mode_dict():
    return {code: {"code": code, "title": title, "color": color, "capacity": cap}
            for code, title, color, cap in MODES}

def _servers_for(mode_code):
    m = _mode_dict()[mode_code]
    cap = m["capacity"]
    servers = []
    base_port = 27015
    for i, map_name in enumerate(MAPS, start=1):
        players = max(1, (i * 3) % cap + cap // 4)
        servers.append({
            "num": 100 + i,
            "mode_code": mode_code,
            "mode_name": m["title"],
            "map": map_name,
            "players": min(players, cap),
            "capacity": cap,
            "ip": f"127.0.0.1:{base_port + i}",
            "thumb": f"img/maps/{map_name}.jpg",
        })
    return servers

def servers_home(request):
    maps = ["de_mirage", "de_dust2", "de_ancient", "de_overpass", "de_train", "de_inferno", "de_nuke"]

    def fake_players(idx, cap):
        load = (idx * 7) % 10
        pct  = 0.3 + (load / 20.0)
        val  = int(round(cap * pct))
        return min(max(val, 0), cap)

    def build_mode(code, title, capacity, color="brand"):
        servers = []
        for i, m in enumerate(maps, start=1):
            players = fake_players(i, capacity)
            servers.append({
                "no": i,
                "ip": f"127.0.0.1:{27014 + i}",
                "players": players,
                "capacity": capacity,
                "map": m,
            })
        mode = {"code": code, "title": title, "color": color, "servers": servers}
        mode["players_total"] = sum(s["players"] for s in servers)
        return mode

    modes = [
        build_mode("dm",       "DM", 16),
        build_mode("1v1",      "1 vs 1",      2, "muted"),
        build_mode("retake",   "Retake",     10, "warn"),
        build_mode("hsdm",     "HSDM",       16, "danger"),
        build_mode("pistoldm", "Pistol DM",  16, "success"),
        build_mode("surf",     "Surf",       32, "muted"),
        build_mode("bhop",     "Bhop",       24, "success"),
        build_mode("kz",       "KZ",         24, "warn"),
        build_mode("execute",  "Execute",    10, "brand"),
        build_mode("multicfg", "Multicfg",   16, "danger"),
    ]

    ctx = {"modes": modes}
    return render(request, "servers/server_list.html", ctx)

def mode_page(request, mode):
    mode_map = _mode_dict()
    if mode not in mode_map:
        return redirect("servers:home")
    info = mode_map[mode]
    servers = _servers_for(mode)
    ctx = {
        "mode": info,
        "servers": servers,
        "mode_nav": MODES,
        "active_mode": mode,
    }
    return render(request, "servers/mode.html", ctx)