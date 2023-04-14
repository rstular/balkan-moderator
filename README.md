# Kebab meister

The bot that will remind you to get a flair, and do so in style.

## Deployment

First, you need to obtain Reddit application credentials (can be done [here](https://www.reddit.com/prefs/apps/)). You will need to create a script application. The redirect URI is not important, but it must be set to something.

### Deploying using `docker-compose`

1. Clone the repository
2. Create a file called `config.json` in the `data/` directory in the repository (see the template file `config.sample.json`). Put your script credentials here.
3. Create a wiki page for each subreddit you want to monitor. The page must exist, and the bot will not create it. See the [wiki page configuration](#per-subreddit-configuration-wiki-page) section for more information.
4. Run `docker compose up -d`

### Deploying as a standalone application

1. Clone the repository
2. Create a file called `config.json` in the `data/` directory in the repository (see the template file `config.sample.json`). Put your script credentials here.
3. Create a wiki page for each subreddit you want to monitor. The page must exist, and the bot will not create it. See the [wiki page configuration](#per-subreddit-configuration-wiki-page) section for more information.
4. Run `pip install -r requirements.txt`
5. Run `python3 -m kebabmeister -c data/config.json`

## Configuration

### JSON configuration

The configuration file is a JSON file. The following options are available:

#### Reddit-related options

- `client_id`: The client ID of your Reddit application
- `client_secret`: The client secret of your Reddit application
- `username`: The username of the bot account
- `password`: The password of the bot account
- `user_agent`: User agent of the bot account (not important)

#### Database related options

To avoid replying to posts & comments multiple times (for example, when the application restarts), the bot keeps track of the comments it has already replied to.

- `url`: The database URL to use. Currently, only `sqlite` is tested, though if you install the right adapter, any database should work.

#### Subreddit options

 - `monitored_subreddits`: A list of subreddits to monitor (participate in).
 - `page_name`: The wiki page to use for configuring the bot behavior in the subreddit. The page must exist, and the bot will not create it.
 - `update_interval`: The interval (in seconds) at which the bot will check for configuration changes (posts & comments are monitored continuously).

### Per-subreddit configuration (wiki page)

The bot will look for a wiki page with the name specified in the `page_name` configuration option. The page must exist, and the bot will not create it. It contains YAML-encoded configuration options. Example:

```yaml
---
reply_on_posts: true
reply_message: |
  Welcome to the subreddit, {author}!
  
  {unflaired_message}
reply_is_pinned: true
unflaired_post_action: reply
unflaired_post_subject: Flair up
unflaired_post_message:
  - You need to flair up, {author}!
  - Where your flair at, špijun? {subreddit} Doesn't tolerate unflaired users!
unflaired_comment_action: message
unflaired_comment_subject: Mamma mia, where your flair at?
unflaired_comment_message:
  - Get your flar now, or ICTY will come for you
  - You need to flair up, {author}!
whitelist: []
```

The following options are available:

- `reply_on_posts`: Whether the bot should reply to posts. If set to `false`, the bot will not post a generic welcome message under every post, but it will still execute the `unflaired_post_action`.
- `reply_message`: The message to post under every post.
- `reply_is_pinned`: Whether the reply should be pinned.
- `unflaired_post_action`: What to do with posts made by unflaired people. The following actions are supported:
  - `reply`: Reply to the post with the message specified in `unflaired_post_message`.
  - `message`: Send a message to the user with the message specified in `unflaired_post_message` and subject specified in `unflaired_post_subject`.
  - `ignore`: Do nothing.
  - `remove`: Remove the post.
- `unflaired_post_subject`: The subject of the message sent to unflaired users when `unflaired_post_action` is set to `message`.
- `unflaired_post_message`: Message body or reply body to send to unflaired users when `unflaired_post_action` is set to `reply` or `message`. It is a list of messages, the bot will pick one at random.
- `unflaired_comment_action`: What to do with comments made by unflaired people. The following actions are supported:
  - `reply`: Reply to the comment with the message specified in `unflaired_comment_message`.
  - `message`: Send a message to the user with the message specified in `unflaired_comment_message` and subject specified in `unflaired_comment_subject`.
  - `ignore`: Do nothing.
  - `remove`: Remove the comment.
- `unflaired_comment_subject`: The subject of the message sent to unflaired users when `unflaired_comment_action` is set to `message`.
- `unflaired_comment_message`: Message body or reply body to send to unflaired users when `unflaired_comment_action` is set to `reply` or `message`. It is a list of messages, the bot will pick one at random.
- `whitelist`: A list of users to ignore. The bot will not send messages to these users, and will not remove their posts/comments.

#### Text formatting

The following text formatting options are available in `reply_message`, `unflaired_post_message` and `unflaired_comment_message`:
- `{author}`: The author of the post
- `{author_flair}`: Current flair of the user
- `{submission_id}`: ID of the post
- `{submission_title}`: Title of the post
- `{subreddit}`: The subreddit the post is in
- `{subreddit_id}`: ID of the subreddit
- `{comment_id}`: ID of the comment
- `{comment_body}`: Body of the comment
- `{unflaired_message}`: The message to post if the user is unflaired. This is randomly selected from the `unflaired_post_message` list. **Only supported in `reply_message`!**

Curly braces can be escaped by doubling them, for example `{{author}}` will be rendered as `{author}`, and will not perform the replacement.