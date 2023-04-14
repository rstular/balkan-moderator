import asyncio
import random
from dataclasses import dataclass
from enum import Enum

import asyncprawcore.exceptions
import yaml
from asyncpraw.models import WikiPage
from asyncpraw.models.reddit.comment import Comment
from asyncpraw.models.reddit.submission import Submission
from asyncpraw.models.reddit.redditor import Redditor
from asyncpraw.models.reddit.subreddit import Subreddit
from dacite import from_dict, Config, MissingValueError
from loguru import logger
from sqlalchemy.exc import IntegrityError

from kebabmeister import state
from kebabmeister.configuration import Configuration
from kebabmeister.database.schemas.comment import SeenComment
from kebabmeister.database.schemas.submission import SeenSubmission
from kebabmeister.tasks import BaseTask
from kebabmeister.utils import is_whitelisted
from kebabmeister.utils.format_string import get_message


class ActionUnflaired(str, Enum):
    REPLY = "reply"
    MESSAGE = "message"
    REMOVE = "remove"
    IGNORE = "ignore"


@dataclass
class SMPerSubredditConfig:
    reply_on_posts: bool
    reply_message: str
    reply_is_pinned: bool

    unflaired_post_action: ActionUnflaired
    unflaired_post_subject: str
    unflaired_post_message: list[str]

    unflaired_comment_action: ActionUnflaired
    unflaired_comment_subject: str
    unflaired_comment_message: list[str]

    whitelist: list[str]


