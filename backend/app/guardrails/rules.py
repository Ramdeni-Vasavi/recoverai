from app.agent.policies import RecoveryAction

GUARDRAIL_VERSION = "recoverai-guard-v1"
MAX_AUTOMATIC_RETRIES = 2
ALLOWED_ACTIONS = {action.value for action in RecoveryAction}
