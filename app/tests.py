import os
import requests
from django.core.cache import cache
from django.conf import settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "memeverse")

os.makedirs(TEMP_DIR, exist_ok=True)


payloadd = {"object":"instagram","entry":[{"time":1763032505424,"id":"17841478341580264","messaging":[{"sender":{"id":"17841478341580264"},"recipient":{"id":"1180226157355226"},"timestamp":1763032505112,"message":{"mid":"aWdfZAG1faXRlbToxOklHTWVzc2FnZAUlEOjE3ODQxNDc4MzQxNTgwMjY0OjM0MDI4MjM2Njg0MTcxMDMwMTI0NDI1OTk4ODUyNTY2NzEzODQwMzozMjUyMjIwOTQxNTQzNjQ4MTA4OTMyODI5MDczNDI3NjYwOAZDZD","attachments":[{"type":"ig_reel","payload":{"reel_video_id":"18090345520838968","title":"VIP King \ud83d\udc51 \ud83d\udcc8\n\n#EgoVibes\n#AttitudeMatters\n#SavageMode\n#AlphaMindset\n#RealTalkVibes\n#LiveOnYourTerms\n#SelfMadeVibes\n#PowerAttitude\n#MainCharacterEnergy\n#UnbotheredAlways\n#RuleYourWorld\n#NoLimitsMindset\n#MotivationDaily\n#GrindAndShine\n#SuccessIsMindset\n#LifeWithPurpose\n#FocusOnYou\n#RiseAndLead\n#BuiltNotBorn\n#OwnTheMoment\n#LegendInMaking\n#BossMentality\n#DrivenByEgo\n#LifeUnfiltered\n#NeverSettle","url":"https:\/\/lookaside.fbsbx.com\/ig_messaging_cdn\/?asset_id=18090345520838968&signature=AYdKa9IKCaJp-3wobSVoR4hCY99CoiE_CzfTMZMG2sn_N3Nn8TtN_a78AzwlfjFC7K_5uo_9NQFQSFkj_QrKlkIP3tjuVQnbD35bO-S0O1tWxsVLPvYH3VMsZRu1l0QGIfQY2kcaKyc50ixPKtEq2eotiIjysTJ9DZRR3vssMba-NBLX4s-7iL2hnvi_nyrwNVl3D2b6o2EDFRBdMQz5UcVoxxnMxNQ"}}],"is_echo":True}}]}]}

def clean_webhook_url(url: str) -> str:
    # Instagram webhook URL contains escaped slashes
    url = url.replace("\\/", "/")

    # Some webhook implementations escape backslashes too
    url = url.replace("\\", "")

    return url
def download_from_instagram_webhook(payload, language="eng"):
    """
    Takes the Instagram Messaging Webhook payload and downloads the reel directly
    from the lookaside CDN URL, then uploads to Cloudinary.
    """

    attachment = payload["entry"][0]["messaging"][0]["message"]["attachments"][0]
    media_type = attachment["type"]                       # ig_reel / image / video
    reel_id = attachment["payload"].get("reel_video_id")  # e.g. 18090345520838968
    title = attachment["payload"].get("title", "Instagram Media")
    media_url = clean_webhook_url(attachment["payload"]["url"])           # CDN download link

   

    # Download file
    ext = "mp4" if media_type == "ig_reel" else "jpg"
    local_path = os.path.join(TEMP_DIR, f"{reel_id}.{ext}")

    with open(local_path, "wb") as f:
        f.write(requests.get(media_url).content)

    print(f"Downloaded Instagram media to {local_path}")

download_from_instagram_webhook(payloadd, language="eng")