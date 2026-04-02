"""Permission Catalogue data — the actual catalogue seeded from real codebase registries.

Builds the full permission tree across 8 domains.
Venue names and entitlements are sourced from UAC where available.
"""

from __future__ import annotations

from unified_api_contracts.internal.schemas.rbac import Entitlement

from unified_trading_api.models.permission_catalogue import (
    CataloguePermission,
    CatalogueTree,
    DomainNode,
    PermissionCategory,
    PermissionDomain,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _perm(
    domain: PermissionDomain,
    category: str,
    key: str,
    label: str,
    description: str = "",
    is_internal_only: bool = False,
) -> CataloguePermission:
    return CataloguePermission(
        key=f"{domain.value}.{category}.{key}",
        label=label,
        description=description,
        domain=domain,
        category=category,
        is_internal_only=is_internal_only,
    )


def _cat(
    domain: PermissionDomain,
    key: str,
    label: str,
    description: str,
    permissions: list[CataloguePermission],
) -> PermissionCategory:
    return PermissionCategory(
        key=key,
        label=label,
        domain=domain,
        description=description,
        permissions=permissions,
    )


# ---------------------------------------------------------------------------
# Domain 1: Platform Services
# ---------------------------------------------------------------------------

_D = PermissionDomain

_PLATFORM_PUBLIC_PERMS = [
    _perm(_D.PLATFORM_SERVICES, "core", "data", "Data Access", "View market data dashboards"),
    _perm(_D.PLATFORM_SERVICES, "core", "research", "Research", "Access research tools"),
    _perm(_D.PLATFORM_SERVICES, "core", "trading", "Trading", "Place and manage trades"),
    _perm(_D.PLATFORM_SERVICES, "core", "execution", "Execution", "Execute orders"),
    _perm(_D.PLATFORM_SERVICES, "core", "observe", "Observe", "Monitor system and positions"),
    _perm(_D.PLATFORM_SERVICES, "core", "manage", "Manage", "Manage configurations"),
    _perm(_D.PLATFORM_SERVICES, "core", "reports", "Reports", "View and generate reports"),
]

_PLATFORM_INTERNAL_PERMS = [
    _perm(_D.PLATFORM_SERVICES, "internal", "admin", "Admin", "System administration", is_internal_only=True),
    _perm(_D.PLATFORM_SERVICES, "internal", "ops", "Operations", "Operational controls", is_internal_only=True),
    _perm(_D.PLATFORM_SERVICES, "internal", "config", "Config", "System configuration", is_internal_only=True),
    _perm(_D.PLATFORM_SERVICES, "internal", "devops", "DevOps", "Deployment and infrastructure", is_internal_only=True),
]

_PLATFORM_DOMAIN = DomainNode(
    domain=_D.PLATFORM_SERVICES,
    label="Platform Services",
    description="Core platform capabilities and internal tools",
    categories=[
        _cat(_D.PLATFORM_SERVICES, "core", "Core Services", "Public platform services", _PLATFORM_PUBLIC_PERMS),
        _cat(_D.PLATFORM_SERVICES, "internal", "Internal Tools", "Staff-only tools", _PLATFORM_INTERNAL_PERMS),
    ],
)

# ---------------------------------------------------------------------------
# Domain 2: Data Access
# ---------------------------------------------------------------------------

# Venue permissions — sourced from UAC registry/venue_constants.py
_CEFI_VENUES = [
    "binance", "coinbase", "bybit", "okx", "deribit", "kraken_futures",
    "gate_io", "kucoin", "htx", "mexc", "bitget", "crypto_com",
    "bitmex", "phemex", "woo_x",
]

_TRADFI_VENUES = [
    "databento", "yahoo_finance", "alpha_vantage", "polygon_io",
    "fred", "quandl", "iex_cloud",
]

_DEFI_VENUES = [
    "aave_v3", "uniswap_v3", "uniswap_v2", "compound_v3", "curve",
    "balancer", "sushiswap", "pancakeswap", "gmx", "hyperliquid",
    "lido", "rocket_pool", "eigenlayer", "ethena", "pendle",
    "instadapp", "morpho",
]

_SPORTS_VENUES = [
    "betfair", "pinnacle", "smarkets", "matchbook",
    "polymarket", "kalshi",
]

_PREDICTION_VENUES = ["polymarket", "kalshi", "novig", "prophetx"]

_VENUE_PERMS: list[CataloguePermission] = []
for _venue in sorted(set(_CEFI_VENUES + _TRADFI_VENUES + _DEFI_VENUES + _SPORTS_VENUES + _PREDICTION_VENUES)):
    _VENUE_PERMS.append(
        _perm(_D.DATA_ACCESS, "venues", _venue, _venue.replace("_", " ").title(), f"Access {_venue} data")
    )

_MARKET_CATEGORY_PERMS = [
    _perm(_D.DATA_ACCESS, "market_categories", "cefi", "CeFi", "Centralised exchange data"),
    _perm(_D.DATA_ACCESS, "market_categories", "tradfi", "TradFi", "Traditional finance data"),
    _perm(_D.DATA_ACCESS, "market_categories", "defi", "DeFi", "Decentralised finance data"),
    _perm(_D.DATA_ACCESS, "market_categories", "sports", "Sports", "Sports betting data"),
    _perm(_D.DATA_ACCESS, "market_categories", "prediction", "Prediction", "Prediction market data"),
]

_DATA_TYPE_PERMS = [
    _perm(_D.DATA_ACCESS, "data_types", "tick", "Tick Data", "Raw tick-level data"),
    _perm(_D.DATA_ACCESS, "data_types", "daily", "Daily Data", "End-of-day aggregations"),
    _perm(_D.DATA_ACCESS, "data_types", "order_book", "Order Book", "Level 2 order book snapshots"),
    _perm(_D.DATA_ACCESS, "data_types", "processed", "Processed Data", "Cleaned and normalised data"),
    _perm(_D.DATA_ACCESS, "data_types", "features", "Features", "Computed feature data"),
]

_INSTRUMENT_TYPE_PERMS = [
    _perm(_D.DATA_ACCESS, "instrument_types", "spot_pair", "Spot Pair", "Spot trading pairs"),
    _perm(_D.DATA_ACCESS, "instrument_types", "perpetual", "Perpetual", "Perpetual futures"),
    _perm(_D.DATA_ACCESS, "instrument_types", "future", "Future", "Dated futures"),
    _perm(_D.DATA_ACCESS, "instrument_types", "option", "Option", "Options contracts"),
    _perm(_D.DATA_ACCESS, "instrument_types", "equity", "Equity", "Equities and stocks"),
    _perm(_D.DATA_ACCESS, "instrument_types", "etf", "ETF", "Exchange-traded funds"),
    _perm(_D.DATA_ACCESS, "instrument_types", "lp_pool", "LP Pool", "Liquidity pool tokens"),
    _perm(_D.DATA_ACCESS, "instrument_types", "lending_pool", "Lending Pool", "Lending protocol pools"),
    _perm(_D.DATA_ACCESS, "instrument_types", "prediction_market", "Prediction Market", "Binary outcome markets"),
    _perm(_D.DATA_ACCESS, "instrument_types", "exchange_odds", "Exchange Odds", "Sports exchange odds"),
    _perm(_D.DATA_ACCESS, "instrument_types", "fixed_odds", "Fixed Odds", "Bookmaker fixed odds"),
]

_DATA_ACCESS_DOMAIN = DomainNode(
    domain=_D.DATA_ACCESS,
    label="Data Access",
    description="Venue, market category, data type, and instrument type permissions",
    categories=[
        _cat(_D.DATA_ACCESS, "venues", "Venues", "Per-venue data access", _VENUE_PERMS),
        _cat(_D.DATA_ACCESS, "market_categories", "Market Categories", "Category-level data access", _MARKET_CATEGORY_PERMS),
        _cat(_D.DATA_ACCESS, "data_types", "Data Types", "Data type access", _DATA_TYPE_PERMS),
        _cat(_D.DATA_ACCESS, "instrument_types", "Instrument Types", "Instrument type access", _INSTRUMENT_TYPE_PERMS),
    ],
)

# ---------------------------------------------------------------------------
# Domain 3: Research & ML
# ---------------------------------------------------------------------------

_RESEARCH_PERMS = [
    _perm(_D.RESEARCH_ML, "training", "model_training", "Model Training", "Train ML models"),
    _perm(_D.RESEARCH_ML, "training", "experiments", "Experiments", "Run and manage experiments"),
    _perm(_D.RESEARCH_ML, "training", "feature_store", "Feature Store", "Access the feature store"),
    _perm(_D.RESEARCH_ML, "registry", "model_registry", "Model Registry", "Browse and manage model registry"),
    _perm(_D.RESEARCH_ML, "registry", "deployment", "Model Deployment", "Deploy models to production"),
    _perm(_D.RESEARCH_ML, "backtesting", "backtesting", "Backtesting", "Run strategy backtests"),
    _perm(_D.RESEARCH_ML, "backtesting", "candidates", "Candidates", "View backtest candidate strategies"),
    _perm(_D.RESEARCH_ML, "backtesting", "comparison", "Comparison", "Compare backtest results"),
    _perm(_D.RESEARCH_ML, "backtesting", "handoff", "Handoff", "Promote backtested strategies to live"),
    _perm(_D.RESEARCH_ML, "signals", "signal_access", "Signal Access", "Access ML-generated signals"),
]

_RESEARCH_DOMAIN = DomainNode(
    domain=_D.RESEARCH_ML,
    label="Research & ML",
    description="Machine learning, backtesting, and signal access",
    categories=[
        _cat(_D.RESEARCH_ML, "training", "Training", "Model training and experimentation", [
            p for p in _RESEARCH_PERMS if p.category == "training"
        ]),
        _cat(_D.RESEARCH_ML, "registry", "Registry", "Model registry and deployment", [
            p for p in _RESEARCH_PERMS if p.category == "registry"
        ]),
        _cat(_D.RESEARCH_ML, "backtesting", "Backtesting", "Strategy backtesting", [
            p for p in _RESEARCH_PERMS if p.category == "backtesting"
        ]),
        _cat(_D.RESEARCH_ML, "signals", "Signals", "Signal access", [
            p for p in _RESEARCH_PERMS if p.category == "signals"
        ]),
    ],
)

# ---------------------------------------------------------------------------
# Domain 4: Execution
# ---------------------------------------------------------------------------

_ALGO_PERMS = [
    _perm(_D.EXECUTION, "algos", "twap", "TWAP", "Time-weighted average price"),
    _perm(_D.EXECUTION, "algos", "vwap", "VWAP", "Volume-weighted average price"),
    _perm(_D.EXECUTION, "algos", "sor", "SOR", "Smart order routing"),
    _perm(_D.EXECUTION, "algos", "iceberg", "Iceberg", "Iceberg order execution"),
    _perm(_D.EXECUTION, "algos", "pov", "POV", "Percentage of volume"),
    _perm(_D.EXECUTION, "algos", "passive_aggressive", "PassiveAggressive", "Passive-aggressive execution"),
    _perm(_D.EXECUTION, "algos", "adaptive_twap", "AdaptiveTWAP", "Adaptive TWAP execution"),
    _perm(_D.EXECUTION, "algos", "almgren_chriss", "AlmgrenChriss", "Almgren-Chriss optimal execution"),
]

_INSTRUCTION_TYPE_PERMS = [
    _perm(_D.EXECUTION, "instruction_types", "trade", "Trade", "Standard trade instruction"),
    _perm(_D.EXECUTION, "instruction_types", "swap", "Swap", "DeFi swap instruction"),
    _perm(_D.EXECUTION, "instruction_types", "zero_alpha", "Zero Alpha", "Zero-alpha rebalance"),
    _perm(_D.EXECUTION, "instruction_types", "prediction_bet", "Prediction Bet", "Prediction market bet"),
    _perm(_D.EXECUTION, "instruction_types", "futures_roll", "Futures Roll", "Futures contract roll"),
    _perm(_D.EXECUTION, "instruction_types", "options_combo", "Options Combo", "Options combination order"),
    _perm(_D.EXECUTION, "instruction_types", "add_liquidity", "Add Liquidity", "DeFi liquidity provision"),
]

_EXECUTION_GATE_PERMS = [
    _perm(_D.EXECUTION, "gates", "can_trade", "Can Trade", "Global trade execution gate"),
    _perm(_D.EXECUTION, "gates", "venue_execution", "Venue Execution", "Per-venue execution permission"),
]

_EXECUTION_DOMAIN = DomainNode(
    domain=_D.EXECUTION,
    label="Execution",
    description="Algo selection, instruction types, and execution gates",
    categories=[
        _cat(_D.EXECUTION, "algos", "Algorithms", "Execution algorithm access", _ALGO_PERMS),
        _cat(_D.EXECUTION, "instruction_types", "Instruction Types", "Order instruction types", _INSTRUCTION_TYPE_PERMS),
        _cat(_D.EXECUTION, "gates", "Gates", "Execution gates and controls", _EXECUTION_GATE_PERMS),
    ],
)

# ---------------------------------------------------------------------------
# Domain 5: Reporting & Regulatory
# ---------------------------------------------------------------------------

_REPORTING_PERMS = [
    _perm(_D.REPORTING_REGULATORY, "reporting", "pnl_attribution", "P&L Attribution", "Profit and loss attribution reports"),
    _perm(_D.REPORTING_REGULATORY, "reporting", "settlement", "Settlement", "Trade settlement reports"),
    _perm(_D.REPORTING_REGULATORY, "reporting", "reconciliation", "Reconciliation", "Position and trade reconciliation"),
    _perm(_D.REPORTING_REGULATORY, "regulatory", "regulatory", "Regulatory Reporting", "Regulatory compliance reports"),
    _perm(_D.REPORTING_REGULATORY, "regulatory", "executive_summary", "Executive Summary", "Executive-level summaries"),
    _perm(_D.REPORTING_REGULATORY, "reporting", "client_reporting", "Client Reporting", "Client-facing reports"),
]

_REPORTING_DOMAIN = DomainNode(
    domain=_D.REPORTING_REGULATORY,
    label="Reporting & Regulatory",
    description="P&L, settlement, reconciliation, and regulatory reporting",
    categories=[
        _cat(_D.REPORTING_REGULATORY, "reporting", "Reporting", "Financial and operational reports", [
            p for p in _REPORTING_PERMS if p.category == "reporting"
        ]),
        _cat(_D.REPORTING_REGULATORY, "regulatory", "Regulatory", "Regulatory and executive reports", [
            p for p in _REPORTING_PERMS if p.category == "regulatory"
        ]),
    ],
)

# ---------------------------------------------------------------------------
# Domain 6: Internal Provisioning
# ---------------------------------------------------------------------------

_PROVISIONING_PERMS = [
    _perm(_D.INTERNAL_PROVISIONING, "slack", "workspace", "Slack Workspace", "Manage Slack workspace", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "slack", "channels", "Slack Channels", "Manage Slack channels", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "github", "org", "GitHub Org", "Manage GitHub organisation", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "github", "teams", "GitHub Teams", "Manage GitHub teams", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "github", "repos", "GitHub Repos", "Manage GitHub repositories", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "microsoft", "account", "M365 Account", "Manage Microsoft 365 accounts", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "microsoft", "license", "M365 License", "Manage Microsoft 365 licences", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "microsoft", "groups", "M365 Groups", "Manage Microsoft 365 groups", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "gcp", "project", "GCP Project", "Manage GCP projects", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "gcp", "iam", "GCP IAM", "Manage GCP IAM policies", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "aws", "iam", "AWS IAM", "Manage AWS IAM", is_internal_only=True),
    _perm(_D.INTERNAL_PROVISIONING, "aws", "sso", "AWS SSO", "Manage AWS SSO", is_internal_only=True),
]

_PROVISIONING_DOMAIN = DomainNode(
    domain=_D.INTERNAL_PROVISIONING,
    label="Internal Provisioning",
    description="Staff-only provisioning for Slack, GitHub, M365, GCP, AWS",
    categories=[
        _cat(_D.INTERNAL_PROVISIONING, "slack", "Slack", "Slack workspace management", [
            p for p in _PROVISIONING_PERMS if p.category == "slack"
        ]),
        _cat(_D.INTERNAL_PROVISIONING, "github", "GitHub", "GitHub org management", [
            p for p in _PROVISIONING_PERMS if p.category == "github"
        ]),
        _cat(_D.INTERNAL_PROVISIONING, "microsoft", "Microsoft 365", "M365 management", [
            p for p in _PROVISIONING_PERMS if p.category == "microsoft"
        ]),
        _cat(_D.INTERNAL_PROVISIONING, "gcp", "GCP", "Google Cloud Platform management", [
            p for p in _PROVISIONING_PERMS if p.category == "gcp"
        ]),
        _cat(_D.INTERNAL_PROVISIONING, "aws", "AWS", "Amazon Web Services management", [
            p for p in _PROVISIONING_PERMS if p.category == "aws"
        ]),
    ],
)

# ---------------------------------------------------------------------------
# Domain 7: Org-Level Scoping
# ---------------------------------------------------------------------------

_ORG_SCOPING_PERMS = [
    _perm(_D.ORG_SCOPING, "org", "subscription_ceiling", "Subscription Ceiling", "Organisation subscription tier ceiling"),
    _perm(_D.ORG_SCOPING, "org", "user_subset", "User Subset", "Limit user access to org subset"),
    _perm(_D.ORG_SCOPING, "org", "data_scoping", "Data Scoping", "Scope data visibility per org"),
]

_ORG_SCOPING_DOMAIN = DomainNode(
    domain=_D.ORG_SCOPING,
    label="Org-Level Scoping",
    description="Organisation-level access controls and limits",
    categories=[
        _cat(_D.ORG_SCOPING, "org", "Organisation", "Organisation-level controls", _ORG_SCOPING_PERMS),
    ],
)

# ---------------------------------------------------------------------------
# Domain 8: Feature Subscriptions
# ---------------------------------------------------------------------------

# Map UAC Entitlement enum values to catalogue permissions
_ENTITLEMENT_PERMS = [
    _perm(
        _D.FEATURE_SUBSCRIPTIONS,
        "entitlements",
        ent.value.replace("-", "_"),
        ent.value.replace("-", " ").title(),
        f"Entitlement gate: {ent.value}",
    )
    for ent in Entitlement
]

_SUBSCRIPTION_PERMS = [
    _perm(_D.FEATURE_SUBSCRIPTIONS, "subscriptions", "signal_subscriptions", "Signal Subscriptions", "Subscribe to trading signals"),
    _perm(_D.FEATURE_SUBSCRIPTIONS, "subscriptions", "custom_feeds", "Custom Feeds", "Custom data feed access"),
    _perm(_D.FEATURE_SUBSCRIPTIONS, "subscriptions", "premium_flags", "Premium Flags", "Premium feature flags"),
]

_FEATURE_SUBSCRIPTIONS_DOMAIN = DomainNode(
    domain=_D.FEATURE_SUBSCRIPTIONS,
    label="Feature Subscriptions",
    description="Entitlement gates, signal subscriptions, and premium features",
    categories=[
        _cat(_D.FEATURE_SUBSCRIPTIONS, "entitlements", "Entitlements", "UAC entitlement gates (from rbac.py)", _ENTITLEMENT_PERMS),
        _cat(_D.FEATURE_SUBSCRIPTIONS, "subscriptions", "Subscriptions", "Signal and feed subscriptions", _SUBSCRIPTION_PERMS),
    ],
)

# ---------------------------------------------------------------------------
# Full catalogue
# ---------------------------------------------------------------------------

_ALL_DOMAINS: list[DomainNode] = [
    _PLATFORM_DOMAIN,
    _DATA_ACCESS_DOMAIN,
    _RESEARCH_DOMAIN,
    _EXECUTION_DOMAIN,
    _REPORTING_DOMAIN,
    _PROVISIONING_DOMAIN,
    _ORG_SCOPING_DOMAIN,
    _FEATURE_SUBSCRIPTIONS_DOMAIN,
]


def _count_permissions(domains: list[DomainNode]) -> int:
    total = 0
    for domain in domains:
        for cat in domain.categories:
            total += len(cat.permissions)
    return total


def _count_categories(domains: list[DomainNode]) -> int:
    total = 0
    for domain in domains:
        total += len(domain.categories)
    return total


PERMISSION_CATALOGUE = CatalogueTree(
    domains=_ALL_DOMAINS,
    total_permissions=_count_permissions(_ALL_DOMAINS),
    total_categories=_count_categories(_ALL_DOMAINS),
)
