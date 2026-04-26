from rhk_ui_mode import UI_MODE_EXPERT, UI_MODE_SIMPLE, ui_mode_config


def test_ui_mode_config_defaults_to_simple() -> None:
    cfg = ui_mode_config(None, is_cloud_env=False)

    assert cfg["mode"] == UI_MODE_SIMPLE
    assert cfg["expert"] is False
    assert cfg["show_expert_actions"] is False
    assert cfg["show_expert_export_buttons"] is False
    assert cfg["show_docx_local_save"] is False
    assert cfg["show_docx_cloud_hint"] is False
    assert cfg["show_download_diag"] is False
    assert cfg["show_internal_tabs"] is False
    assert cfg["show_legacy_ph_tools"] is False


def test_ui_mode_config_expert_local() -> None:
    cfg = ui_mode_config(UI_MODE_EXPERT, is_cloud_env=False)

    assert cfg["mode"] == UI_MODE_EXPERT
    assert cfg["expert"] is True
    assert cfg["show_expert_actions"] is True
    assert cfg["show_expert_export_buttons"] is True
    assert cfg["show_docx_local_save"] is True
    assert cfg["show_docx_cloud_hint"] is False
    assert cfg["show_download_diag"] is True
    assert cfg["show_internal_tabs"] is True
    assert cfg["show_legacy_ph_tools"] is True


def test_ui_mode_config_expert_cloud_hides_local_save() -> None:
    cfg = ui_mode_config(UI_MODE_EXPERT, is_cloud_env=True)

    assert cfg["mode"] == UI_MODE_EXPERT
    assert cfg["show_docx_local_save"] is False
    assert cfg["show_docx_cloud_hint"] is True
