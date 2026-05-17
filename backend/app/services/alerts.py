import os
import boto3
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def send_email(to_email, subject, body):
    sender = os.getenv("SES_SENDER_EMAIL")
    if not sender or not to_email:
        return False

    ses = boto3.client("ses", region_name=os.getenv("AWS_REGION"))
    ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )
    return True

def send_whatsapp(to_phone, message):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    sender = os.getenv("TWILIO_WHATSAPP_FROM")

    if not sid or not token or not sender or not to_phone:
        return False

    client = Client(sid, token)
    client.messages.create(
        body=message,
        from_=sender,
        to=f"whatsapp:{to_phone}"
    )
    return True
