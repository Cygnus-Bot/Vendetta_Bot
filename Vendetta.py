import praw
import time

# --- Reddit login ---
reddit = praw.Reddit("vendetta")
subreddit = reddit.subreddit("AskOuijaRedux")
print(f"✅ Logged in as: {reddit.user.me()}")

# --- Rate limiting ---
ACTION_DELAY = 2
last_action_time = 0

def safe_action(func, *args, **kwargs):
    """Run a Reddit API action with rate limiting"""
    global last_action_time
    elapsed = time.time() - last_action_time
    if elapsed < ACTION_DELAY:
        time.sleep(ACTION_DELAY - elapsed)
    try:
        result = func(*args, **kwargs)
        last_action_time = time.time()
        return result
    except Exception as e:
        print(f"⚠️ API action failed: {e}")
        return None

# --- Helper functions ---
def collect_letters(comment):
    """Walk up the comment chain and collect single-letter comments"""
    letters = []
    current = comment.parent()
    while isinstance(current, praw.models.Comment):
        body = current.body.strip()
        if len(body) == 1 and body.isalpha():
            letters.append(body.upper())
        current = current.parent()
    return letters[::-1]

def is_goodbye(text: str) -> bool:
    """Check if text starts with 'goodbye' or 'good bye' (case-insensitive)"""
    lowered = text.lower()
    return lowered.startswith("goodbye") or lowered.startswith("good bye")

# --- Blocked word lists ---
nsfw_words = {"SEX", "PORN", "NSFW"}
politics_words = {"TRUMP", "BIDEN", "POLITICS", "USSR", "HITLER"}

# --- Modmail responses ---
nsfw_response = (
    "Hello, unfortunately your comment was removed because it violates Rule 8. "
    "Please review this rule as to not breach this in the future. "
    "If you believe this was a mistake, contact the moderators by linking this comment."
)
politics_response = (
    "Hello, unfortunately your comment was removed because it violates Rule 9. "
    "Please review this rule as to not breach this in the future. "
    "If you believe this was a mistake, contact the moderators by linking this comment."
)

# --- Stream comments ---
for comment in subreddit.stream.comments(skip_existing=True):
    text = comment.body.strip()
    print(f"{comment.author}: {text}")

    if is_goodbye(text):
        letters = collect_letters(comment)
        if not letters:
            print("🤔 No letters found in chain")
            continue

        ouija_word = "".join(letters)
        print(f"📜 Built word: {ouija_word}")

        action_taken = False
        reason = ""
        message = ""

        # Check NSFW first
        if ouija_word.upper() in nsfw_words:
            reason = "Rule 8: NSFW "
            message = nsfw_response
            action_taken = True
        # Then check Politics
        elif ouija_word.upper() in politics_words:
            reason = "Rule 9: Politics"
            message = politics_response
            action_taken = True

        if action_taken:
            # --- Check for prior abuse or ban notes ---
            prior_abuse_or_ban = False
            notes = safe_action(subreddit.mod.notes, redditor=comment.author.name)
            if notes:
                for note in notes:
                    if note.label in {"ABUSE_WARNING", "BAN", "PERMA_BAN", "BOT_BAN"}:
                        prior_abuse_or_ban = True
                        break

            if prior_abuse_or_ban:
                # Escalation: send modmail to moderators recommending a ban
                mod_link = f"https://www.reddit.com{comment.permalink}"
                escalation_subject = f"User may need to be banned: {comment.author}"
                escalation_message = (
                    f"The user u/{comment.author} has a repeat forbidden Ouija answer.\n\n"
                    f"Comment link: {mod_link}\n\n"
                    f"Reason: {reason}\n\n"
                    "This user has prior abuse or ban notes. Please review for potential banning."
                )
                for mod in subreddit.moderator():
                    safe_action(reddit.redditor(mod.name).message,
                                subject=escalation_subject,
                                message=escalation_message)
                print(f"⚠️ User {comment.author} has prior notes — escalated to moderators for possible ban.")

            # Remove the Goodbye comment
            safe_action(comment.mod.remove)
            print(f"🚫 Removed forbidden answer: {ouija_word} ({reason})")

            # Lock the parent comment
            parent = comment.parent()
            if isinstance(parent, praw.models.Comment):
                safe_action(parent.mod.lock)
                print(f"🔒 Locked parent comment: {parent.id}")

            # Add mod note
            safe_action(subreddit.mod.notes.create,
                        label="ABUSE_WARNING",
                        note=f"Ouija answer removed for {reason}: {ouija_word}",
                        redditor=comment.author.name)
            print(f"📝 Added mod note: Abuse Warning")

            # Modmail the user who posted the goodbye (skip moderators)
            if comment.author not in subreddit.moderator():
                safe_action(reddit.redditor(comment.author.name).message,
                            subject="Your Ouija answer was removed",
                            message=message)
                print(f"📬 Modmailed user {comment.author}")
            else:
                print(f"ℹ️ Skipped modmail because {comment.author} is a moderator")

            # Modmail all moderators with a link to the removed comment
            mod_link = f"https://www.reddit.com{comment.permalink}"
            mod_subject = f"Removed Ouija answer: {ouija_word}"
            mod_message = f"The following comment was removed:\n\n{mod_link}\n\nReason: {reason}"
            for mod in subreddit.moderator():
                safe_action(reddit.redditor(mod.name).message,
                            subject=mod_subject,
                            message=mod_message)
            print(f"📬 Modmailed all moderators about the removal")
        else:
            print(f"✅ Allowed answer: {ouija_word} (no action taken)")