class SubmissionMonitoringTask(BaseTask):
    PER_SUBREDDIT_CONFIG: dict[str, SMPerSubredditConfig] = {}
    PER_SUBREDDIT_CONFIG_RAW: dict[str, str] = {}
    barriers: dict[str, asyncio.Event] = {}
    DEFAULT_CONFIG: SMPerSubredditConfig

    def __init__(self, config: Configuration):
        super().__init__(config, "submission_monitoring")
        self.DEFAULT_CONFIG = SMPerSubredditConfig(
            reply_on_posts=False,
            reply_message="Welcome!\n\n{unflaired_message}",
            reply_is_pinned=False,
            unflaired_post_action=ActionUnflaired.IGNORE,
            unflaired_post_subject="Flair up, man!",
            unflaired_post_message=["Flair up, man!"],
            unflaired_comment_action=ActionUnflaired.IGNORE,
            unflaired_comment_subject="Flair up, man!",
            unflaired_comment_message=["Flair up, man!"],
            whitelist=[],
        )

    async def run(self):
        subroutines = []
        # Spawn tasks for all subreddits
        for subreddit_name in self.config.monitored_subreddits:
            subreddit: Subreddit = await state.reddit.subreddit(subreddit_name)
            await subreddit.load()

            self.barriers[subreddit.id] = asyncio.Event()
            subroutines.append(asyncio.create_task(self._monitor_subreddit_submissions(subreddit),
                                                   name=f"submissions-{subreddit.display_name}"))
            subroutines.append(asyncio.create_task(self._monitor_subreddit_comments(subreddit),
                                                   name=f"comments-{subreddit.display_name}"))
            subroutines.append(asyncio.create_task(self._monitor_config_page(subreddit),
                                                   name=f"config-{subreddit.display_name}"))
            # Graceful startup
            await asyncio.sleep(3)

        await asyncio.gather(*subroutines)

    async def _monitor_config_page(self, subreddit: Subreddit):
        logger.info(f"Monitoring config page for subreddit {subreddit.display_name}")
        while True:
            try:
                # Get configuration string
                config_page: WikiPage = await subreddit.wiki.get_page("kebabmeister")
                config_raw: str = config_page.content_md

                # Check if the raw string has changed since the last check
                if config_raw != self.PER_SUBREDDIT_CONFIG_RAW.get(subreddit.id, ""):
                    self.PER_SUBREDDIT_CONFIG_RAW[subreddit.id] = config_raw
                    # Parse the configuration
                    config = from_dict(
                        data_class=SMPerSubredditConfig, data=yaml.safe_load(config_page.content_md), config=Config(
                            type_hooks={
                                ActionUnflaired: lambda str_action: ActionUnflaired[str_action.upper()],
                            }
                        ))
                    # Check if the parsed configuration has changed since the last successful parse
                    if config != self.PER_SUBREDDIT_CONFIG.get(subreddit.id, self.DEFAULT_CONFIG):
                        logger.debug(f"Config for subreddit {subreddit.display_name} changed")
                        # Signal to all tasks that the configuration has been initialized
                        self.PER_SUBREDDIT_CONFIG[subreddit.id] = config
                        logger.trace(f"Config for subreddit {subreddit.display_name} is now {config}")

                        self.barriers[subreddit.id].set()

            except asyncprawcore.exceptions.Forbidden:
                # If we cannot access the config page, log a warning and continue
                logger.warning(f"Could not access config page for subreddit {subreddit.display_name} (403)")
            except MissingValueError as e:
                # If the configuration is invalid, log an error and send a message to the subreddit owner
                logger.warning(f"Could not parse config for subreddit {subreddit.display_name} ({e})")
                # await self.try_message(subreddit, "Invalid configuration", f"Your configuration is invalid: {e}")
            except Exception as e:
                logger.exception(f"Could not parse config for subreddit {subreddit.display_name}", e)
            # Sleep until the next check
            await asyncio.sleep(self.config.subreddit_config.update_interval)

    async def _monitor_subreddit_comments(self, subreddit: Subreddit):
        # Wait until the configuration has been initialized
        await self.barriers[subreddit.id].wait()

        logger.info(f"Monitoring comments in subreddit {subreddit.display_name}")

        async for comment in subreddit.stream.comments():  # type: Comment
            try:
                await SubmissionMonitoringTask._add_seen_comment(comment.id)
                logger.debug(f"New comment: {comment.id}")
            except IntegrityError:
                # If the comment is already in the database, ignore it
                continue
            except Exception as e:
                logger.exception(f"Could not add comment {comment.id} to database", e)
                continue

            # Get the configuration for the current subreddit
            subreddit_cfg = self.PER_SUBREDDIT_CONFIG.get(subreddit.id, self.DEFAULT_CONFIG)
            if is_whitelisted(comment.author, subreddit_cfg.whitelist):
                continue

            if comment.author_flair_text is None and subreddit_cfg.unflaired_comment_action != ActionUnflaired.IGNORE:
                # Check if the submission needs to be deleted
                if subreddit_cfg.unflaired_comment_action == ActionUnflaired.REMOVE:
                    try:
                        await comment.mod.remove(mod_note="Unflaired comment")
                        logger.debug(f"Removed unflaired comment in subreddit {subreddit.display_name}")
                    except Exception as e:
                        logger.warning(f"Could not remove unflaired comment in subreddit {subreddit.display_name}: {e}")
                    continue
                # Check if we need to send a message to the author
                elif subreddit_cfg.unflaired_comment_action == ActionUnflaired.MESSAGE:
                    await self.try_message(comment.author, subreddit_cfg.unflaired_comment_subject,
                                           get_message(random.choice(subreddit_cfg.unflaired_comment_message),
                                                       comment=comment,
                                                       author=comment.author,
                                                       subreddit=subreddit))
                # Check if we need to reply to the submission
                elif subreddit_cfg.unflaired_post_action == ActionUnflaired.REPLY:
                    await self.try_reply(comment, get_message(random.choice(subreddit_cfg.unflaired_comment_message),
                                                              comment=comment,
                                                              author=comment.author,
                                                              subreddit=subreddit))
                else:
                    logger.warning(f"Unknown action {subreddit_cfg.unflaired_comment_action} for unflaired comments")

    async def _monitor_subreddit_submissions(self, subreddit: Subreddit):
        # Wait until the configuration has been initialized
        await self.barriers[subreddit.id].wait()

        logger.info(f"Monitoring submissions in subreddit {subreddit.display_name}")

        async for submission in subreddit.stream.submissions():  # type: Submission
            try:
                await SubmissionMonitoringTask._add_seen_submission(submission.id)
                logger.debug(f"New submission: {submission.title} ({submission.id})")
            except IntegrityError:
                # If the submission is already in the database, ignore it
                continue
            except Exception as e:
                logger.exception(f"Could not add submission {submission.id} to database", e)
                continue

            # Get the configuration for the current subreddit
            subreddit_cfg = self.PER_SUBREDDIT_CONFIG.get(subreddit.id, self.DEFAULT_CONFIG)

            unflaired_reply_text = ""  # This is a placeholder for the message that will be included in the reply
            # Check if the submission is flaired
            if (submission.author_flair_text is None
                    and not is_whitelisted(submission.author, subreddit_cfg.whitelist)
                    and subreddit_cfg.unflaired_post_action != ActionUnflaired.IGNORE):

                # Check if the submission needs to be deleted
                if subreddit_cfg.unflaired_post_action == ActionUnflaired.REMOVE:
                    try:
                        await submission.mod.remove(mod_note="Unflaired post")
                        logger.debug(f"Removed unflaired post in subreddit {subreddit.display_name}")
                    except Exception as e:
                        logger.warning(f"Could not remove unflaired post in subreddit {subreddit.display_name}: {e}")
                    continue
                # Check if we need to send a message to the author
                elif subreddit_cfg.unflaired_post_action == ActionUnflaired.MESSAGE:
                    await self.try_message(submission.author, subreddit_cfg.unflaired_post_subject,
                                           get_message(random.choice(subreddit_cfg.unflaired_post_message),
                                                       submission=submission,
                                                       author=submission.author,
                                                       subreddit=subreddit))
                # Check if we need to reply to the submission
                elif subreddit_cfg.unflaired_post_action == ActionUnflaired.REPLY:
                    # If general replies are enabled, the flair-up message will be included with that message
                    unflaired_reply_text = random.choice(subreddit_cfg.unflaired_post_message)
                    if not subreddit_cfg.reply_on_posts:
                        await self.try_reply(submission, get_message(unflaired_reply_text,
                                                                     submission=submission,
                                                                     author=submission.author,
                                                                     subreddit=subreddit))
                else:
                    logger.warning(f"Unknown action {subreddit_cfg.unflaired_post_action} for unflaired posts")

            # Check if we need to reply to the submission
            if subreddit_cfg.reply_on_posts:
                await self.try_reply(submission, get_message(subreddit_cfg.reply_message,
                                                             submission=submission,
                                                             author=submission.author,
                                                             subreddit=subreddit,
                                                             unflaired_message=unflaired_reply_text),
                                     sticky=subreddit_cfg.reply_is_pinned)

    @staticmethod
    async def _add_seen_submission(submission_id: str):
        async with state.db_session() as session:
            async with session.begin():
                session.add(SeenSubmission(reddit_id=submission_id))

    @staticmethod
    async def _add_seen_comment(comment_id: str):
        async with state.db_session() as session:
            async with session.begin():
                session.add(SeenComment(reddit_id=comment_id))

    @staticmethod
    async def try_mod_message(subreddit: Subreddit, subject: str, message: str):
        try:
            await subreddit.message(subject=subject, message=message)
        except Exception as e:
            logger.error(f"Could not send message to subreddit owner: {e}")

    @staticmethod
    async def try_message(redditor: Redditor, subject: str, message: str):
        try:
            await redditor.message(subject=subject, message=message)
        except Exception as e:
            logger.error(f"Could not send message to user: {e}")

    @staticmethod
    async def try_reply(submission: Submission | Comment, message: str, distinguish: bool = True, sticky: bool = False):
        try:
            comment: Comment = await submission.reply(message)
            if distinguish or sticky:
                await comment.mod.distinguish(how="yes" if distinguish else "no", sticky=sticky)
            logger.debug(f"Replied to {type(submission).__name__} with specified message text")
        except Exception as e:
            logger.error(f"Could not reply to {type(submission).__name__} {submission.id}: {e}")
