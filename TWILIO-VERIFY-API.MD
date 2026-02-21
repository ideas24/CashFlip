https://www.twilio.com/docs/verify/api

Verify API


As part of Twilio's account security offerings, the Twilio Verify API enables you to add user verification to your web application. The API supports the following channels:

SMS
Base URL


All URLs in this documentation use the following base URL:


Copy code block
https://verify.twilio.com/v2/
The Twilio REST API is served over HTTPS. To ensure data privacy, unencrypted HTTP is not supported.

Authentication


To authenticate requests to the Twilio APIs, Twilio supports HTTP Basic authentication
. Use your API key as the username and your API key secret as the password. You can create an API key either in the Twilio Console or using the API.

Note: Twilio recommends using API keys for authentication in production apps. For local testing, you can use your Account SID as the username and your Auth token as the password. You can find your Account SID and Auth Token in the Twilio Console
.

Learn more about Twilio API authentication.


Copy code block
curl -X POST https://verify.twilio.com/v2/Services \
    -d FriendlyName=MyServiceName \
    -u $TWILIO_API_KEY:$TWILIO_API_KEY_SECRET
User verification workflow


This section shows the 3 steps required to complete a basic one-time passcode (OTP) verification. Follow the links for more documentation on advanced features such as service configuration, custom codes, rate limiting, PSD2 compliance, and more.
Step 1: Create a Verification Service

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

service = client.verify.v2.services.create(
    friendly_name="My First Verify Service"
)

print(service.sid)
Response

Copy response
{
  "sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "friendly_name": "My First Verify Service",
  "code_length": 4,
  "lookup_enabled": false,
  "psd2_enabled": false,
  "skip_sms_to_landlines": false,
  "dtmf_input_required": false,
  "tts_name": "name",
  "do_not_share_warning_enabled": false,
  "custom_code_enabled": true,
  "push": {
    "include_date": false,
    "apn_credential_sid": "CRaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "fcm_credential_sid": null
  },
  "totp": {
    "issuer": "test-issuer",
    "time_step": 30,
    "code_length": 3,
    "skew": 2
  },
  "whatsapp": {
    "msg_service_sid": "MGaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "from": "whatsapp:+1234567890"
  },
  "passkeys": {
    "relying_party": {
      "id": "www.mydomain.com",
      "name": "My domain",
      "origins": [
        "www.mydomain.com",
        "www.login.mydomain.com"
      ]
    },
    "authenticator_attachment": "",
    "discoverable_credentials": null,
    "user_verification": "discouraged"
  },
  "default_template_sid": "HJaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verify_event_subscription_enabled": false,
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z",
  "url": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "links": {
    "verification_checks": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/VerificationCheck",
    "verifications": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Verifications",
    "rate_limits": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/RateLimits",
    "messaging_configurations": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/MessagingConfigurations",
    "entities": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Entities",
    "webhooks": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Webhooks",
    "access_tokens": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/AccessTokens"
  }
}

A Verification Service is the set of common configurations used to create and check verifications. This includes features like:

Friendly name (used in the verification message templates, except in countries with brand restrictions
)
Code length
Other service-level options
One verification service can be used to send multiple verification tokens, it is not necessary to create a new service each time.

Step 2: Send a verification token

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verifications.create(to="+15017122661", channel="sms")

