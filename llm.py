import os
from google import genai
from dotenv import load_dotenv
load_dotenv()

client = genai.Client()

TOOL = {
    "type": "function",
    "name": "record_email_analysis",
    "description": "Record what kind of email this is and any structured details in it.",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "application_ack", "rejection", "interview_invite",
                    "assessment", "recruiter_reply", "offer", "not_job_related",
                ],
                "description": (
                    "Judge by what decision the email actually states, not its tone or subject "
                    "line, companies often reject politely while thanking you for applying. "
                    "application_ack: only confirms receipt, no decision made yet. "
                    "rejection: declines to move forward, even when warmly worded, e.g. "
                    "'decided to move forward with other candidates' or 'pursue candidates whose "
                    "experience more closely aligns' are rejections, regardless of a thank-you "
                    "subject line."
                ),
            },
            "company": {
                "type": "string",
                "nullable": True,
                "description": "The hiring company's name, check the opening sentences and the sender's domain, not just a signature block.",
            },
            "role": {
                "type": "string",
                "nullable": True,
                "description": "The job title mentioned, often stated in the opening sentence, e.g. 'the Machine Learning Engineer position'.",
            },
            "contact_name": {"type": "string", "nullable": True},
            "is_no_reply": {
                "type": "boolean",
                "description": "true if this is email has been sent automatically and cannot be replied to, else false",
            },
        },
        "required": ["type", "company", "role", "contact_name", "is_no_reply"],
    },
}

def analyze_email(subject: str, body: str, from_addr: str) -> dict:
    interaction = client.interactions.create(
        model="gemini-3.5-flash",
        input=(
            f"From: {from_addr}\nSubject: {subject}\n\n{body[:3000]}\n\n"
            "Analyze this email in the context of a job search."
        ),
        tools=[TOOL],
        generation_config={"tool_choice": "any"},
    )
    call = next(step for step in interaction.steps if step.type == "function_call")
    return call.arguments
