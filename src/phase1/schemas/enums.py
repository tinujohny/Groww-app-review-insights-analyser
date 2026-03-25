from enum import Enum


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class ReviewSource(str, Enum):
    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"


class PipelineRunTrigger(str, Enum):
    SCHEDULED = "scheduled"
    CLI = "cli"
    UI = "ui"
    BACKFILL = "backfill"
