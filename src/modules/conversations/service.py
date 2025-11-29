from ...integrations.openai_service import OpenAIService

class ConversationService:
    def __init__(self):
        self.openai_service = OpenAIService()

    def process_conversation(self, conversation_text):
        summary = self.openai_service.summarize_conversation(conversation_text)
        return summary
