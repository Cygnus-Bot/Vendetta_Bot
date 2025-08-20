import praw
import time
import json
import os

# --- Reddit login ---
reddit = praw.Reddit("vendetta")
subreddit = reddit.subreddit("AskOuijaRedux")
print(f"✅ Logged in as: {reddit.user.me()}")

# --- Rate limiting ---
ACTION_DELAY = 1.1
last_action_time = 0


def safe_action(func, *args, **kwargs):
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
def load_words(filename):
    if not os.path.exists(filename):
        print(f"⚠️ Missing {filename}, using empty list")
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {w.upper() for w in data.get("words", [])}


# Load blocked words from JSON files
nsfw_words = load_words("nsfw.json")
politics_words = load_words("politics.json")
tos_words = load_words("tos.json")

# --- Modmail responses ---
tos_response = (
    "Hello, unfortunately your comment was removed because it violates Rule 1. "
    "Please review this rule as to not breach this in the future. "
    "If you believe this was a mistake, contact the moderators by linking this comment."
)
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
try:
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

            # Check NSFW
            if ouija_word.upper() in nsfw_words:
                reason = "Rule 8: NSFW "
                message = nsfw_response
                action_taken = True
            # Check Politics
            elif ouija_word.upper() in politics_words:
                reason = "Rule 9: Politics"
                message = politics_response
                action_taken = True
            # Check TOS Violations
            elif ouija_word.upper() in tos_words:
                reason = "Rule 1: TOS Broken"
                message = tos_response
                action_taken = True

            if action_taken:
                # --- Check for prior abuse or ban notes ---
                prior_abuse_or_ban = False
                try:
                    notes = reddit.redditor(str(comment.author)).mod.notes(subreddit=subreddit)
                    for note in notes:
                        if note.label in {"ABUSE_WARNING", "BAN", "PERMA_BAN", "BOT_BAN"}:
                            prior_abuse_or_ban = True
                            break
                except Exception as e:
                    print(f"⚠️ Could not fetch mod notes for {comment.author}: {e}")

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
                    safe_action(subreddit.message,
                        subject=escalation_subject,
                        message=escalation_message)
                    print(f"⚠️ User {comment.author} has prior notes — escalated to moderators for possible ban.")

                # --- Determine how many letter comments to remove ---
                letters_to_remove = 0
                if len(ouija_word) == 3:
                    letters_to_remove = 1
                elif len(ouija_word) == 4:
                    letters_to_remove = 2
                elif len(ouija_word) >= 5:
                    letters_to_remove = 3

                # Collect all parent letter comments
                parent_comments = []
                current = comment.parent()
                while isinstance(current, praw.models.Comment):
                    body = current.body.strip()
                    if len(body) == 1 and body.isalpha():
                        parent_comments.append(current)
                    current = current.parent()

                # Reverse to get order from first letter to last
                parent_comments = parent_comments[::-1]

                # Remove last N letters
                for bad_letter_comment in parent_comments[-letters_to_remove:]:
                    safe_action(bad_letter_comment.mod.remove)
                    print(f"🚫 Removed letter comment: {bad_letter_comment.body} ({reason})")

                    # Add mod note for the letter
                    try:
                        subreddit.mod.notes.create(
                            label="ABUSE_WARNING",
                            user=bad_letter_comment.author,
                            note=f"Letter contributing to forbidden word {ouija_word}"
                        )
                        print("📝 Added mod note for letter")
                    except Exception as e:
                        print(f"⚠️ Failed to add mod note for letter: {e}")

                    # Modmail moderators about the removed letter
                    mod_link = f"https://www.reddit.com{bad_letter_comment.permalink}"
                    safe_action(subreddit.message,
                                subject=f"Removed letter contributing to {ouija_word}",
                                message=f"Letter comment removed:\n\n{mod_link}\n\nReason: {reason}")
                    print("📬 Modmailed moderators about letter removal")

                # Finally, remove the Goodbye comment itself
                safe_action(comment.mod.remove)
                print(f"🚫 Removed forbidden Goodbye: {ouija_word} ({reason})")

                # Add mod note for the Goodbye
                try:
                    subreddit.mod.notes.create(
                        label="ABUSE_WARNING",
                        user=comment.author,
                        note=f"{reason}: {ouija_word}"
                    )
                    print("📝 Added mod note: Abuse Warning for Goodbye")
                except Exception as e:
                    print(f"⚠️ API action failed when adding mod note: {e}")

                # Modmail the user who posted the Goodbye (skip moderators)
                if comment.author not in subreddit.moderator():
                    safe_action(reddit.redditor(comment.author.name).message,
                                subject="Your Ouija answer was removed",
                                message=message)
                    print(f"📬 Modmailed user {comment.author}")
                else:
                    print(f"ℹ️ Skipped modmail because {comment.author} is a moderator")

                # Modmail all moderators with a link to the removed Goodbye
                mod_link = f"https://www.reddit.com{comment.permalink}"
                mod_subject = f"Goodbye removed: {ouija_word}"
                mod_message = f"The following Goodbye was removed:\n\n{mod_link}\n\nReason: {reason}. " \
                              f"Please remove the necessary contributions"

                safe_action(subreddit.message,
                            subject=mod_subject,
                            message=mod_message)
                print("📬 Sent modmail to moderators for Goodbye")

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
                mod_subject = f"Goodbye removed: {ouija_word}"
                mod_message = f"The following goodbye was removed:\n\n{mod_link}\n\nReason: {reason}. " \
                              f"Please remove the necessary contributions"

                safe_action(subreddit.message,
                            subject=mod_subject,
                            message=mod_message)
                print("📬 Sent modmail to moderators")
                print(f"📬 Modmailed all moderators about the removal")
            else:
                safe_action(comment.mod.approve)
                print(f"✅ Allowed answer: {ouija_word} (no action taken)")
except Exception as e:
    error_message = f"🚨 I have just eaten shit and died! Please help me.\n\nError: {e}"
    safe_action(subreddit.message,
        subject="Vendetta_Bot crashed",
        message=error_message
    )
    raise