print(verification.status)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "pending",
  "valid": false,
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z",
  "lookup": {},
  "amount": null,
  "payee": null,
  "send_code_attempts": [
    {
      "time": "2015-07-30T20:00:00Z",
      "channel": "SMS",
      "attempt_sid": "VLaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "sna": null,
  "url": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Verifications/VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
This request sends a token to the end user through the specified channel. Newly created verifications have a status of pending. Supported channels are:
Step 3: Check the verification token

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification_check = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verification_checks.create(to="+15017122661", code="123456")

print(verification_check.status)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "approved",
  "valid": true,
  "amount": null,
  "payee": null,
  "sna_attempts_error_codes": [],
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z"
}
This request checks whether the user-provided token is correct.

Token	Status in response
Correct	approved
Incorrect	pending

Verify SMS overview


SMS is the most popular channel for phone number verification and two-factor authentication (2FA) because most people can receive text messages and onboarding is seamless.

SMS 2FA is effective. Studies show it blocks the majority of automated attacks, bulk phishing attempts, and targeted attacks.

Learn how to send one-time passcodes (OTPs) via SMS with Twilio Verify SMS. Before you send your first OTP, obtain and document recipient consent following the Twilio Messaging Policy. To learn more and stay compliant, see the Consent and Opt-in Policy.

The following example shows how to start a verification with SMS:

Start a Verification with SMS

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verifications.create(to="+15017122661", channel="sms")

print(verification.sid)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "pending",
  "valid": false,
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z",
  "lookup": {},
  "amount": null,
  "payee": null,
  "send_code_attempts": [
    {
      "time": "2015-07-30T20:00:00Z",
      "channel": "SMS",
      "attempt_sid": "VLaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "sna": null,
  "url": "https://verify.twilio.com/v2/Services/VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Verifications/VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
After you start a verification with SMS, use the Verification Check API to confirm the code the user provides.
Verification Check


Use the VerificationCheck resource to validate that the user-provided token is correct.

Prerequisites:

Create a Verification Service
Start a Verification
VerificationCheck Response Properties


These fields are returned in the output JSON response. The type SID<VE> is a unique ID starting with the letters VE.

Property nameTypeRequiredPIIDescriptionChild properties
sid
SID<VE>
Optional
Not PII
The unique string that we created to identify the VerificationCheck resource.

Pattern:
^VE[0-9a-fA-F]{32}$
Min length:
34
Max length:
34
service_sid
SID<VA>
Optional
Not PII
The SID of the Service the resource is associated with.

Pattern:
^VA[0-9a-fA-F]{32}$
Min length:
34
Max length:
34
account_sid
SID<AC>
Optional
Not PII
The SID of the Account that created the VerificationCheck resource.

Pattern:
^AC[0-9a-fA-F]{32}$
Min length:
34
Max length:
34
to
string
Optional
PII MTL: 30 days
The phone number or email being verified. Phone numbers must be in E.164 format.

channel
enum<string>
Optional
Not PII
The verification method to use. One of: email, sms, whatsapp, call, or sna.

Possible values:
sms
call
email
whatsapp
sna
status
string
Optional
Not PII
The status of the verification. Can be: pending, approved, canceled, max_attempts_reached, deleted, failed or expired.

valid
boolean
Optional
Not PII
Use "status" instead. Legacy property indicating whether the verification was successful.

amount
string
Optional
PII MTL: 1 day
The amount of the associated PSD2 compliant transaction. Requires the PSD2 Service flag enabled.

payee
string
Optional
PII MTL: 1 day
The payee of the associated PSD2 compliant transaction. Requires the PSD2 Service flag enabled.

date_created
string<date-time>
Optional
Not PII
The ISO 8601
 date and time in GMT when the Verification Check resource was created.

date_updated
string<date-time>
Optional
Not PII
The ISO 8601
 date and time in GMT when the Verification Check resource was last updated.

sna_attempts_error_codes
array
Optional
Not PII
List of error codes as a result of attempting a verification using the sna channel. The error codes are chronologically ordered, from the first attempt to the latest attempt. This will be an empty list if no errors occured or null if the last channel used wasn't sna.

Check a Verification


POST https://verify.twilio.com/v2/Services/{ServiceSid}/VerificationCheck

(warning)
Warning
Twilio deletes the verification SID once it's:

expired (after 10 minutes)
approved
max check attempts reached
If any of these events occur, the VerificationCheck request returns a 404 Not Found error similar to the following example:


Copy code block
Unable to create record: The requested resource /Services/VAXXXXXXXXXXXXX/VerificationCheck was not found
To review what happened to a specific verification, use the Verify Logs in the Twilio Console
.

You can pass the following input parameters. A SID<VE> value is a unique ID that starts with VE.

Path parameters


Property nameTypeRequiredPIIDescription
service_sid
SID<VA>
required
Not PII
The SID of the verification Service to create the resource under.

Pattern:
^VA[0-9a-fA-F]{32}$
Min length:
34
Max length:
34
Request body parameters


Encoding type:application/x-www-form-urlencoded
Schema
Example
Property nameTypeRequiredPIIDescriptionChild properties
code
string
Optional
Not PII
The 4-10 character string being verified.

to
string
Optional
PII MTL: 30 days
The phone number or email to verify. Either this parameter or the verification_sid must be specified. Phone numbers must be in E.164 format.

verification_sid
SID<VE>
Optional
Not PII
A SID that uniquely identifies the Verification Check. Either this parameter or the to phone number/email must be specified.

Pattern:
^VE[0-9a-fA-F]{32}$
Min length:
34
Max length:
34
amount
string
Optional
PII MTL: 1 day
The amount of the associated PSD2 compliant transaction. Requires the PSD2 Service flag enabled.

payee
string
Optional
PII MTL: 1 day
The payee of the associated PSD2 compliant transaction. Requires the PSD2 Service flag enabled.

sna_client_token
string
Optional
Not PII
A sna client token received in sna url invocation response needs to be passed in Verification Check request and should match to get successful response.

Check a Verification with a Phone Number

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification_check = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verification_checks.create(to="+15017122661", code="1234")

print(verification_check.status)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "approved",
  "valid": true,
  "amount": null,
  "payee": null,
  "sna_attempts_error_codes": [],
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z"
}
Check a Verification with a SID

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification_check = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verification_checks.create(
    verification_sid="VEXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", code="1234"
)

print(verification_check.status)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "approved",
  "valid": true,
  "amount": null,
  "payee": null,
  "sna_attempts_error_codes": [],
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z"
}
Check a Silent Network Auth Verification with Error Codes

Python

Report code block

Copy code block
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

verification_check = client.verify.v2.services(
    "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
).verification_checks.create(to="+15017122661")

print(verification_check.sid)
Response

Copy response
{
  "sid": "VEaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "service_sid": "VAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "account_sid": "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to": "+15017122661",
  "channel": "sms",
  "status": "approved",
  "valid": true,
  "amount": null,
  "payee": null,
  "sna_attempts_error_codes": [],
  "date_created": "2015-07-30T20:00:00Z",
  "date_updated": "2015-07-30T20:00:00Z"
}
An SNA VerificationCheck can display a status value of approved while still listing error codes in sna_attempts_error_codes. This situation occurs when an earlier SNA verification attempt fails and produces an error code, but a later attempt succeeds and approves the verification.

