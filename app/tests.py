import requests

def send_instagram_reply():
    url = f"https://graph.facebook.com/v18.0/832475516619479/messages"
    
   
    payload = {
        "recipient": {"id": "1180226157355226"},
        "message": {"text": "successfully uploaded"}
    }

    params = {
        "access_token": "EAALT4fBUzwYBP97VPNZBSnA1pq29vXi1m7ZB5okGlmJRnQRxJ4Ul2yV5HZAWsfL64nmU1SUlh5c8BSB3UcflfpsVrWnupOw6yC9b1x3BGsghZAP77rebCjOzzg44JxQTdET8ZAPFgca5XbteJBWBTmKjM652AnJtjlim2qSAzo9ysxodq1OqZB1HmfnOUZAnLKNsj7boLalxM4ZCX44ZBLiLOZApjIrWTUbgIv"
    }

    response = requests.post(url, params=params, json=payload)
    print(response.json())
    # print("message sent")
    return response.json()

send_instagram_reply()