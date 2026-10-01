class AccessLog:
    # EVAL: bait -- matches the documented exception for audit tables.
    def append(self, actor, action):
        return {"actor": actor, "action": action}
