from uagents import Model

class ModerationRequest(Model):
    text: str

class ModerationResponse(Model):
    is_inappropriate: bool