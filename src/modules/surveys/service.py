import logging

logger = logging.getLogger(__name__)

class SurveyService:
    def trigger_survey(self, email, survey_type="standard"):
        """
        Trigger a survey to be sent to the given email.
        In the future, this will integrate with an email provider.
        """
        logger.info(f"Triggering {survey_type} survey for {email}")
        
        # Mock email sending
        print(f"EMAIL SENT: Survey {survey_type} to {email}")
        
        return True
