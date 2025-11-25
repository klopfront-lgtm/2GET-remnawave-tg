from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):

    waiting_for_broadcast_message = State()
    confirming_broadcast = State()
    waiting_for_promo_details = State()
    waiting_for_promo_code = State()
    waiting_for_promo_bonus_days = State()
    waiting_for_promo_max_activations = State()
    waiting_for_promo_validity_days = State()
    waiting_for_promo_type = State()
    waiting_for_promo_value = State()
    waiting_for_promo_tariff_selection = State()
    waiting_for_promo_min_purchase = State()
    waiting_for_promo_edit_details = State()
    waiting_for_promo_edit_code = State()
    waiting_for_promo_edit_bonus_days = State()
    waiting_for_promo_edit_max_activations = State()
    waiting_for_promo_edit_validity_days = State()
    waiting_for_bulk_promo_quantity = State()
    waiting_for_bulk_promo_bonus_days = State()
    waiting_for_bulk_promo_max_activations = State()
    waiting_for_bulk_promo_validity_days = State()
    waiting_for_user_id_to_ban = State()
    waiting_for_user_id_to_unban = State()

    waiting_for_user_id_for_logs = State()
    
    # User management states
    waiting_for_user_search = State()
    waiting_for_subscription_days_to_add = State()
    waiting_for_direct_message_to_user = State()
    waiting_for_user_delete_confirmation = State()

    # Ads campaigns
    waiting_for_ad_source = State()
    waiting_for_ad_start_param = State()
    waiting_for_ad_cost = State()

    # Tariff management states
    waiting_for_tariff_name = State()
    waiting_for_tariff_description = State()
    waiting_for_tariff_price = State()
    waiting_for_tariff_duration = State()
    waiting_for_tariff_traffic_limit = State()
    waiting_for_tariff_device_limit = State()
    waiting_for_tariff_speed_limit = State()
    waiting_for_tariff_edit_field = State()
    waiting_for_tariff_edit_value = State()
    waiting_for_tariff_delete_confirmation = State()

    # Discount management states
    waiting_for_discount_user_id = State()
    waiting_for_discount_percentage = State()
    waiting_for_discount_tariff_selection = State()
    waiting_for_discount_view_user_id = State()
    
    # Subscription limits management states
    waiting_for_subscription_limit = State()
    waiting_for_traffic_limit = State()
    waiting_for_device_limit = State()
    waiting_for_subscription_name = State()
