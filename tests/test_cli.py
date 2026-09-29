import json

from pdx_logs import cli

ERROR_LOG_LINES = [
    "[10:00:01][jomini_effect.cpp:1162]: Variable 'am' is set but is never used. Note that use in localization doesn't count due to technical limitations. Use in unused scripted triggers and effects also does not count",
    "[10:00:01][jomini_effect.cpp:1166]: Event target 'fe_su' is used but is never set. Setting it in an unused scripted trigger or effect does not count",
    "[10:00:02][localization_util.cpp:103]: MODIFIER_TYPE_NAME_can_extract_provisions: \"Can extract provisions\"",
    "[10:00:03][pdx_data_callstack.cpp:17]: No context supplied (Use SetDataContext), wanted context of type 'GameLobby' for 'GameLobby.Ready'",
    "[10:00:04][jomini_effect_impl.cpp:495]: common/scripted_effects/gdpw.txt:12: GDPW-INVARIANT share sum 1.02 at 1337.4.1",
]
ROTATED_LINES = [
    "[09:00:01][jomini_effect.cpp:1166]: Event target 'fe_wealth_estate' is used but is never set. Setting it in an unused scripted trigger or effect does not count",
    "[09:00:02][localization_util.cpp:103]: MODIFIER_TYPE_NAME_can_extract_provisions: \"Can extract provisions\"",
]


def write_logs(tmp_path):
    (tmp_path / "error.1.log").write_text("\n".join(ROTATED_LINES) + "\n", encoding="utf-8")
    (tmp_path / "error.log").write_text("\n".join(ERROR_LOG_LINES) + "\n", encoding="utf-8")
    return tmp_path


def groups_for(tmp_path):
    _, paths = cli.resolve_log_set(write_logs(tmp_path), "error")
    messages, _, _ = cli.parse_files(paths)
    return cli.normalize_messages(messages)


def test_error_log_lines_keep_error_severity(tmp_path):
    groups = groups_for(tmp_path)
    key = next(k for k in groups if k.startswith("error_log:"))
    assert groups[key]["severity"] == "error"
    scored, actionable, _ = cli.score_and_split(groups, ["sul_"])
    assert actionable[0]["pattern_key"] == key or groups[key]["priority"] >= 100


def test_context_type_name_survives_masking(tmp_path):
    groups = groups_for(tmp_path)
    keys = [k for k in groups if "wanted context" in k]
    assert keys and "of type 'GameLobby' for '…'" in keys[0]


def test_used_and_set_patterns_name_the_kind(tmp_path):
    groups = groups_for(tmp_path)
    assert groups["Event target used but never set"]["params"] == ["fe_wealth_estate", "fe_su"]
    assert groups["Variable set but never used"]["params"] == ["am"]


def test_keys_export_dedups_across_rotation(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PDX_LOG_DIR", str(write_logs(tmp_path)))
    cfg = {"prefixes": [], "logs_dir": None}
    assert cli.cmd_keys(["--all-sessions"], cfg) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        "unlocalized\tloc key\tMODIFIER_TYPE_NAME_can_extract_provisions\t2",
        "unused_vars\tvariable\tam\t1",
        "unset_vars\tevent target\tfe_su\t1",
        "unset_vars\tevent target\tfe_wealth_estate\t1",
    ]


def test_keys_json_and_selector(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PDX_LOG_DIR", str(write_logs(tmp_path)))
    cfg = {"prefixes": [], "logs_dir": None}
    cli.cmd_keys(["--unset-vars", "--json", "--all-sessions"], cfg)
    data = json.loads(capsys.readouterr().out)
    assert list(data["exports"]) == ["unset_vars"]
    assert [e["name"] for e in data["exports"]["unset_vars"]] == ["fe_su", "fe_wealth_estate"]
