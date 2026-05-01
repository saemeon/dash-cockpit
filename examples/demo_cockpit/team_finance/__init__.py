from team_finance.cards.cash_position import cash_position_card
from team_finance.cards.revenue_trend import revenue_trend_card
from team_finance.templates.kpi_lookup import KpiLookupTemplate


def get_cards():
    return [revenue_trend_card, cash_position_card]


def get_card_templates():
    return [KpiLookupTemplate]
