import praw, prawcore, time, json
r = praw.Reddit("vendetta")
sub = r.subreddit("AskOuijaRedux") 
configfile = open("config.json", "r")
config = json.load(configfile)

def getRemovalIDs():
    for id in sub.mod.removal_reasons:
        print(f"TITLE: {id.title} - ID: {id}")

def removeContent(item, ruleName):
    try:
        removalReason = config.get(ruleName, None).get("removalReason", None)
        ruleAction = config.get(ruleName, None).get("modActions", None)
        ruleMessage = sub.mod.removal_reasons[removalReason].message
        item.mod.remove(reason_id=removalReason)
        item.mod.send_removal_message(title="Content Removed", message=str(ruleMessage), type="private")
        try:
            r.comment(item.id).author.notes.create(
                label=str(ruleAction), note=f"{ruleName} Violation.", subreddit=sub
            )
        except (TypeError, AttributeError):
            pass
        
        warnings = 0
        for note in sub.mod.notes.redditors(item.author, limit=999):
            if note.type == "NOTE":
                if note.label in ["SPAM_WATCH", "SPAM_WARNING", "ABUSE_WARNING"]:
                    warnings = warnings+1
    
        if warnings > 1:
            print("User needs to be Banned")




    except praw.exceptions.RedditAPIException:
        pass
    

if __name__ == "__main__":
    getRemovalIDs()