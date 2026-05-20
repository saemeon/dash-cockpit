from team_ops.cards.alert_feed import alert_feed_card
from team_ops.cards.broken_card import broken_card
from team_ops.cards.headcount import headcount_card
from team_ops.cards.ticket_volume import ticket_volume_card


def get_cards():
    return [headcount_card, ticket_volume_card, alert_feed_card, broken_card]
