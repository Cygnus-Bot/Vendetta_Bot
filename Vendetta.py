import praw, time, json, os, removalmanager

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

try:
    # --- Stream comments ---
    for comment in subreddit.stream.comments(skip_existing=True):
        submission = comment.submission
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
                reason = "rule8"
                action_taken = True

            # Check Politics
            elif ouija_word.upper() in politics_words:
                reason = "rule9"
                action_taken = True

            # Check TOS Violations
            elif ouija_word.upper() in tos_words:
                reason = "rule1"
                action_taken = True

            if action_taken:
                removalmanager.removeContent(comment, reason)

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
                    removalmanager.removeContent(bad_letter_comment, reason)
                    print(f"🚫 Removed letter comment: {bad_letter_comment.body} ({reason})")
            else:
                safe_action(comment.mod.approve)
                print(f"✅ Allowed answer: {ouija_word} (no action taken)")

except Exception as e:
    error_message = f"🚨 I have just eaten shit and died! Please help me.\n\nError: {e}"
    safe_action(subreddit.message,
        subject="Vendetta_Bot crashed",
        message=error_message
    )