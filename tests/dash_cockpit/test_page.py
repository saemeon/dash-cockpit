from dash_cockpit._page import ConfiguratorPage, TeamPage, UserPage, page_card_ids


def test_team_page_defaults():
    p = TeamPage(name="Finance", card_ids=["rev", "cost"])
    assert p.team == ""
    assert p.columns == 2


def test_team_page_card_ids():
    p = TeamPage(name="Finance", card_ids=["rev", "cost", "margin"])
    assert page_card_ids(p) == ["rev", "cost", "margin"]


def test_user_page_card_ids():
    p = UserPage(name="My View", layout=[["rev", "cost"], ["margin"]])
    assert page_card_ids(p) == ["rev", "cost", "margin"]


def test_user_page_empty_layout():
    p = UserPage(name="Empty", layout=[])
    assert page_card_ids(p) == []


def test_team_page_empty():
    p = TeamPage(name="Empty", card_ids=[])
    assert page_card_ids(p) == []


def test_configurator_page_defaults():
    p = ConfiguratorPage(name="Build your own", template_ids=["kpi"])
    assert p.initial_card_ids == []
    assert p.columns == 2


def test_configurator_page_card_ids_returns_initial_only():
    p = ConfiguratorPage(
        name="Build your own",
        template_ids=["kpi", "trend"],
        initial_card_ids=["pinned_card"],
    )
    assert page_card_ids(p) == ["pinned_card"]


def test_configurator_page_card_ids_no_initial():
    p = ConfiguratorPage(name="Empty configurator", template_ids=["kpi"])
    assert page_card_ids(p) == []
