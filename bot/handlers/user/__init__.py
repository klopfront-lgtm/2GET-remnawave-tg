from aiogram import Router

from . import start
# TODO: after splitting subscription into a package, replace this import
from .subscription import router as subscription_router
from . import referral
from . import promo_user
from . import trial_handler
from . import profile
from . import balance_topup
from . import tariff_selection
from . import subscriptions_management

user_router_aggregate = Router(name="user_router_aggregate")

user_router_aggregate.include_router(promo_user.router)
user_router_aggregate.include_router(trial_handler.router)
user_router_aggregate.include_router(profile.router)
user_router_aggregate.include_router(balance_topup.router)
user_router_aggregate.include_router(subscriptions_management.router)
user_router_aggregate.include_router(tariff_selection.router)
user_router_aggregate.include_router(start.router)
user_router_aggregate.include_router(subscription_router)
user_router_aggregate.include_router(referral.router)
