from asyncpraw.models.reddit.subreddit import Subreddit
from asyncpraw.models.reddit.comment import Comment
from asyncpraw.models.reddit.submission import Submission
from asyncpraw.models.reddit.redditor import Redditor


def get_message(base_msg: str,
                author: Redditor = None,
                submission: Submission = None,
                subreddit: Subreddit = None,
                comment: Comment = None,
                **kwargs) -> str:
    custom_format = {
        "author": author.name if author else None,
        "author_flair": submission.author_flair_text if submission else None,
        "submission_id": submission.id if submission else None,
        "submission_title": submission.title if submission else None,
        "subreddit": subreddit.display_name if subreddit else None,
        "subreddit_id": subreddit.id if subreddit else None,
        "comment_id": comment.id if comment else None,
        "comment_body": comment.body if comment else None,
    }
    return base_msg.format(**custom_format, **kwargs)
