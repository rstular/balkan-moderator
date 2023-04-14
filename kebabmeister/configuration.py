from dataclasses import dataclass, field

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class DatabaseConfiguration:
    url: str


@dataclass_json
@dataclass
class SubredditConfigConfiguration:
    page_name: str
    update_interval: int


@dataclass_json
@dataclass
class RedditConfiguration:
    client_id: str
    client_secret: str = field(repr=False)
    user_agent: str
    username: str
    password: str = field(repr=False)


@dataclass_json
@dataclass
class Configuration:
    reddit: RedditConfiguration
    database: DatabaseConfiguration
    monitored_subreddits: list[str]
    subreddit_config: SubredditConfigConfiguration
