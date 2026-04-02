Great choice — HomeConnect is a well-known target for this. Good news: **you don't need to reverse engineer the APK at all.**

---

## Bosch HomeConnect Has an Official API

Bosch publishes a **developer API** for HomeConnect appliances:

- 🌐 **https://developer.home-connect.com**
- Full REST API with OAuth2
- Covers dishwashers, ovens, washing machines, etc.
- Free developer access

---

## How It Works

```
Your Code → HomeConnect API → Bosch Cloud → Your Dishwasher (via WiFi)
```

The app just wraps this same API.

---

## Step-by-Step: Get Your Dishwasher Controllable

**1. Register as a Developer**
- Go to https://developer.home-connect.com
- Sign up with the **same email as your HomeConnect app account**

**2. Create an Application**
- Dashboard → "Applications" → "Register Application"
- OAuth flow: pick `Authorization Code`
- Redirect URI: `http://localhost:8080` (for local testing)
- Note your `client_id` and `client_secret`

**3. Authenticate (OAuth2)**
```python
# Quick local OAuth2 flow
import requests
from urllib.parse import urlencode

CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
REDIRECT_URI = "http://localhost:8080"
BASE_URL = "https://api.home-connect.com"

auth_params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": "IdentifyAppliance Monitor Control",
}

print("Open this URL in browser:")
print(f"{BASE_URL}/security/oauth/authorize?{urlencode(auth_params)}")

# After redirect, grab the `code` from the URL
code = input("Paste the code from redirect URL: ")

token_response = requests.post(f"{BASE_URL}/security/oauth/token", data={
    "grant_type": "authorization_code",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "code": code,
})

tokens = token_response.json()
ACCESS_TOKEN = tokens["access_token"]
print("Access token:", ACCESS_TOKEN)
```

**4. Discover Your Appliances**
```python
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

appliances = requests.get(f"{BASE_URL}/api/homeappliances", headers=headers).json()
for a in appliances["data"]["homeappliances"]:
    print(a["haId"], a["type"], a["name"])
# Output: BOSCH-HXX-XXXXXXXXXXXXXXX  Dishwasher  My Dishwasher
```

**5. Get Available Programs**
```python
HA_ID = "BOSCH-HXX-XXXXXXXXXXXXXXX"

programs = requests.get(
    f"{BASE_URL}/api/homeappliances/{HA_ID}/programs/available",
    headers=headers
).json()

for p in programs["data"]["programs"]:
    print(p["key"])
# e.g.: Dishcare.Program.Auto2, Dishcare.Program.Eco50, etc.
```

**6. Start a Program**
```python
payload = {
    "data": {
        "key": "Dishcare.Program.Auto2",
        "options": [
            {"key": "BSH.Common.Option.StartInRelative", "value": 0, "unit": "seconds"},
            {"key": "Dishcare.Option.IntensivZone", "value": False},
            {"key": "Dishcare.Option.BrillianceDry", "value": True},
        ]
    }
}

response = requests.put(
    f"{BASE_URL}/api/homeappliances/{HA_ID}/programs/active",
    headers={**headers, "Content-Type": "application/json"},
    json=payload
)
print(response.status_code)  # 204 = success
```

**7. Monitor Status (SSE stream)**
```python
import sseclient

stream = requests.get(
    f"{BASE_URL}/api/homeappliances/{HA_ID}/events",
    headers={**headers, "Accept": "text/event-stream"},
    stream=True
)

client = sseclient.SSEClient(stream)
for event in client.events():
    print(event.data)
```

---

## Key Dishwasher Options Reference

| Option Key | Values |
|---|---|
| `Dishcare.Option.IntensivZone` | `true/false` |
| `Dishcare.Option.BrillianceDry` | `true/false` |
| `Dishcare.Option.VarioSpeedPlus` | `true/false` |
| `BSH.Common.Option.StartInRelative` | seconds (e.g. 3600 = 1hr delay) |
| `BSH.Common.Option.FinishInRelative` | seconds until finish |

---

## Even Better: Home Assistant Integration

If you use **Home Assistant**, there's a ready-made HomeConnect integration that wraps all of this — zero code needed.

---

Want me to build a clean Python client class around this, or wire it into something specific (automation, CLI, Telegram bot, etc.)?
